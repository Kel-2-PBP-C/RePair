from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from core.context_processors import navigation
from core.views import landing


@override_settings(ROOT_URLCONF="core.tests.urls_shared", REQUIRE_LOGIN_FOR_LANDING=False)
class SharedNavigationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, path="/landing/", authenticated=False):
        request = self.factory.get(path)
        request.user = (
            SimpleNamespace(is_authenticated=True, username="noe", get_short_name=lambda: "Noe")
            if authenticated
            else AnonymousUser()
        )
        request.resolver_match = resolve(path)
        return request

    def test_missing_optional_apps_do_not_break_navigation(self):
        nav = navigation(self.request())["navigation"]
        self.assertEqual(nav["home_url"], "/landing/")
        self.assertTrue(nav["items"][0]["active"])
        self.assertIsNone(nav["items"][1]["url"])
        self.assertIsNone(nav["items"][2]["url"])
        self.assertIsNone(nav["profile_url"])
        self.assertIsNone(nav["login_url"])
        self.assertIsNone(nav["logout_url"])

    def test_shared_branch_renders_for_guests_without_accounts(self):
        response = landing(self.request())
        self.assertContains(response, "Beranda sedang disiapkan")
        self.assertContains(response, 'aria-disabled="true"', count=2)
        self.assertNotContains(response, "/accounts/")

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated")
    def test_registered_routes_replace_disabled_links(self):
        request = self.request("/keranjang/")
        nav = navigation(request)["navigation"]
        self.assertEqual(nav["items"][1]["url"], "/keranjang/")
        self.assertTrue(nav["items"][1]["active"])
        self.assertFalse(nav["items"][0]["active"])
        self.assertEqual(nav["items"][2]["url"], "/posts/")
        self.assertEqual(nav["login_url"], "/accounts/auth/")

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated")
    def test_guest_is_offered_authentication(self):
        response = landing(self.request())
        self.assertContains(response, 'href="/accounts/auth/"')
        self.assertNotContains(response, 'action="/accounts/logout/"')

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated")
    def test_signed_in_navigation_has_profile_and_csrf_protected_logout(self):
        response = landing(self.request(authenticated=True))
        self.assertContains(response, "Selamat datang, Noe.")
        self.assertContains(response, "Profil &amp; Pengaturan")
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated")
    def test_settings_uses_same_active_profile_group(self):
        nav = navigation(self.request("/accounts/settings/"))["navigation"]
        self.assertTrue(nav["account_active"])
        self.assertEqual(nav["profile_url"], "/accounts/profile/")

    @override_settings(
        ROOT_URLCONF="core.tests.urls_integrated",
        REQUIRE_LOGIN_FOR_LANDING=True,
        LOGIN_URL="accounts:auth",
    )
    def test_landing_requires_auth_only_when_integration_enables_it(self):
        response = landing(self.request())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/auth/?next=/landing/")
        self.assertEqual(landing(self.request(authenticated=True)).status_code, 200)

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated", NAVBAR_POSTS_URL_NAME="custom_post_list")
    def test_post_module_can_supply_its_actual_route_name(self):
        nav = navigation(self.request())["navigation"]
        self.assertEqual(nav["items"][2]["url"], "/my-posts/")
