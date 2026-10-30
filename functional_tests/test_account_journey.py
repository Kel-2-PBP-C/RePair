"""Real browser journeys against an isolated live Django test server.

Only the external Google and region-service boundaries are mocked. Cookies,
CSRF, sessions, form submissions, redirects, templates and JavaScript are real.
"""

import os
from unittest.mock import Mock, patch
from urllib.parse import urlencode, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.http import HttpResponseRedirect
from django.test import override_settings
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from accounts.models import GoogleIdentity, Profile


@override_settings(
    GOOGLE_ONLY_AUTH=True,
    GOOGLE_CLIENT_ID="browser-test-client",
    GOOGLE_CLIENT_SECRET="browser-test-secret",
    GOOGLE_REDIRECT_URI="http://localhost:8000/accounts/google/callback/",
    GOOGLE_ALLOW_REGISTRATION=True,
    PRODUCTION=False,
)
class AccountBrowserTests(StaticLiveServerTestCase):
    password = "BrowserAccount!729Blue"
    changed_password = "ChangedAccount!938Green"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-background-networking")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("prefs", {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        })
        if os.environ.get("CHROME_BINARY"):
            options.binary_location = os.environ["CHROME_BINARY"]
        service = Service(executable_path=os.environ.get("CHROMEDRIVER"))
        cls.browser = webdriver.Chrome(service=service, options=options)
        cls.addClassCleanup(cls.browser.quit)

    def setUp(self):
        self.browser.delete_all_cookies()
        self.browser.set_window_size(1440, 1000)
        self.wait = WebDriverWait(self.browser, 10)
        provider = Mock()
        provider.authorize_redirect.side_effect = lambda request, uri, **kwargs: HttpResponseRedirect(
            reverse("accounts:google_callback") + "?" + urlencode({"state": kwargs["state"], "code": "browser-test"})
        )
        self.enterContext(patch("accounts.google_auth.get_google_client", return_value=provider))
        self.enterContext(patch("accounts.google_auth.verified_claims", return_value={
            "subject": "browser-subject", "email": "browser@example.com", "name": "Browser Member",
        }))
        self.enterContext(patch("accounts.regions.search_regions", return_value=[]))

    def open_page(self, name, fragment=""):
        self.browser.get(self.live_server_url + reverse(name) + fragment)

    def element(self, selector):
        return self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))

    def fill(self, selector, value):
        field = self.element(selector)
        field.clear()
        field.send_keys(value)

    def click(self, selector):
        element = self.element(selector)
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        element.click()

    def wait_for_page(self, name):
        self.wait.until(lambda driver: urlsplit(driver.current_url).path == reverse(name))

    def submit(self, selector):
        button = self.element(selector)
        invalid_fields = self.browser.execute_script(
            "return arguments[0].formNoValidate ? [] : Array.from(arguments[0].form.elements)"
            ".filter(field => field.willValidate && !field.validity.valid)"
            ".map(field => field.name);", button,
        )
        self.assertEqual(invalid_fields, [], "Browser validation prevents submission")
        old_document = self.browser.find_element(By.TAG_NAME, "html")
        self.click(selector)
        self.wait.until(EC.staleness_of(old_document))

    def google_sign_in(self, username, password):
        self.open_page("accounts:auth")
        self.click("#google-login")
        self.wait_for_page("accounts:credentials")
        self.fill("#id_username", username)
        self.fill("#id_password", password)
        self.submit(".brand-form button[type=submit]")

    def complete_onboarding(self):
        self.wait_for_page("accounts:complete_profile")
        self.fill("#id_domicile", "Depok")
        self.element("#id_domicile").send_keys(Keys.ESCAPE)
        self.click("label[for='id_preferred_categories_1']")
        self.submit("button[value=save]")
        self.wait_for_page("core:landing")

    def test_google_registration_profile_preferences_password_logout_and_deletion(self):
        self.google_sign_in("browsermember", self.password)
        self.complete_onboarding()
        user = get_user_model().objects.get(username="browsermember")
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.profile.preferred_categories, ["buku"])
        self.assertTrue(user.profile.onboarding_completed)

        self.open_page("accounts:profile")
        self.assertTrue(self.element("#id_username").get_property("readOnly"))
        self.click("[data-profile-edit]")
        self.fill("#id_username", "discarded-name")
        self.click("[data-profile-cancel]")
        self.assertEqual(self.element("#id_username").get_attribute("value"), "browsermember")
        self.assertTrue(self.element("#id_username").get_property("readOnly"))

        self.click("[data-profile-edit]")
        self.fill("#id_username", "updatedmember")
        self.fill("#id_full_name", "Updated Member")
        # Native date controls use OS-specific keyboard segments. Set their ISO
        # value and dispatch the same events as selecting a day in the picker.
        self.browser.execute_script(
            "arguments[0].value = '2000-01-02';"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            self.element("#id_birth_date"),
        )
        self.fill("#id_domicile", "Bandung")
        self.element("#id_domicile").send_keys(Keys.ESCAPE)
        self.submit("[data-profile-save] button")
        user.refresh_from_db()
        self.assertEqual(user.username, "updatedmember")
        self.assertEqual(user.first_name, "Updated Member")
        self.assertEqual(user.profile.domicile, "Bandung")
        self.assertEqual(user.email, "browser@example.com")

        self.open_page("accounts:profile", "#settings")
        self.click("#id_email_notifications")
        self.click("#id_profile_visibility")
        Select(self.element("#id_language")).select_by_value("en")
        self.submit("#settings button[type=submit]")
        profile = Profile.objects.get(user=user)
        self.assertFalse(profile.email_notifications)
        self.assertFalse(profile.profile_visibility)
        self.assertEqual(profile.language, "en")

        self.open_page("accounts:profile", "#security")
        self.fill("#id_old_password", self.password)
        self.fill("#id_new_password1", self.changed_password)
        self.fill("#id_new_password2", self.changed_password)
        self.submit("#security button[type=submit]")
        self.wait_for_page("accounts:profile")
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.changed_password))
        self.submit("button[form=settings-logout-form]")
        self.wait_for_page("accounts:auth")

        self.google_sign_in("updatedmember", self.changed_password)
        self.wait_for_page("accounts:complete_profile")
        self.submit("button[value=skip]")
        self.wait_for_page("core:landing")
        self.open_page("accounts:profile", "#account-status")
        self.fill("#id_deactivate_password", self.changed_password)
        self.click("#id_confirm")
        self.submit("#account-status button[type=submit]")
        self.wait_for_page("home")
        self.assertFalse(get_user_model().objects.filter(pk=user.pk).exists())
        self.assertFalse(Profile.objects.filter(user_id=user.pk).exists())
        self.assertFalse(GoogleIdentity.objects.filter(user_id=user.pk).exists())
        self.open_page("accounts:profile")
        self.wait_for_page("accounts:auth")

    def test_mobile_login_error_and_profile_validation_preserve_saved_data(self):
        user = get_user_model().objects.create_user(
            username="existingmember", email="browser@example.com", password=self.password,
            first_name="Existing Member",
        )
        GoogleIdentity.objects.create(user=user, subject="browser-subject", email=user.email)
        Profile.objects.create(user=user, domicile="Depok", birth_date="2000-01-02", onboarding_completed=True)
        self.browser.set_window_size(390, 844)
        self.google_sign_in("existingmember", "incorrect-password")
        self.wait_for_page("accounts:credentials")
        self.assertIn("tidak benar", self.element("[role=alert]").text)
        self.fill("#id_password", self.password)
        self.submit(".brand-form button[type=submit]")
        self.wait_for_page("accounts:complete_profile")
        self.submit("button[value=skip]")
        self.wait_for_page("core:landing")
        self.open_page("accounts:profile")
        self.click("[data-profile-edit]")
        self.fill("#id_username", "invalid username!")
        self.submit("[data-profile-save] button")
        self.assertEqual(self.element("[data-profile-editor]").get_attribute("data-profile-invalid"), "true")
        self.assertTrue(self.element("#id_username_error").text)
        user.refresh_from_db()
        self.assertEqual(user.username, "existingmember")
        self.click("[data-profile-cancel]")
        self.wait.until(lambda driver: driver.find_element(By.ID, "id_username").get_attribute("value") == "existingmember")
        self.assertTrue(self.element("[data-profile-edit]").is_displayed())
