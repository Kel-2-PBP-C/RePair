from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from .models import Barter, Bid


class BarterDetailTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='item-owner',
            first_name='Owner',
            last_name='Person',
            password='test-password',
        )
        self.viewer = user_model.objects.create_user(
            username='viewer-user',
            first_name='Viewer',
            last_name='Person',
            password='test-password',
        )
        Profile.objects.create(user=self.owner, social_contact='@owner-contact')
        Profile.objects.create(user=self.viewer, social_contact='@viewer-contact')
        self.barter = Barter.objects.create(
            owner=self.owner,
            title='A repairable lamp',
            description='A' * 600,
            item_year=None,
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=None,
            item_location='',
            item_replacement='',
        )

    def test_details_use_the_listing_owner_profile(self):
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse('barter_details:barter_detail', args=[self.barter.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile_initials'], 'OP')
        self.assertEqual(response.context['preferred_contact'], '@owner-contact')
        self.assertNotContains(response, '@viewer-contact')

    def test_optional_details_and_shipping_method_are_not_rendered_as_none(self):
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse('barter_details:barter_detail', args=[self.barter.pk])
        )

        self.assertNotContains(response, 'None')
        self.assertNotContains(response, 'COD / Temu Langsung')
        self.assertContains(response, 'A' * 600)
        self.assertContains(response, 'class="item-description"')

    def test_owner_does_not_see_the_details_action_footer(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse('barter_details:barter_detail', args=[self.barter.pk])
        )

        self.assertNotContains(response, 'class="site-footer"')
        self.assertNotContains(response, 'id="bid-modal"')

    def test_offer_form_uses_listing_fields_without_requested_item_field(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse('barter_details:barter_detail', args=[self.barter.pk])
        )

        self.assertContains(response, 'name="replacement_location"')
        self.assertContains(response, 'name="replacement_category"')
        self.assertContains(response, 'value="goods"')
        self.assertNotContains(response, 'name="item_replacement"')
        self.assertNotContains(response, 'name="condition_percentage"')

    def test_offer_submission_accepts_one_character_description_and_profile_fields(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse('barter_details:submit_bid_ajax', args=[self.barter.pk]),
            {
                'replacement_type': Bid.ReplacementType.GOODS,
                'replacement_item': 'A',
                'replacement_description': 'B',
                'replacement_thumbnail': '',
                'replacement_location': 'Depok',
                'replacement_location_code': '32.76',
                'replacement_category': 'buku',
                'condition': Bid.ConditionChoices.GOOD,
            },
        )

        self.assertEqual(response.status_code, 201, response.content)
        bid = Bid.objects.get()
        self.assertEqual(bid.replacement_item, 'A')
        self.assertEqual(bid.replacement_location, 'Depok')
        self.assertEqual(bid.replacement_location_code, '32.76')
        self.assertEqual(bid.replacement_category, 'buku')
        self.assertIsNone(bid.item_year)
        self.assertIsNone(bid.condition_percentage)