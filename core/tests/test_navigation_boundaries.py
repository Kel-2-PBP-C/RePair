"""Boundary cases for navigation and public document return links."""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from core.context_processors import _is_active, navigation


class NavigationBoundaryTests(SimpleTestCase):
    def test_active_path_requires_a_complete_path_segment(self):
        for path, url, expected in (
            ("/posts/", "/posts/", True),
            ("/posts/12/", "/posts/", True),
            ("/posts-old/", "/posts/", False),
            ("/posts-extra/12/", "/posts/", False),
            ("/", "/", True),
            ("/posts/", "/", False),
            ("/posts/", None, False),
        ):
            with self.subTest(path=path, url=url):
                self.assertEqual(_is_active(SimpleNamespace(path=path), url), expected)

    def test_request_without_auth_or_resolver_metadata_uses_guest_navigation(self):
        request = RequestFactory().get("/unknown/")
        result = navigation(request)["navigation"]
        self.assertEqual(result["items"][-1]["url"], reverse("accounts:auth"))
        self.assertFalse(any(item["active"] for item in result["items"]))

    @override_settings(ROOT_URLCONF="core.tests.urls_integrated", NAVBAR_CART_URL_NAME="custom_post_list")
    def test_cart_route_can_be_configured_by_an_integrated_module(self):
        request = RequestFactory().get("/my-posts/")
        request.user = AnonymousUser()
        result = navigation(request)["navigation"]
        self.assertEqual(result["items"][1]["url"], "/my-posts/")
        self.assertTrue(result["items"][1]["active"])

    def test_authentication_pages_do_not_mark_settings_active(self):
        for name in ("accounts:auth", "accounts:login", "accounts:register"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                if response.status_code == 302:
                    response = self.client.get(response.url)
                result = response.context["navigation"]
                self.assertFalse(result["account_active"])
                self.assertFalse(result["items"][-1]["active"])


@override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
class PolicyReturnLinkBoundaryTests(SimpleTestCase):
    def test_backslash_and_fragment_policy_loops_use_home(self):
        for target in ("/\\example.org/path", "/privacy/#privacy-rights", "/terms/#terms", "relative-path", ""):
            with self.subTest(target=target):
                response = self.client.get(reverse("core:privacy"), {"next": target})
                self.assertEqual(response.context["close_url"], reverse("home"))

    def test_application_query_and_fragment_are_preserved_in_close_link(self):
        target = "/accounts/profile/?tab=privacy#settings"
        for name in ("core:terms", "core:privacy"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {"next": target}, secure=True)
                self.assertEqual(response.context["close_url"], target)

    def test_return_link_markup_is_escaped_in_rendered_template(self):
        response = self.client.get(reverse("core:terms"), {"next": '/landing/?q=" onmouseover="alert(1)'})
        self.assertNotContains(response, 'href="/landing/?q=" onmouseover="')
        self.assertContains(response, "&quot;")
