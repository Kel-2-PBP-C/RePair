from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from barter_details.models import Barter
from .models import CartItem


class CartActionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cart-user',
            password='test-password',
        )
        self.barter_owner = get_user_model().objects.create_user(
            username='barter-owner',
            password='test-password',
        )
        self.barter = Barter.objects.create(
            owner=self.barter_owner,
            title='A repairable lamp',
            description='A lamp available for barter.',
            item_year=2022,
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=80,
            shipping_method=Barter.ShippingChoices.COD,
            item_location='Depok',
        )
        self.client.force_login(self.user)

    def test_add_to_cart_creates_one_cart_item(self):
        url = reverse('keranjang:tambah_keranjang', args=[self.barter.pk])

        response = self.client.post(url)
        duplicate_response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(duplicate_response.status_code, 302)
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CartItem.objects.get(user=self.user).barter, self.barter)

    def test_favorite_and_delete_use_the_cart_item_integer_id(self):
        cart_item = CartItem.objects.create(user=self.user, barter=self.barter)
        favorite_url = reverse(
            'keranjang:toggle_favorit',
            args=[cart_item.pk],
        )
        delete_url = reverse('keranjang:hapus_keranjang', args=[cart_item.pk])

        favorite_response = self.client.post(favorite_url)
        cart_item.refresh_from_db()
        self.assertEqual(favorite_response.status_code, 302)
        self.assertTrue(cart_item.is_favorite)

        delete_response = self.client.post(delete_url)
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(CartItem.objects.filter(pk=cart_item.pk).exists())

    def test_cart_displays_the_numeric_condition_percentage(self):
        CartItem.objects.create(user=self.user, barter=self.barter)

        response = self.client.get(reverse('keranjang:keranjang'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kondisi: 80%')
