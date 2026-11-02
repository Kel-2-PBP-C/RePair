from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from barter_details.models import Barter
from .forms import FavoriteForm
from .models import CartItem


User = get_user_model()


class KeranjangCoverageTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="cart_cov_user",
            password="password123",
        )
        self.owner = User.objects.create_user(
            username="cart_cov_owner",
            password="password123",
        )
        self.client.force_login(self.user)

        self.barter_jakarta = Barter.objects.create(
            owner=self.owner,
            title="Sepeda Lipat",
            description="Sepeda untuk pengujian",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=75,
            item_year=2020,
            item_replacement="Helm",
            item_location="Jakarta Selatan",
        )
        self.barter_bandung = Barter.objects.create(
            owner=self.owner,
            title="Sepeda Gunung",
            description="Sepeda kedua untuk pengujian",
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=60,
            item_year=2019,
            item_replacement="Tas",
            item_location="Bandung",
        )
        self.item = CartItem.objects.create(
            user=self.user,
            barter=self.barter_jakarta,
        )
        self.item_bandung = CartItem.objects.create(
            user=self.user,
            barter=self.barter_bandung,
        )

    def favorite_url(self, item=None):
        return reverse(
            "keranjang:toggle_favorit",
            args=[(item or self.item).pk],
        )

    def message_texts(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    # =====================================
    # MODEL & FORM
    # =====================================

    def test_str_menampilkan_pengguna_dan_judul_barang(self):
        self.assertEqual(str(self.item), "cart_cov_user - Sepeda Lipat")

    def test_favorite_form_tidak_wajib_diisi(self):
        form = FavoriteForm(data={}, instance=self.item)

        self.assertFalse(form.fields["is_favorite"].required)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data["is_favorite"])

    def test_favorite_form_menyimpan_nilai_true(self):
        form = FavoriteForm(data={"is_favorite": "true"}, instance=self.item)

        self.assertTrue(form.is_valid())
        form.save()
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_favorite)

    # =====================================
    # READ: FILTER LOKASI
    # =====================================

    def test_filter_lokasi(self):
        response = self.client.get(
            reverse("keranjang:keranjang"),
            {"location": "  bandung "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["location_query"], "bandung")
        self.assertEqual(
            list(response.context["cart_items"]),
            [self.item_bandung],
        )

    def test_filter_pencarian_dan_lokasi_digabung(self):
        response = self.client.get(
            reverse("keranjang:keranjang"),
            {"q": "sepeda", "location": "jakarta"},
        )

        self.assertEqual(
            list(response.context["cart_items"]),
            [self.item],
        )

    def test_keranjang_hanya_menerima_get(self):
        response = self.client.post(reverse("keranjang:keranjang"))

        self.assertEqual(response.status_code, 405)

    # =====================================
    # UPDATE: FAVORIT LEWAT FORM
    # =====================================

    def test_favorit_dengan_nilai_form_true(self):
        response = self.client.post(
            self.favorite_url(),
            {"is_favorite": "true"},
        )

        self.assertRedirects(response, reverse("keranjang:keranjang"))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_favorite)
        self.assertIn(
            "Barang berhasil ditambahkan ke favorit.",
            self.message_texts(response),
        )

    def test_favorit_dengan_nilai_form_false_tidak_membalik_status(self):
        self.item.is_favorite = True
        self.item.save()

        response = self.client.post(
            self.favorite_url(),
            {"is_favorite": "false"},
        )

        self.assertRedirects(response, reverse("keranjang:keranjang"))
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_favorite)
        self.assertIn(
            "Barang dihapus dari favorit.",
            self.message_texts(response),
        )

    def test_favorit_nilai_form_bersifat_idempoten(self):
        # Mengirim "true" dua kali tetap menghasilkan favorit (tidak toggle).
        self.client.post(self.favorite_url(), {"is_favorite": "true"})
        self.client.post(self.favorite_url(), {"is_favorite": "true"})

        self.item.refresh_from_db()
        self.assertTrue(self.item.is_favorite)

    def test_favorit_ajax_dengan_nilai_form(self):
        response = self.client.post(
            self.favorite_url(),
            {"is_favorite": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "is_favorite": True,
                "message": "Barang berhasil ditambahkan ke favorit.",
            },
        )
        # Request AJAX tidak menambahkan flash message.
        self.assertEqual(self.message_texts(response), [])

    def test_favorit_ajax_toggle_tanpa_nilai(self):
        self.item.is_favorite = True
        self.item.save()

        response = self.client.post(
            self.favorite_url(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_favorite"])
        self.assertEqual(
            response.json()["message"],
            "Barang dihapus dari favorit.",
        )
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_favorite)

    def test_favorit_form_tidak_valid_ajax(self):
        with patch.object(FavoriteForm, "is_valid", return_value=False):
            response = self.client.post(
                self.favorite_url(),
                {"is_favorite": "true"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("errors", response.json())
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_favorite)

    def test_favorit_form_tidak_valid_request_biasa(self):
        with patch.object(FavoriteForm, "is_valid", return_value=False):
            response = self.client.post(
                self.favorite_url(),
                {"is_favorite": "true"},
            )

        self.assertRedirects(response, reverse("keranjang:keranjang"))
        self.assertIn(
            "Status favorit gagal diperbarui.",
            self.message_texts(response),
        )
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_favorite)

    def test_favorit_tidak_menerima_get(self):
        response = self.client.get(self.favorite_url())

        self.assertEqual(response.status_code, 405)

    # =====================================
    # CREATE / DELETE: PESAN & ERROR
    # =====================================

    def test_tambah_barang_tidak_ada_mengembalikan_404(self):
        response = self.client.post(
            reverse(
                "keranjang:tambah_keranjang",
                args=["00000000-0000-0000-0000-000000000000"],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_tambah_barang_baru_menampilkan_pesan_sukses(self):
        self.item.delete()

        response = self.client.post(
            reverse("keranjang:tambah_keranjang", args=[self.barter_jakarta.pk])
        )

        self.assertRedirects(
            response,
            reverse("main_page:show_main"),
            fetch_redirect_response=False,
        )
        self.assertIn(
            "Barang berhasil ditambahkan ke keranjang.",
            self.message_texts(response),
        )

    def test_hapus_barang_menampilkan_pesan(self):
        response = self.client.post(
            reverse("keranjang:hapus_keranjang", args=[self.item.pk])
        )

        self.assertRedirects(response, reverse("keranjang:keranjang"))
        self.assertIn(
            "Barang berhasil dihapus dari keranjang.",
            self.message_texts(response),
        )
        self.assertFalse(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_hapus_barang_tidak_menerima_get(self):
        response = self.client.get(
            reverse("keranjang:hapus_keranjang", args=[self.item.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_menghapus_barter_menghapus_item_keranjang(self):
        self.barter_jakarta.delete()

        self.assertFalse(CartItem.objects.filter(pk=self.item.pk).exists())
