from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from barter_details.models import Barter
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


class MainPageBarterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="main-page-owner")
        for condition, status in (
            (Barter.ConditionChoices.NEW, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.GOOD, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.REPAIR, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.NEW, Barter.StatusChoices.NEGOTIATING),
            (Barter.ConditionChoices.GOOD, Barter.StatusChoices.BARTERED),
        ):
            Barter.objects.create(
                owner=cls.owner,
                title=f"{condition} {status}",
                description="Listing for main page filter test",
                condition=condition,
                status=status,
                item_location="Depok",
            )

    def get_main_page(self, query_string=""):
        request = RequestFactory().get(f"/landing/{query_string}")
        request.user = self.owner
        return show_main(request)

    def test_only_available_items_are_displayed(self):
        response = self.get_main_page()

        self.assertContains(response, "NEW AVAILABLE")
        self.assertContains(response, "GOOD AVAILABLE")
        self.assertContains(response, "REPAIR AVAILABLE")
        self.assertNotContains(response, "NEW NEGOTIATING")
        self.assertNotContains(response, "GOOD BARTERED")

    def test_condition_filter_uses_item_condition_choices(self):
        for condition in Barter.ConditionChoices.values:
            with self.subTest(condition=condition):
                response = self.get_main_page(f"?kondisi={condition}")
                self.assertContains(response, f"{condition} AVAILABLE")
                for other_condition in Barter.ConditionChoices.values:
                    if other_condition != condition:
                        self.assertNotContains(response, f"{other_condition} AVAILABLE")
                self.assertNotContains(response, "NEGOTIATING")
                self.assertNotContains(response, "BARTERED")

    def test_add_item_link_opens_the_profile_post_creation_form(self):
        response = self.get_main_page()

        self.assertContains(
            response,
            f'href="{reverse("profile_post:show_posts")}?create=1"',
        )
        self.client.force_login(self.owner)
        profile_posts_response = self.client.get(
            f'{reverse("profile_post:show_posts")}?create=1'
        )
        self.assertEqual(profile_posts_response.status_code, 200)
        self.assertContains(
            profile_posts_response,
            "new URLSearchParams(window.location.search).get('create') === '1'",
        )
