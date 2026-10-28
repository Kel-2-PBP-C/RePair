from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ProfileForm
from accounts.models import Profile
from profile_post.forms import PostForm
from profile_post.models import BarterOffer, BarterReview, Post
from profile_post.views import _format_created_at, _get_user_contact


User = get_user_model()


class PostFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="jamie",
            email="jamie@example.test",
            first_name="Jamie",
            last_name="Ng",
            password="test-password",
        )
        self.profile = Profile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def post_data(self, category="buku"):
        return {
            "title": "A well-loved book",
            "description": "In good condition",
            "location": "Depok",
            "location_code": "",
            "category": category,
            "condition": Post.ConditionChoices.GOOD,
            "preferred_barter": "A houseplant",
        }

    def test_new_posts_require_a_category_and_legacy_posts_can_remain_uncategorized(self):
        self.assertFalse(PostForm(self.post_data(category="")).is_valid())
        self.assertTrue(PostForm(self.post_data()).is_valid())

        post = Post.objects.create(
            user=self.user,
            title="Legacy post",
            description="No category was previously stored",
            location="Depok",
            preferred_barter="A houseplant",
        )
        edit_form = PostForm(self.post_data(category=""), instance=post)
        self.assertTrue(edit_form.is_valid(), edit_form.errors)
        self.assertNotIn("shipping_duration", edit_form.fields)

    def test_create_endpoint_saves_the_selected_category(self):
        response = self.client.post(
            reverse("profile_post:create_post"),
            self.post_data(category="elektronik"),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.get().category, "elektronik")

    def test_edit_endpoint_updates_the_selected_category(self):
        post = Post.objects.create(
            user=self.user,
            title="A well-loved book",
            description="In good condition",
            location="Depok",
            category="buku",
            preferred_barter="A houseplant",
        )
        response = self.client.post(
            reverse("profile_post:edit_post", args=[post.pk]),
            self.post_data(category="hobi"),
        )

        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.category, "hobi")

    def test_posts_page_uses_account_initials_and_shows_contact_setup_state(self):
        response = self.client.get(reverse("profile_post:show_posts"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_initials"], "JN")
        self.assertEqual(response.context["preferred_contact"], "")
        self.assertContains(
            response,
            f'data-default-location-code="{response.context["default_location_code"]}"',
        )
        self.assertContains(
            response,
            f'data-default-location-label="{response.context["default_location_label"]}"',
        )
        self.assertEqual(response.content.decode().count("<body"), 1)
        self.assertContains(response, "Kontak pilihan:")
        self.assertContains(response, "Belum diatur")
        self.assertContains(response, "Atur di Pengaturan Akun")
        self.assertContains(response, "Kategori barang")
        self.assertContains(response, 'id="loading-indicator"')
        self.assertNotContains(response, 'id="loading-picator"')
        self.assertContains(response, "css/profile-post.css")
        self.assertContains(response, "js/vendor/purify.min.js")
        self.assertNotContains(response, "cdn.tailwindcss.com")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/dompurify")
        self.assertNotContains(response, "filter-shipping")
        self.assertNotContains(response, "form-shipping")

    def test_posts_page_exposes_saved_domicile_as_javascript_defaults(self):
        self.profile.domicile = "Kota Depok, Jawa Barat"
        self.profile.domicile_code = "32.76"
        self.profile.save(update_fields=["domicile", "domicile_code"])

        response = self.client.get(reverse("profile_post:show_posts"))

        self.assertEqual(response.context["default_location_code"], "32.76")
        self.assertEqual(response.context["default_location_label"], "Kota Depok, Jawa Barat")
        self.assertContains(response, 'data-default-location-code="32.76"')
        self.assertContains(response, 'data-default-location-label="Kota Depok, Jawa Barat"')

    def test_preferred_contact_is_used_and_never_falls_back_to_email(self):
        self.assertEqual(_get_user_contact(self.user), "")

        profile_form = ProfileForm(user=self.user, instance=self.profile)
        self.assertEqual(profile_form.fields["social_contact"].label, "Kontak pilihan")
        self.assertIn("LINE", profile_form.fields["social_contact"].help_text)

        self.profile.social_contact = "@jamie-on-line"
        self.profile.save(update_fields=["social_contact"])
        self.assertEqual(_get_user_contact(self.user), "@jamie-on-line")

    def test_offer_contact_fallback_does_not_expose_the_offerers_email(self):
        post = Post.objects.create(
            user=self.user,
            title="A well-loved book",
            description="In good condition",
            location="Depok",
            preferred_barter="A houseplant",
        )
        offerer = User.objects.create_user(
            username="offerer",
            email="offerer@example.test",
            password="test-password",
        )
        BarterOffer.objects.create(
            post=post,
            offerer=offerer,
            offered_item_title="A houseplant",
            offered_item_description="Healthy plant",
            offerer_contact=offerer.email,
        )

        response = self.client.get(
            reverse("profile_post:get_post_offers", args=[post.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["offers"][0]["offerer_contact"], "Kontak belum diatur")
        self.assertNotIn("offerer@example.test", response.content.decode())

    def test_category_is_returned_by_posts_api_and_shown_on_detail(self):
        post = Post.objects.create(
            user=self.user,
            title="A well-loved book",
            description="In good condition",
            location="Depok",
            category="buku",
            preferred_barter="A houseplant",
        )
        list_response = self.client.get(reverse("profile_post:get_posts_json"))
        detail_response = self.client.get(
            reverse("profile_post:post_detail", args=[post.pk])
        )

        self.assertEqual(list_response.json()["posts"][0]["category_label"], "Buku")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Buku")
        self.assertContains(detail_response, _format_created_at(post.created_at)[0])
        self.assertNotContains(detail_response, "Pengiriman")

    def test_description_clamps_to_three_lines_in_post_list(self):
        response = self.client.get(reverse("profile_post:show_posts"))

        self.assertContains(response, "line-clamp-3 break-words [overflow-wrap:anywhere]")

    def test_list_template_only_offers_an_owner_submitted_review(self):
        response = self.client.get(reverse("profile_post:show_posts"))

        self.assertContains(response, "Ulasan Anda untuk")
        self.assertContains(response, "Ulasan dari pihak penawar belum tersedia.")
        self.assertNotContains(response, "Simulasikan review penawar")
        self.assertNotContains(response, "review-role")

    def test_offer_sort_orders_by_offer_count_then_newest(self):
        fewer_offers = Post.objects.create(
            user=self.user,
            title="One offer",
            description="Post with fewer offers",
            location="Depok",
            preferred_barter="A plant",
        )
        more_offers = Post.objects.create(
            user=self.user,
            title="Two offers",
            description="Post with more offers",
            location="Depok",
            preferred_barter="A plant",
        )
        offerer = User.objects.create_user(username="offerer", password="test-password")
        for post in (fewer_offers, more_offers, more_offers):
            BarterOffer.objects.create(
                post=post,
                offerer=offerer,
                offered_item_title="A plant",
                offered_item_description="Healthy",
                offerer_contact="",
            )

        response = self.client.get(
            reverse("profile_post:get_posts_json"), {"sort": "offer"}
        )

        self.assertEqual(
            [post["id"] for post in response.json()["posts"]],
            [more_offers.id, fewer_offers.id],
        )

    def test_created_at_uses_indonesian_date_and_relative_time(self):
        created_at = timezone.make_aware(datetime(2026, 1, 15, 9, 30))

        date_display, relative_display = _format_created_at(created_at)

        self.assertIn("Januari", date_display)
        self.assertNotIn("January", date_display)
        self.assertTrue(relative_display.endswith("yang lalu"))

    def test_review_endpoint_always_records_owner_to_offerer_review(self):
        post = Post.objects.create(
            user=self.user,
            title="Completed barter",
            description="Completed",
            location="Depok",
            preferred_barter="A plant",
            status=Post.StatusChoices.BARTERED,
        )
        offerer = User.objects.create_user(
            username="reviewed-offerer", password="test-password"
        )
        BarterOffer.objects.create(
            post=post,
            offerer=offerer,
            offered_item_title="A plant",
            offered_item_description="Healthy",
            offerer_contact="",
            is_selected=True,
        )

        response = self.client.post(
            reverse("profile_post:submit_review", args=[post.pk]),
            {
                "role": BarterReview.RoleChoices.OFFERER_TO_OWNER,
                "rating": "4",
                "comment": "A good barter",
            },
        )

        self.assertEqual(response.status_code, 200)
        review = BarterReview.objects.get(post=post)
        self.assertEqual(review.role, BarterReview.RoleChoices.OWNER_TO_OFFERER)
        self.assertEqual(review.reviewer, self.user)
        self.assertEqual(review.reviewee, offerer)

        list_response = self.client.get(reverse("profile_post:get_posts_json"))
        serialized_review = list_response.json()["posts"][0]["reviews"]
        self.assertNotIn("to_owner", serialized_review)
        self.assertEqual(serialized_review["to_offerer"]["rating"], 4)

    def test_owner_to_offerer_reviews_are_the_only_reviews_counted_as_received(self):
        reviewed_user = User.objects.create_user(
            username="reviewed-member", password="test-password"
        )
        actual_review_post = Post.objects.create(
            user=reviewed_user,
            title="Actual review",
            description="Post",
            location="Depok",
            preferred_barter="A plant",
        )
        simulated_review_post = Post.objects.create(
            user=reviewed_user,
            title="Legacy simulated review",
            description="Post",
            location="Depok",
            preferred_barter="A plant",
        )
        BarterReview.objects.create(
            post=actual_review_post,
            reviewer=self.user,
            reviewee=reviewed_user,
            role=BarterReview.RoleChoices.OWNER_TO_OFFERER,
            rating=4,
            comment="Actual",
        )
        BarterReview.objects.create(
            post=simulated_review_post,
            reviewer=self.user,
            reviewee=reviewed_user,
            role=BarterReview.RoleChoices.OFFERER_TO_OWNER,
            rating=1,
            comment="Legacy simulated",
        )
        self.client.force_login(reviewed_user)

        response = self.client.get(
            reverse("profile_post:get_user_stats"), {"period": "A"}
        )

        self.assertEqual(response.json()["rating"]["value"], 4.0)
