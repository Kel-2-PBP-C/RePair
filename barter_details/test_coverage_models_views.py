from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from profile_post.models import BarterOffer
from .forms import BidForm
from .models import Barter, Bid


def valid_bid_data(**overrides):
    data = {
        'replacement_type': Bid.ReplacementType.GOODS,
        'replacement_item': 'Kipas Angin',
        'replacement_description': 'Masih berfungsi',
        'replacement_thumbnail': '',
        'replacement_location': 'Depok',
        'replacement_location_code': '32.76',
        'replacement_category': 'buku',
        'condition': Bid.ConditionChoices.GOOD,
    }
    data.update(overrides)
    return data


class BarterModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='model-owner',
            password='test-password',
        )
        self.bidder = user_model.objects.create_user(
            username='model-bidder',
            password='test-password',
        )
        self.barter = Barter.objects.create(
            owner=self.owner,
            title='Radio Tua',
            description='Radio yang masih menyala',
            condition=Barter.ConditionChoices.GOOD,
            item_location='Bogor',
            item_replacement='Buku',
        )

    def test_legacy_kwargs_map_to_new_fields_and_mark_profile_post(self):
        barter = Barter.objects.create(
            user=self.owner,
            title='Kamera',
            description='Kamera analog',
            image_url='https://example.com/kamera.jpg',
            location='Depok',
            preferred_barter='Lensa',
        )

        barter.refresh_from_db()
        self.assertEqual(barter.owner, self.owner)
        self.assertEqual(barter.thumbnail, 'https://example.com/kamera.jpg')
        self.assertEqual(barter.item_location, 'Depok')
        self.assertEqual(barter.item_replacement, 'Lensa')
        self.assertTrue(barter.is_profile_post)

    def test_legacy_kwargs_do_not_override_explicit_profile_post_flag(self):
        barter = Barter(
            user=self.owner,
            title='Meja',
            description='Meja kayu',
            location='Bekasi',
            is_profile_post=False,
        )

        self.assertFalse(barter.is_profile_post)

    def test_regular_kwargs_are_not_profile_posts(self):
        self.assertFalse(self.barter.is_profile_post)

    def test_legacy_property_getters(self):
        self.assertEqual(self.barter.user, self.owner)
        self.assertEqual(self.barter.image_url, self.barter.thumbnail)
        self.assertEqual(self.barter.location, 'Bogor')
        self.assertEqual(self.barter.preferred_barter, 'Buku')

    def test_legacy_property_setters(self):
        self.barter.user = self.bidder
        self.barter.image_url = 'https://example.com/baru.jpg'
        self.barter.location = 'Tangerang'
        self.barter.preferred_barter = 'Sepatu'
        self.barter.save()

        self.barter.refresh_from_db()
        self.assertEqual(self.barter.owner, self.bidder)
        self.assertEqual(self.barter.thumbnail, 'https://example.com/baru.jpg')
        self.assertEqual(self.barter.item_location, 'Tangerang')
        self.assertEqual(self.barter.item_replacement, 'Sepatu')

    def test_str_returns_title(self):
        self.assertEqual(str(self.barter), 'Radio Tua')

    def test_for_forum_only_returns_available_profile_posts(self):
        forum_post = Barter.objects.create(
            owner=self.owner,
            title='Forum post',
            description='Tampil di forum',
            item_location='Depok',
            is_profile_post=True,
        )
        Barter.objects.create(
            owner=self.owner,
            title='Sedang negosiasi',
            description='Tidak tampil',
            item_location='Depok',
            is_profile_post=True,
            status=Barter.StatusChoices.NEGOTIATING,
        )

        self.assertEqual(list(Barter.objects.for_forum()), [forum_post])

    def test_bid_for_goods_saves_and_str_uses_target(self):
        bid = Bid.objects.create(
            target=self.barter,
            bidder=self.bidder,
            replacement_item='Jam Tangan',
            replacement_description='Jam tangan analog',
            condition=Bid.ConditionChoices.NEW,
        )

        self.assertEqual(bid.status, Bid.Status.PENDING)
        self.assertEqual(str(bid), 'Radio Tua')

    def test_bid_for_goods_requires_condition(self):
        with self.assertRaises(ValidationError) as context:
            Bid.objects.create(
                target=self.barter,
                bidder=self.bidder,
                replacement_item='Jam Tangan',
                replacement_description='Jam tangan analog',
            )

        self.assertIn('condition', context.exception.message_dict)
        self.assertFalse(Bid.objects.exists())

    def test_bid_cannot_target_own_item(self):
        with self.assertRaises(ValidationError) as context:
            Bid.objects.create(
                target=self.barter,
                bidder=self.owner,
                replacement_item='Jam Tangan',
                replacement_description='Jam tangan analog',
                condition=Bid.ConditionChoices.NEW,
            )

        self.assertIn('Tidak bisa menawar barang sendiri.', context.exception.messages)
        self.assertFalse(Bid.objects.exists())

    def test_service_bid_clears_goods_only_fields(self):
        bid = Bid.objects.create(
            target=self.barter,
            bidder=self.bidder,
            replacement_type=Bid.ReplacementType.SERVICE,
            replacement_item='Jasa servis',
            replacement_description='Servis elektronik',
            replacement_thumbnail='https://example.com/servis.jpg',
            replacement_location='Depok',
            replacement_location_code='32.76',
            replacement_category='buku',
            item_year=2020,
            condition=Bid.ConditionChoices.GOOD,
            condition_percentage=50,
        )

        bid.refresh_from_db()
        self.assertEqual(bid.replacement_thumbnail, '')
        self.assertIsNone(bid.item_year)
        self.assertEqual(bid.condition, '')
        self.assertIsNone(bid.condition_percentage)
        self.assertEqual(bid.replacement_location, '')
        self.assertEqual(bid.replacement_location_code, '')
        self.assertEqual(bid.replacement_category, '')


