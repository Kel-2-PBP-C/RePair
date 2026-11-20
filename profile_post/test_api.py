from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Profile
from barter_details.models import Barter
from profile_post.models import BarterOffer, BarterReview, Post


User = get_user_model()


class ProfilePostRestApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='post-owner', password='password')
        self.owner_profile = Profile.objects.create(
            user=self.owner,
            domicile='Kota Depok, Jawa Barat',
            domicile_code='3276',
        )
        self.other_user = User.objects.create_user(username='other-user', password='password')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def make_post(self, **kwargs):
        defaults = {
            'owner': self.owner,
            'is_profile_post': True,
            'title': 'A post',
            'description': 'A description',
            'item_location': 'Kota Depok, Jawa Barat',
            'category': 'buku',
        }
        defaults.update(kwargs)
        return Post.objects.create(**defaults)

    def test_api_urls_follow_the_readme_router_convention(self):
        self.assertEqual(reverse('profile_post_api:posts-list'), '/api/profile-post/posts/')

    def test_list_is_authenticated_owner_scoped_and_uses_standard_pagination(self):
        own_post = self.make_post(title='Mine')
        Post.objects.create(
            owner=self.other_user,
            is_profile_post=True,
            title='Not mine',
            description='Another description',
            item_location='Bogor',
            category='buku',
        )

        response = self.client.get(reverse('profile_post_api:posts-list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(own_post.pk))
        self.assertEqual(response.data['results'][0]['offers_count'], 0)

    def test_api_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('profile_post_api:posts-list'))

        self.assertEqual(response.status_code, 403)

    def test_api_accepts_the_existing_session_authentication(self):
        self.client.force_authenticate(user=None)
        self.client.login(username='post-owner', password='password')

        response = self.client.get(reverse('profile_post_api:posts-list'))

        self.assertEqual(response.status_code, 200)

    def test_create_uses_authenticated_owner_and_default_profile_region(self):
        response = self.client.post(
            reverse('profile_post_api:posts-list'),
            {
                'title': 'New post',
                'description': 'A useful item',
                'category': 'hobi',
                'condition': Barter.ConditionChoices.GOOD,
                'owner': self.other_user.pk,
                'status': Barter.StatusChoices.BARTERED,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        post = Post.objects.get(title='New post')
        self.assertEqual(post.owner, self.owner)
        self.assertTrue(post.is_profile_post)
        self.assertEqual(post.status, Barter.StatusChoices.AVAILABLE)
        self.assertEqual(post.location_code, '3276')
        self.assertEqual(post.item_location, 'Kota Depok, Jawa Barat')

    def test_create_requires_a_category(self):
        response = self.client.post(
            reverse('profile_post_api:posts-list'),
            {
                'title': 'New post',
                'description': 'A useful item',
                'condition': Barter.ConditionChoices.GOOD,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.data)

    def test_patch_and_delete_only_allow_available_posts(self):
        available = self.make_post()
        response = self.client.patch(
            reverse('profile_post_api:posts-detail', args=[available.pk]),
            {'title': 'Changed'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        available.refresh_from_db()
        self.assertEqual(available.title, 'Changed')

        negotiating = self.make_post(status=Barter.StatusChoices.NEGOTIATING)
        response = self.client.patch(
            reverse('profile_post_api:posts-detail', args=[negotiating.pk]),
            {'title': 'Not changed'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.delete(
            reverse('profile_post_api:posts-detail', args=[negotiating.pk])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Post.objects.filter(pk=negotiating.pk).exists())

        response = self.client.delete(
            reverse('profile_post_api:posts-detail', args=[available.pk])
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Post.objects.filter(pk=available.pk).exists())

    def test_nested_offers_include_offerers_domicile_without_exposing_email(self):
        post = self.make_post()
        offerer = User.objects.create_user(
            username='offerer',
            first_name='Offer',
            last_name='Person',
            email='private@example.test',
        )
        Profile.objects.create(user=offerer, domicile='Kota Bogor, Jawa Barat')
        offer = BarterOffer.objects.create(
            post=post,
            offerer=offerer,
            offered_item_title='Offered item',
            offered_item_description='An offer description',
            offerer_contact='private@example.test',
            is_selected=True,
        )

        response = self.client.get(
            reverse('profile_post_api:posts-offers', args=[post.pk])
        )
        post_response = self.client.get(
            reverse('profile_post_api:posts-detail', args=[post.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(post_response.data['offers_count'], 1)
        self.assertEqual(
            post_response.data['selected_offer']['offerer_contact'],
            'Kontak belum diatur',
        )
        self.assertEqual(
            post_response.data['reviews'],
            {'to_offerer': None, 'to_owner': None},
        )
        self.assertEqual(response.data['post_title'], post.title)
        self.assertEqual(response.data['offers'][0]['id'], offer.pk)
        self.assertEqual(response.data['offers'][0]['offerer_name'], 'Offer Person')
        self.assertEqual(
            response.data['offers'][0]['offerer_domicile'],
            'Kota Bogor, Jawa Barat',
        )
        self.assertEqual(
            response.data['offers'][0]['offerer_contact'],
            'Kontak belum diatur',
        )
        self.assertNotContains(response, 'private@example.test')

    def test_other_users_cannot_read_or_manage_a_post(self):
        post = self.make_post()
        self.client.force_authenticate(self.other_user)

        response = self.client.get(
            reverse('profile_post_api:posts-detail', args=[post.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_regions_stats_and_forum_endpoints_preserve_existing_results(self):
        post = self.make_post()
        other_post = self.make_post(
            owner=self.other_user,
            title='Other user post',
        )
        self.make_post(status=Barter.StatusChoices.NEGOTIATING)

        with self.settings(BOGORTECH_API_KEY=''):
            regions = self.client.get(
                reverse('profile_post_api:posts-regions'),
                {'q': 'depok'},
            )
        stats = self.client.get(reverse('profile_post_api:posts-stats'))
        forum = self.client.get(reverse('profile_post_api:posts-forum'))

        self.assertEqual(regions.status_code, 200)
        self.assertIn('results', regions.data)
        self.assertEqual(stats.data['posts'], {'value': 2})
        self.assertCountEqual(
            [item['id'] for item in forum.data['forum_posts']],
            [post.pk, other_post.pk],
        )

    def test_offer_selection_negotiation_cancellation_and_completion(self):
        post = self.make_post()
        offer = BarterOffer.objects.create(
            post=post,
            offerer=self.other_user,
            offered_item_title='Offered item',
            offered_item_description='An offer description',
        )
        detail_url = reverse('profile_post_api:posts-detail', args=[post.pk])

        response = self.client.post(
            reverse('profile_post_api:posts-select-offer', args=[post.pk]),
            {'offer_id': offer.pk},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(post.status, Barter.StatusChoices.NEGOTIATING)
        self.assertTrue(offer.is_selected)

        response = self.client.post(
            reverse('profile_post_api:posts-cancel-negotiation', args=[post.pk])
        )
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(post.status, Barter.StatusChoices.AVAILABLE)
        self.assertFalse(offer.is_selected)

        self.client.post(
            reverse('profile_post_api:posts-select-offer', args=[post.pk]),
            {'offer_id': offer.pk},
            format='json',
        )
        response = self.client.post(
            reverse('profile_post_api:posts-complete', args=[post.pk])
        )
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, Barter.StatusChoices.BARTERED)
        self.assertIsNotNone(post.completed_at)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_owner_and_selected_offerer_can_review_completed_barter(self):
        post = self.make_post(status=Barter.StatusChoices.BARTERED)
        offer = BarterOffer.objects.create(
            post=post,
            offerer=self.other_user,
            offered_item_title='Offered item',
            offered_item_description='An offer description',
            is_selected=True,
        )

        response = self.client.post(
            reverse('profile_post_api:posts-reviews', args=[post.pk]),
            {'rating': 9, 'comment': '<b>Great</b>'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['comment'], 'Great')
        self.assertEqual(response.data['role'], BarterReview.RoleChoices.OWNER_TO_OFFERER)

        self.client.force_authenticate(self.other_user)
        response = self.client.post(
            reverse('profile_post_api:posts-reviews', args=[post.pk]),
            {'rating': 4},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data['role'],
            BarterReview.RoleChoices.OFFERER_TO_OWNER,
        )
        self.assertEqual(
            BarterReview.objects.filter(post=post).count(),
            2,
        )
        self.assertTrue(offer.is_selected)

        response = self.client.post(
            reverse('profile_post_api:posts-reviews', args=[post.pk]),
            {'rating': 4},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
