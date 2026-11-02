"""Functional HTTP journey through the real middleware, forms, sessions and DB.

Only Google's external client is stubbed; CSRF protection remains enabled.
Browser/JavaScript behavior is deliberately outside this Django client test.
"""

from unittest.mock import Mock, patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.http import HttpResponseRedirect
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts import google_auth
from accounts.models import GoogleIdentity, Profile
from barter_details.models import Barter


@override_settings(
    GOOGLE_ONLY_AUTH=True,
    GOOGLE_CLIENT_ID="journey-client.apps.googleusercontent.com",
    GOOGLE_CLIENT_SECRET="journey-test-secret",
    GOOGLE_REDIRECT_URI="http://localhost:8000/accounts/google/callback/",
    GOOGLE_ALLOW_REGISTRATION=True,
    PRODUCTION=False,
)
class GoogleMemberJourneyTests(TestCase):
    password = "SepedaLangit!782Biru"
    new_password = "KameraHujan!953Hijau"

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.provider = Mock()
        self.provider.authorize_redirect.return_value = HttpResponseRedirect(
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        patcher = patch("accounts.google_auth.get_google_client", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def google_login(self):
        response = self.client.get(reverse("accounts:google_login"))
        self.assertRedirects(response, "https://accounts.google.com/o/oauth2/v2/auth", fetch_redirect_response=False)
        transaction = self.client.session[google_auth.TRANSACTION_KEY]
        self.provider.authorize_access_token.return_value = {
            "id_token": "provider-verified-token",
            "userinfo": {
                "sub": "journey-subject", "email": "journey@example.org",
                "email_verified": True, "name": "Anggota Journey",
                "nonce": transaction["nonce"],
            },
        }
        response = self.client.get(reverse("accounts:google_callback"), {
            "state": transaction["state"], "code": "journey-authorization-code",
        })
        self.assertRedirects(response, reverse("accounts:credentials"))

    def post_form(self, name, data):
        # GET the page first, as a browser does, to receive a current CSRF cookie.
        self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        return self.client.post(reverse(name), {
            **data, "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
        })

    def test_google_member_can_register_navigate_update_relogin_and_delete(self):
        self.assertContains(self.client.get(reverse("home")), "Google")
        self.google_login()
        user = get_user_model().objects.get(email="journey@example.org")
        self.assertFalse(user.has_usable_password())

        missing_csrf = self.client.post(reverse("accounts:credentials"), {
            "username": "journey-member", "password": self.password,
        })
        self.assertEqual(missing_csrf.status_code, 403)
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

        response = self.post_form("accounts:credentials", {
            "username": "journey-member", "password": self.password,
        })
        self.assertRedirects(response, reverse("accounts:complete_profile"))
        response = self.post_form("accounts:complete_profile", {
            "username": "journey-member", "domicile": "Depok",
            "preferred_categories": ["buku", "hobi"],
        })
        self.assertRedirects(response, reverse("core:landing"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.profile.preferred_categories, ["buku", "hobi"])

        item = Barter.objects.create(
            owner=user, title="Kamera perjalanan", thumbnail="https://example.org/item.jpg",
            description="Kamera layak pakai untuk bertukar.", item_year=2020,
            condition=80, item_location="Depok",
        )
        for name, kwargs in (
            ("core:landing", {}), ("keranjang:keranjang", {}), ("profile_post:show_posts", {}),
            ("barter_details:barter_detail", {"pk": item.pk}),
            ("core:terms", {}), ("core:privacy", {}),
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, kwargs=kwargs)).status_code, 200)

        response = self.post_form("accounts:profile", {
            "action": "profile", "username": "journey-updated", "full_name": "Anggota Baru",
            "email": "cannot-overwrite-google@example.org", "domicile": "Bandung",
            "birth_date": "2000-01-02", "social_contact": "@anggota",
            "preferred_categories": ["elektronik"], "preferred_categories_present": "1",
        })
        self.assertRedirects(response, reverse("accounts:profile") + "#profile")
        user.refresh_from_db()
        self.assertEqual(user.username, "journey-updated")
        self.assertEqual(user.email, "journey@example.org")
        self.assertEqual(user.profile.domicile, "Bandung")

        response = self.post_form("accounts:profile", {
            "action": "preferences", "language": "en", "profile_visibility": "on",
        })
        self.assertRedirects(response, reverse("accounts:profile") + "#settings")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.language, "en")
        self.assertFalse(user.profile.email_notifications)

        response = self.post_form("accounts:profile", {
            "action": "password", "old_password": self.password,
            "new_password1": self.new_password, "new_password2": self.new_password,
        })
        self.assertRedirects(response, reverse("accounts:profile") + "#settings")
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.new_password))

        response = self.client.post(reverse("accounts:logout"), {
            "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, reverse("accounts:auth"))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.google_login()
        response = self.post_form("accounts:credentials", {
            "username": "journey-updated", "password": self.new_password,
        })
        self.assertRedirects(response, reverse("accounts:complete_profile"))
        self.assertRedirects(
            self.post_form("accounts:complete_profile", {"action": "skip"}),
            reverse("core:landing"),
        )

        user_id = user.pk
        response = self.post_form("accounts:profile", {
            "action": "delete", "password": self.new_password, "confirm": "on",
        })
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertFalse(GoogleIdentity.objects.filter(user_id=user_id).exists())
        self.assertFalse(Barter.objects.filter(pk=item.pk).exists())