class BidFormTests(TestCase):
    def test_location_without_region_code_is_rejected(self):
        form = BidForm(data=valid_bid_data(replacement_location_code=''))

        self.assertFalse(form.is_valid())
        self.assertIn('Pilih wilayah dari daftar.', form.errors['replacement_location'])

    def test_valid_data_is_accepted_and_defaults_to_goods(self):
        self.assertEqual(
            BidForm().initial['replacement_type'],
            Bid.ReplacementType.GOODS,
        )
        self.assertTrue(BidForm(data=valid_bid_data()).is_valid())


class BarterViewCoverageTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='view-owner',
            password='test-password',
        )
        self.viewer = user_model.objects.create_user(
            username='view-viewer',
            password='test-password',
        )
        Profile.objects.create(user=self.viewer, social_contact='@viewer')
        self.barter = Barter.objects.create(
            owner=self.owner,
            title='Gitar Akustik',
            description='Gitar dengan senar baru',
            condition=Barter.ConditionChoices.GOOD,
            item_location='Depok',
        )
        self.bid_url = reverse('barter_details:submit_bid_ajax', args=[self.barter.pk])
        self.delete_url = reverse('barter_details:delete_ajax', args=[self.barter.pk])

    def test_detail_returns_404_for_unknown_barter(self):
        response = self.client.get(
            reverse(
                'barter_details:barter_detail',
                args=['00000000-0000-0000-0000-000000000000'],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_lists_other_available_items_of_owner(self):
        other = Barter.objects.create(
            owner=self.owner,
            title='Biola',
            description='Biola kecil',
            item_location='Depok',
        )
        Barter.objects.create(
            owner=self.owner,
            title='Drum',
            description='Sudah dibarter',
            item_location='Depok',
            status=Barter.StatusChoices.BARTERED,
        )

        response = self.client.get(
            reverse('barter_details:barter_detail', args=[self.barter.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['other_items']), [other])

    def test_bid_requires_login(self):
        response = self.client.post(self.bid_url, valid_bid_data())

        self.assertEqual(response.status_code, 401)
        self.assertFalse(BarterOffer.objects.exists())

    def test_bid_rejects_get(self):
        self.client.force_login(self.viewer)

        response = self.client.get(self.bid_url)

        self.assertEqual(response.status_code, 405)

    def test_owner_cannot_bid_on_own_item(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.bid_url, valid_bid_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(BarterOffer.objects.exists())

    def test_bid_rejected_when_item_not_available(self):
        self.barter.status = Barter.StatusChoices.NEGOTIATING
        self.barter.save()
        self.client.force_login(self.viewer)

        response = self.client.post(self.bid_url, valid_bid_data())

        self.assertEqual(response.status_code, 400)
        self.assertIn('message', response.json())
        self.assertFalse(BarterOffer.objects.exists())

    def test_invalid_bid_returns_form_errors(self):
        self.client.force_login(self.viewer)

        response = self.client.post(
            self.bid_url,
            valid_bid_data(replacement_item='', replacement_location_code=''),
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertIn('replacement_item', errors)
        self.assertIn('replacement_location', errors)
        self.assertFalse(BarterOffer.objects.exists())

    def test_bid_on_existing_profile_post_keeps_flag_and_stores_contact(self):
        self.barter.is_profile_post = True
        self.barter.save()
        self.client.force_login(self.viewer)

        response = self.client.post(self.bid_url, valid_bid_data())

        self.assertEqual(response.status_code, 201)
        offer = BarterOffer.objects.get()
        self.assertEqual(offer.offerer_contact, '@viewer')
        self.barter.refresh_from_db()
        self.assertTrue(self.barter.is_profile_post)

    def test_delete_requires_login(self):
        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.client.force_login(self.viewer)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())

    def test_owner_can_delete(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], reverse('add_items:create'))
        self.assertFalse(Barter.objects.filter(pk=self.barter.pk).exists())

    def test_delete_rejects_get(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())
