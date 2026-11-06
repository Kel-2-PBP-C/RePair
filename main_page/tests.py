from io import StringIO
from unittest.mock import Mock, patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import resolve, reverse

from barter_details.models import Barter
from keranjang.models import CartItem
from .views import show_main


class MainPageIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="main-page-member")

    def test_both_landing_names_resolve_to_the_catalog_and_require_login(self):
        for name in ("core:landing", "main_page:show_main"):
            with self.subTest(route=name):
                url = reverse(name)
                self.assertEqual(url, "/landing/")
                self.assertEqual(resolve(url).func, show_main)
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('accounts:auth')}?next=/landing/",
                    fetch_redirect_response=False,
                )

    def test_anonymous_redirect_preserves_catalog_search(self):
        self.assertRedirects(
            self.client.get(reverse("main_page:show_main"), {"search": "kamera"}),
            f"{reverse('accounts:auth')}?next=/landing/%3Fsearch%3Dkamera",
            fetch_redirect_response=False,
        )

    def test_signed_in_home_renders_catalog_with_integrated_navigation(self):
        self.client.force_login(self.user)
        for name in ("core:landing", "main_page:show_main"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertTemplateUsed(response, "main_page/main_page.html")
                self.assertTemplateUsed(response, "base.html")
                self.assertContains(response, "Rekomendasi Untuk Kamu")
                self.assertContains(response, "Cari Barang yang Kamu Inginkan...")
                self.assertContains(response, "Belum ada barang yang diposting.")
                self.assertNotContains(response, "semangat ngerjainnya guys-noe")
                for target in ("keranjang:keranjang", "profile_post:show_posts", "accounts:profile"):
                    self.assertContains(response, f'href="{reverse(target)}"')
                active_items = [item["key"] for item in response.context["navigation"]["items"] if item["active"]]
                self.assertEqual(active_items, ["home"])

    def test_catalog_rejects_member_mutation_requests(self):
        self.client.force_login(self.user)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse("main_page:show_main"))
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET")


class MainPageBarterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(username="main-page-viewer")
        cls.owner = get_user_model().objects.create_user(username="main-page-owner")
        cls.items = {}
        for condition, status in (
            (Barter.ConditionChoices.NEW, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.GOOD, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.REPAIR, Barter.StatusChoices.AVAILABLE),
            (Barter.ConditionChoices.NEW, Barter.StatusChoices.NEGOTIATING),
            (Barter.ConditionChoices.GOOD, Barter.StatusChoices.BARTERED),
        ):
            item = Barter.objects.create(
                owner=cls.owner,
                title=f"{condition} {status}",
                description="Listing for main page filter test",
                condition=condition,
                status=status,
                item_location="Depok",
            )
            cls.items[(condition, status)] = item
        cls.own_item = Barter.objects.create(
            owner=cls.viewer, title="Barang saya sendiri", description="Barang pemilik sesi saat ini.",
            condition=Barter.ConditionChoices.GOOD, item_location="Bogor",
        )

    def setUp(self):
        self.client.force_login(self.viewer)

    def get_main_page(self, **query):
        return self.client.get(reverse("main_page:show_main"), query)

    def test_only_available_items_from_other_owners_are_displayed(self):
        response = self.get_main_page()
        expected = {
            item.pk for (condition, status), item in self.items.items()
            if status == Barter.StatusChoices.AVAILABLE
        }
        self.assertEqual({item.pk for item in response.context["items"]}, expected)
        self.assertContains(response, 'class="barang-card"', count=3)
        for title in ("NEW AVAILABLE", "GOOD AVAILABLE", "REPAIR AVAILABLE"):
            self.assertContains(response, title)
        for title in ("NEW NEGOTIATING", "GOOD BARTERED", self.own_item.title):
            self.assertNotContains(response, title)

    def test_condition_filter_uses_item_condition_choices(self):
        for condition in Barter.ConditionChoices.values:
            with self.subTest(condition=condition):
                response = self.get_main_page(kondisi=condition)
                self.assertEqual(list(response.context["items"]), [self.items[(condition, "AVAILABLE")]])
                self.assertContains(response, f"{condition} AVAILABLE")
                self.assertContains(response, 'class="barang-card"', count=1)
                self.assertEqual(response.context["kondisi"], condition)

    def test_unrecognized_condition_keeps_all_available_items(self):
        response = self.get_main_page(kondisi="not-a-condition")
        self.assertEqual(response.context["items"].count(), 3)
        self.assertContains(response, 'class="barang-card"', count=3)

    def test_search_is_case_insensitive_and_trims_surrounding_spaces(self):
        response = self.get_main_page(search="  good  ")
        self.assertEqual(response.context["search"], "good")
        self.assertEqual(list(response.context["items"]), [self.items[("GOOD", "AVAILABLE")]])
        self.assertContains(response, 'value="good"')
        self.assertNotContains(response, "GOOD BARTERED")

    def test_search_and_condition_filter_are_applied_together(self):
        response = self.get_main_page(search="available", kondisi="REPAIR")
        self.assertEqual(list(response.context["items"]), [self.items[("REPAIR", "AVAILABLE")]])
        self.assertContains(response, "Butuh Perbaikan")

    def test_no_search_match_displays_filtered_empty_state(self):
        response = self.get_main_page(search="barang-tidak-ada", kondisi="GOOD")
        self.assertFalse(response.context["items"].exists())
        self.assertContains(response, "Barang yang kamu cari tidak ditemukan.")
        self.assertNotContains(response, 'class="barang-card"')

    def test_own_items_cannot_be_revealed_by_search(self):
        response = self.get_main_page(search=self.own_item.title)
        self.assertFalse(response.context["items"].exists())
        self.assertContains(response, "Barang yang kamu cari tidak ditemukan.")

    def test_search_markup_is_escaped_in_the_input(self):
        response = self.get_main_page(search='<script>alert("unsafe")</script>')
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("unsafe")</script>')

    def test_add_item_link_opens_the_profile_post_creation_form(self):
        response = self.get_main_page()

        self.assertContains(
            response,
            f'href="{reverse("profile_post:show_posts")}?create=1"',
        )
        profile_posts_response = self.client.get(
            f'{reverse("profile_post:show_posts")}?create=1'
        )
        self.assertEqual(profile_posts_response.status_code, 200)
        self.assertContains(
            profile_posts_response,
            "new URLSearchParams(window.location.search).get('create') === '1'",
        )


