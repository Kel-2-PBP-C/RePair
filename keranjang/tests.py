
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from barter_details.models import Barter
from .models import CartItem


User = get_user_model()


class KeranjangTest(TestCase):

    def setUp(self):
        # Membuat dua pengguna untuk pengujian.
        self.user = User.objects.create_user(
            username="user_test",
            password="password123"
        )

        self.other_user = User.objects.create_user(
            username="other_test",
            password="password123"
        )

        # Login sebagai pengguna pertama.
        self.client.login(
            username="user_test",
            password="password123"
        )

        # Membuat barang milik pengguna lain.
        self.barter = Barter.objects.create(
            owner=self.other_user,
            thumbnail="https://example.com/image.jpg",
            title="Tas Testing",
            description="Barang untuk pengujian",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=90,
            item_year=2024,
            item_replacement="Buku",
            item_location="Jakarta",
        )

    # =====================================
    # READ: MELIHAT KERANJANG
    # =====================================

    def test_akses_keranjang(self):
        response = self.client.get(
            reverse("keranjang:keranjang")
        )

        self.assertEqual(response.status_code, 200)

    def test_keranjang_hanya_menampilkan_barang_sendiri(self):
        # Barang milik user pertama.
        CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        # Membuat barang lain untuk pengguna kedua.
        other_barter = Barter.objects.create(
            owner=self.user,
            thumbnail="https://example.com/other.jpg",
            title="Barang Pengguna Lain",
            description="Barang untuk pengguna lain",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=85,
            item_year=2024,
            item_replacement="Buku",
            item_location="Jakarta",
        )

        CartItem.objects.create(
            user=self.other_user,
            barter=other_barter
        )

        response = self.client.get(
            reverse("keranjang:keranjang")
        )

        self.assertContains(response, "Tas Testing")
        self.assertNotContains(response, "Barang Pengguna Lain")

    # =====================================
    # CREATE: MENAMBAHKAN BARANG
    # =====================================

    def test_tambah_barang(self):
        response = self.client.post(
            reverse(
                "keranjang:tambah_keranjang",
                args=[self.barter.id]
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            CartItem.objects.filter(
                user=self.user,
                barter=self.barter
            ).exists()
        )

    def test_barang_duplikat(self):
        CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        self.client.post(
            reverse(
                "keranjang:tambah_keranjang",
                args=[self.barter.id]
            )
        )

        self.assertEqual(
            CartItem.objects.filter(
                user=self.user,
                barter=self.barter
            ).count(),
            1
        )

    def test_tidak_bisa_tambah_barang_sendiri(self):
        own_barter = Barter.objects.create(
            owner=self.user,
            thumbnail="https://example.com/own.jpg",
            title="Barang Sendiri",
            description="Barang milik sendiri",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=90,
            item_year=2024,
            item_replacement="Buku",
            item_location="Jakarta",
        )

        self.client.post(
            reverse(
                "keranjang:tambah_keranjang",
                args=[own_barter.id]
            )
        )

        self.assertFalse(
            CartItem.objects.filter(
                user=self.user,
                barter=own_barter
            ).exists()
        )

    # =====================================
    # SEARCH: PENCARIAN BARANG
    # =====================================

    def test_pencarian_barang(self):
        CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        response = self.client.get(
            reverse("keranjang:keranjang"),
            {"q": "Tas Testing"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tas Testing")

    def test_pencarian_barang_tidak_ditemukan(self):
        CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        response = self.client.get(
            reverse("keranjang:keranjang"),
            {"q": "Barang Tidak Ada"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Tas Testing")

    # =====================================
    # UPDATE: FITUR FAVORIT
    # =====================================

    def test_tandai_favorit(self):
        item = CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        response = self.client.post(
            reverse(
                "keranjang:toggle_favorit",
                args=[item.id]
            )
        )

        item.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(item.is_favorite)

    def test_batalkan_favorit(self):
        item = CartItem.objects.create(
            user=self.user,
            barter=self.barter,
            is_favorite=True
        )

        self.client.post(
            reverse(
                "keranjang:toggle_favorit",
                args=[item.id]
            )
        )

        item.refresh_from_db()

        self.assertFalse(item.is_favorite)

    def test_barang_favorit_di_atas(self):
        item_biasa = CartItem.objects.create(
            user=self.user,
            barter=self.barter,
            is_favorite=False
        )

        favorite_barter = Barter.objects.create(
            owner=self.other_user,
            thumbnail="https://example.com/favorite.jpg",
            title="Barang Favorit",
            description="Barang favorit testing",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=95,
            item_year=2024,
            item_replacement="Sepatu",
            item_location="Jakarta",
        )

        item_favorit = CartItem.objects.create(
            user=self.user,
            barter=favorite_barter,
            is_favorite=True
        )

        response = self.client.get(
            reverse("keranjang:keranjang")
        )

        cart_items = list(response.context["cart_items"])

        self.assertEqual(cart_items[0].id, item_favorit.id)
        self.assertEqual(cart_items[1].id, item_biasa.id)

    def test_tidak_bisa_mengubah_favorit_orang_lain(self):
        item = CartItem.objects.create(
            user=self.other_user,
            barter=self.barter
        )

        response = self.client.post(
            reverse(
                "keranjang:toggle_favorit",
                args=[item.id]
            )
        )

        item.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(item.is_favorite)

    # =====================================
    # DELETE: MENGHAPUS BARANG
    # =====================================

    def test_hapus_barang(self):
        item = CartItem.objects.create(
            user=self.user,
            barter=self.barter
        )

        response = self.client.post(
            reverse(
                "keranjang:hapus_keranjang",
                args=[item.id]
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            CartItem.objects.filter(id=item.id).exists()
        )

    def test_pengguna_tidak_bisa_menghapus_barang_orang_lain(self):
        item = CartItem.objects.create(
            user=self.other_user,
            barter=self.barter
        )

        response = self.client.post(
            reverse(
                "keranjang:hapus_keranjang",
                args=[item.id]
            )
        )

        self.assertEqual(response.status_code, 404)

        self.assertTrue(
            CartItem.objects.filter(id=item.id).exists()
        )

    # =====================================
    # SECURITY: LOGIN
    # =====================================

    def test_pengguna_belum_login(self):
        self.client.logout()

        response = self.client.get(
            reverse("keranjang:keranjang")
        )

        self.assertEqual(response.status_code, 302)
