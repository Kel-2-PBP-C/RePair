from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class MainPageIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="main-page-member")

    def test_both_landing_names_require_login(self):
        for name in ("core:landing", "main_page:show_main"):
            with self.subTest(route=name):
                self.assertRedirects(
                    self.client.get(reverse(name)),
                    f"{reverse('accounts:auth')}?next=/landing/",
                    fetch_redirect_response=False,
                )

    def test_signed_in_home_opens_main_page_with_integrated_navigation(self):
        self.client.force_login(self.user)
        for name in ("core:landing", "main_page:show_main"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertTemplateUsed(response, "main_page.html")
                self.assertContains(response, "Temukan Barang yang Kamu Butuhkan")
                for target in ("keranjang", "profile_post:show_profile", "accounts:profile"):
                    self.assertContains(response, f'href="{reverse(target)}"')
