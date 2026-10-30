from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from barter_details.models import Barter


class MainPageTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testuser",
            password="TestPass123!"
        )

        cls.other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="TestPass123!"
        )

        cls.barang = Barter.objects.create(
            owner=cls.user,
            title="Laptop Lenovo",
            description="Laptop bekas masih bagus",
            thumbnail="https://example.com/laptop.jpg",
            condition="GOOD",
            condition_percentage=80,
            item_year=2022,
            item_replacement="Handphone",
            item_location="Depok"
        )

    def test_homepage_bisa_dibuka(self):
        response = self.client.get(reverse("main_page:show_main"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "main_page/main_page.html"
        )

    def test_barang_muncul_di_homepage(self):
        response = self.client.get(reverse("main_page:show_main"))

        self.assertContains(response, "Laptop Lenovo")
        self.assertContains(response, "Depok")
        self.assertContains(response, "80%")

    def test_pencarian_barang(self):
        response = self.client.get(
            reverse("main_page:show_main"),
            {"search": "Lenovo"}
        )

        self.assertContains(response, "Laptop Lenovo")

    def test_pencarian_barang_tidak_ditemukan(self):
        response = self.client.get(
            reverse("main_page:show_main"),
            {"search": "Samsung"}
        )

        self.assertNotContains(response, "Laptop Lenovo")

    def test_filter_kondisi(self):
        response = self.client.get(
            reverse("main_page:show_main"),
            {"kondisi": "GOOD"}
        )

        self.assertContains(response, "Laptop Lenovo")

        response = self.client.get(
            reverse("main_page:show_main"),
            {"kondisi": "NEW"}
        )

        self.assertNotContains(response, "Laptop Lenovo")

    def test_pemilik_bisa_melihat_tombol_edit_hapus(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("main_page:show_main"))

        self.assertContains(response, "Edit Barang")
        self.assertContains(response, "Hapus Barang")

    def test_pengguna_lain_tidak_melihat_tombol_edit_hapus(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("main_page:show_main"))

        self.assertNotContains(response, "Edit Barang")
        self.assertNotContains(response, "Hapus Barang")