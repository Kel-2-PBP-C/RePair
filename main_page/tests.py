from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .views import show_main


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

    def test_signed_in_home_is_plain_placeholder_with_integrated_navigation(self):
        self.client.force_login(self.user)
        for name in ("core:landing", "main_page:show_main"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertTemplateUsed(response, "core/landing.html")
                self.assertContains(response, "<p>semangat ngerjainnya guys-noe</p>", html=True)
                self.assertContains(response, '<header class="repair-navbar">')
                self.assertContains(response, '<nav class="repair-navbar-menu"')
                self.assertContains(response, '<footer class="site-footer shell">')
                self.assertNotContains(response, "Cari barang...")
                self.assertNotContains(response, "Rekomendasi Barang")
                self.assertNotContains(response, "Tambah ke Keranjang")
                self.assertNotContains(response, 'class="panel"')
                for target in ("keranjang", "profile_post:show_posts", "accounts:profile"):
                    self.assertContains(response, f'href="{reverse(target)}"')

    def test_main_page_view_keeps_the_same_placeholder(self):
        request = RequestFactory().get("/landing/")
        request.user = self.user
        response = show_main(request)
        self.assertContains(response, "<p>semangat ngerjainnya guys-noe</p>", html=True)
        self.assertNotContains(response, "Rekomendasi Barang")