class MainPageDummyJSONTests(TestCase):
    def test_imported_products_render_images_and_working_detail_and_cart_links_offline(self):
        products = [
            {
                "id": number,
                "title": f"Produk DummyJSON {number:02d}",
                "description": f"Produk contoh untuk menguji integrasi katalog nomor {number}.",
                "category": ("smartphones", "furniture", "mens-shirts", "sports-accessories")[number % 4],
                "thumbnail": f"https://cdn.dummyjson.com/product-images/{number}.webp",
            }
            for number in range(1, 51)
        ]
        response = Mock(status_code=200)
        response.json.return_value = {"products": products}
        viewer = get_user_model().objects.create_user(username="dataset-viewer")
        self.client.force_login(viewer)
        with patch("barter_details.management.commands.import_dummyjson.requests.get", return_value=response) as fetch:
            call_command("import_dummyjson", stdout=StringIO())
            self.assertEqual(fetch.call_count, 1)
            # Catalog requests must use persisted rows without refetching the API.
            fetch.side_effect = AssertionError("Browsing must not fetch DummyJSON again")
            page = self.client.get(reverse("core:landing"))
            self.assertContains(page, 'class="barang-card"', count=50)
            self.assertEqual(page.context["items"].count(), 50)
            self.assertFalse(get_user_model().objects.get(username="dataset_dummyjson").is_active)
            for product in products:
                identifier = uuid5(NAMESPACE_URL, f'https://dummyjson.com/products/{product["id"]}')
                with self.subTest(source_id=product["id"]):
                    self.assertContains(page, product["title"])
                    self.assertContains(page, f'src="{product["thumbnail"]}"')
                    self.assertContains(page, f'href="{reverse("barter_details:barter_detail", args=[identifier])}"')
                    self.assertContains(page, f'action="{reverse("keranjang:tambah_keranjang", args=[identifier])}"')

            first_id = uuid5(NAMESPACE_URL, "https://dummyjson.com/products/1")
            detail = self.client.get(reverse("barter_details:barter_detail", args=[first_id]))
            self.assertContains(detail, products[0]["title"])
            self.assertContains(detail, products[0]["thumbnail"])
            filtered = self.client.get(reverse("main_page:show_main"), {
                "search": "produk dummyjson 01", "kondisi": "GOOD",
            })
            self.assertContains(filtered, 'class="barang-card"', count=1)
            self.assertContains(filtered, products[0]["title"])
            added = self.client.post(reverse("keranjang:tambah_keranjang", args=[first_id]))
            self.assertRedirects(added, reverse("main_page:show_main"))
            self.assertTrue(CartItem.objects.filter(user=viewer, barter_id=first_id).exists())
            self.assertContains(self.client.get(reverse("keranjang:keranjang")), products[0]["title"])
            self.assertEqual(fetch.call_count, 1)
