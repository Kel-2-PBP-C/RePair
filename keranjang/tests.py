from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from barter_details.models import Barter
from profile_post.models import BarterOffer, BarterReview
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
        self.assertContains(response, '(80%)')

    def test_negotiating_cart_item_shows_profile_status_color_and_owner_contact(self):
        self.barter.is_profile_post = True
        self.barter.status = Barter.StatusChoices.NEGOTIATING
        self.barter.save(update_fields=['is_profile_post', 'status'])
        Profile.objects.create(
            user=self.barter_owner,
            social_contact='@owner-contact',
        )
        BarterOffer.objects.create(
            post=self.barter,
            offerer=self.user,
            offered_item_title='Buku',
            offered_item_description='Kondisi bagus',
            offerer_contact='@bidder-contact',
            is_selected=True,
        )
        CartItem.objects.create(user=self.user, barter=self.barter)

        response = self.client.get(reverse('keranjang:keranjang'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cart-status-negotiating')
        self.assertContains(response, 'Dalam Negosiasi')
        self.assertContains(response, 'barter-owner')
        self.assertContains(response, '@owner-contact')

    def test_completed_selected_bidder_can_review_owner_and_review_appears_in_profile_posts(self):
        self.barter.is_profile_post = True
        self.barter.status = Barter.StatusChoices.BARTERED
        self.barter.save(update_fields=['is_profile_post', 'status'])
        BarterOffer.objects.create(
            post=self.barter,
            offerer=self.user,
            offered_item_title='Buku',
            offered_item_description='Kondisi bagus',
            offerer_contact='@bidder-contact',
            is_selected=True,
        )
        CartItem.objects.create(user=self.user, barter=self.barter)

        cart_response = self.client.get(reverse('keranjang:keranjang'))
        self.assertContains(cart_response, 'cart-status-bartered')
        self.assertContains(cart_response, 'Sudah Dibarter')
        self.assertContains(
            cart_response,
            reverse('profile_post:submit_bidder_review', args=[self.barter.pk]),
        )

        review_response = self.client.post(
            reverse('profile_post:submit_bidder_review', args=[self.barter.pk]),
            {'rating': '5', 'comment': 'Barter berjalan lancar.'},
        )

        self.assertRedirects(review_response, reverse('keranjang:keranjang'))
        review = BarterReview.objects.get(post=self.barter)
        self.assertEqual(review.role, BarterReview.RoleChoices.OFFERER_TO_OWNER)
        self.assertEqual(review.reviewer, self.user)
        self.assertEqual(review.reviewee, self.barter_owner)

        self.client.force_login(self.barter_owner)
        posts_response = self.client.get(reverse('profile_post:get_posts_json'))
        post_data = next(
            post for post in posts_response.json()['posts']
            if post['id'] == str(self.barter.pk)
        )
        self.assertEqual(post_data['status_code'], Barter.StatusChoices.BARTERED)
        self.assertEqual(post_data['reviews']['to_owner']['rating'], 5)
        self.assertContains(
            self.client.get(reverse('profile_post:show_posts')),
            'Ulasan penawar untuk Anda',
        )
