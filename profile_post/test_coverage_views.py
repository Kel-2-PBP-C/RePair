import uuid
from datetime import timedelta
from unittest import mock

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts import regions as acc_regions
from accounts.models import Profile
from profile_post import views
from profile_post.forms import PostForm, resolve_region_from_accounts
from profile_post.models import BarterOffer, BarterReview, Post


User = get_user_model()


class ProfilePostHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="helper-owner", email="owner@example.test")

    def test_default_region_uses_fallback_label_when_only_code_is_saved(self):
        Profile.objects.create(user=self.user, domicile_code="3171", domicile="")

        self.assertEqual(
            views._get_user_default_region(self.user),
            ("3171", "Jakarta Pusat, DKI Jakarta"),
        )

    def test_default_region_uses_code_as_label_when_code_is_unknown(self):
        Profile.objects.create(user=self.user, domicile_code="9999", domicile="")

        self.assertEqual(views._get_user_default_region(self.user), ("9999", "9999"))

    def test_default_region_falls_back_to_jakarta_selatan_without_profile_data(self):
        Profile.objects.create(user=self.user)

        self.assertEqual(
            views._get_user_default_region(self.user),
            ("3174", "Jakarta Selatan, DKI Jakarta"),
        )

    def test_query_regions_normalizes_search_helper_results(self):
        def fake_search(query):
            return [
                {"code": "32.76", "name": "Kota Depok"},
                {"id": "32.71", "label": "Kota Bogor"},
                ("31.74", "Jakarta Selatan"),
                "not-a-region",
                ("too-short",),
            ]

        with mock.patch.object(acc_regions, "search_regions", fake_search):
            results = views._query_accounts_regions("kota")

        self.assertEqual(
            results,
            [
                {"code": "32.76", "name": "Kota Depok"},
                {"code": "32.71", "name": "Kota Bogor"},
            ],
        )

    def test_query_regions_caps_results_at_25(self):
        fake_data = [{"code": str(i), "name": f"Kota {i}"} for i in range(40)]
        with mock.patch.object(acc_regions, "search_regions", lambda query: fake_data):
            results = views._query_accounts_regions("")

        self.assertEqual(len(results), 25)
        self.assertEqual(results[0], {"code": "0", "name": "Kota 0"})

    def test_query_regions_reads_dict_and_list_constants(self):
        with mock.patch.object(acc_regions, "search_regions", lambda query: []), \
                mock.patch.object(
                    acc_regions,
                    "REGIONS",
                    {"11.01": {"name": "Kabupaten Simeulue"}, "11.02": "Kabupaten Aceh Singkil"},
                    create=True,
                ):
            results = views._query_accounts_regions("aceh")
        self.assertEqual(results, [{"code": "11.02", "name": "Kabupaten Aceh Singkil"}])

        with mock.patch.object(acc_regions, "search_regions", lambda query: []), \
                mock.patch.object(
                    acc_regions,
                    "REGION_LIST",
                    [{"code": "12.01", "name": "Kota Medan"}, ("12.02", "Kota Binjai"), 42],
                    create=True,
                ):
            results = views._query_accounts_regions("")
        self.assertEqual(
            results,
            [{"code": "12.01", "name": "Kota Medan"}, {"code": "12.02", "name": "Kota Binjai"}],
        )

    def test_query_regions_falls_back_to_builtin_list_when_accounts_has_no_match(self):
        with mock.patch.object(acc_regions, "search_regions", lambda query: []):
            results = views._query_accounts_regions("surabaya")

        self.assertEqual(results, [{"code": "3578", "name": "Kota Surabaya, Jawa Timur"}])

    def test_resolve_detail_url_prefers_barter_detail_route(self):
        post_id = uuid.uuid4()
        self.assertEqual(
            views._resolve_detail_url(post_id),
            reverse("barter_details:barter_detail", args=[post_id]),
        )

    def test_resolve_detail_url_falls_back_to_hardcoded_path(self):
        with mock.patch.object(views, "reverse", side_effect=NoReverseMatch):
            self.assertEqual(views._resolve_detail_url("abc"), "/profile-post/abc/")

    def test_localized_errors_use_generic_message_when_params_are_missing(self):
        class DummyForm(forms.Form):
            name = forms.CharField(label="Nama")

        form = DummyForm(data={"name": "x"})
        form.is_valid()
        form.add_error("name", ValidationError("too long", code="max_length"))
        form.add_error(None, ValidationError("odd", code="something_else"))

        errors = views._localized_form_errors(form)
        self.assertEqual(errors["Nama"], ["Nama: Periksa kembali nilai yang dimasukkan."])
        self.assertEqual(errors["Formulir"], ["Formulir: Periksa kembali nilai yang dimasukkan."])

    def test_calc_delta_reports_percentage_change(self):
        self.assertEqual(
            views._calc_delta(3, 2),
            {"value": 3, "diff": 1, "pct": 50.0, "direction": "up"},
        )
        self.assertEqual(
            views._calc_delta(2.0, 4.0, is_float=True),
            {"value": 2.0, "diff": -2.0, "pct": -50.0, "direction": "down"},
        )
        self.assertEqual(views._calc_delta(0, 0)["direction"], "neutral")

    def test_offer_str_includes_title_and_offerer(self):
        post = Post.objects.create(
            user=self.user, title="Lamp", description="Desk lamp", location="Depok",
        )
        offer = BarterOffer.objects.create(
            post=post,
            offerer=self.user,
            offered_item_title="Kettle",
            offered_item_description="Electric",
        )
        self.assertEqual(str(offer), "Tawaran Kettle oleh helper-owner")


class PostFormCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="form-owner")

    def valid_data(self):
        return {
            "title": "<b>Rice cooker</b>",
            "description": "Works well",
            "location": "Depok",
            "location_code": "32.76",
            "category": Profile.CATEGORY_CHOICES[0][0],
            "condition": Post.ConditionChoices.GOOD,
            "preferred_barter": "Blender",
        }

    def test_region_resolver_uses_accounts_lookup_returning_dict(self):
        with mock.patch.object(
            acc_regions, "get_region_label", lambda code: {"label": "Kota Depok, Jawa Barat"}, create=True,
        ):
            self.assertEqual(
                resolve_region_from_accounts("<i>32.76</i>", "Depok"),
                ("32.76", "Kota Depok, Jawa Barat"),
            )
        with mock.patch.object(acc_regions, "get_region_label", lambda code: {}, create=True):
            self.assertEqual(resolve_region_from_accounts("32.76", "Depok"), ("32.76", "Depok"))

    def test_region_resolver_uses_accounts_lookup_returning_string(self):
        with mock.patch.object(acc_regions, "get_region_name", lambda code: "Kota Bogor", create=True):
            self.assertEqual(resolve_region_from_accounts("32.71", ""), ("32.71", "Kota Bogor"))

    def test_unbound_form_is_not_valid_and_does_not_require_data(self):
        form = PostForm()
        self.assertFalse(form.is_bound)
        self.assertTrue(form.fields["category"].required)

    def test_data_keyword_aliases_are_mapped_and_title_is_sanitized(self):
        data = QueryDict(mutable=True)
        data.update(self.valid_data())
        form = PostForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["title"], "Rice cooker")
        self.assertEqual(form.cleaned_data["item_location"], "Depok")
        self.assertEqual(form.cleaned_data["item_replacement"], "Blender")
        # The caller's QueryDict is copied, not mutated with the canonical names.
        self.assertNotIn("item_location", data)

    def test_save_with_commit_persists_profile_post(self):
        form = PostForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner = self.user

        post = form.save()

        self.assertTrue(Post.objects.filter(pk=post.pk, is_profile_post=True).exists())

    def test_save_can_skip_profile_post_flag(self):
        form = PostForm(data=self.valid_data(), mark_as_profile_post=False)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner = self.user

        post = form.save()

        post.refresh_from_db()
        self.assertFalse(post.is_profile_post)


class ProfilePostEndpointCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="endpoint-owner", email="owner@example.test")
        self.profile = Profile.objects.create(
            user=self.user, domicile_code="3171", domicile="Jakarta Pusat, DKI Jakarta",
        )
        self.other = User.objects.create_user(username="endpoint-other", email="other@example.test")
        Profile.objects.create(user=self.other, social_contact="@other")
        self.client.force_login(self.user)

    def make_post(self, owner=None, **kwargs):
        defaults = {
            "user": owner or self.user,
            "title": "Bike",
            "description": "City bike",
            "location": "Depok",
            "location_code": "32.76",
            "condition": Post.ConditionChoices.GOOD,
            "preferred_barter": "Guitar",
        }
        defaults.update(kwargs)
        return Post.objects.create(**defaults)

    def list_titles(self, **params):
        response = self.client.get(reverse("profile_post:get_posts_json"), params)
        self.assertEqual(response.status_code, 200)
        return [post["title"] for post in response.json()["posts"]]

    # ---- detail page / id lookup ----
    def test_detail_page_supports_legacy_numeric_ids(self):
        post = self.make_post(legacy_profile_post_id=77)

        response = self.client.get(reverse("profile_post:post_detail", args=["77"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["post"], post)

    def test_detail_page_returns_404_for_non_uuid_non_numeric_ids(self):
        response = self.client.get(reverse("profile_post:post_detail", args=["not-a-post"]))
        self.assertEqual(response.status_code, 404)

    # ---- regions API ----
    def test_region_search_api_returns_matching_regions(self):
        with mock.patch.object(
            acc_regions, "search_regions", lambda query: [{"code": "32.76", "name": "Kota Depok"}],
        ):
            response = self.client.get(reverse("profile_post:search_regions"), {"q": " depok "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": [{"code": "32.76", "name": "Kota Depok"}]})

    def test_region_search_api_rejects_post(self):
        response = self.client.post(reverse("profile_post:search_regions"))
        self.assertEqual(response.status_code, 405)

    # ---- stats ----
    def test_monthly_stats_compare_against_previous_period(self):
        now = timezone.now()
        old = self.make_post(title="Old")
        Post.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=45))
        self.make_post(title="New A")
        self.make_post(title="New B")

        response = self.client.get(reverse("profile_post:get_user_stats"), {"period": "m"})

        data = response.json()
        self.assertEqual(data["period"], "M")
        self.assertTrue(data["show_delta"])
        self.assertEqual(data["posts"], {"value": 2, "diff": 1, "pct": 100.0, "direction": "up"})
        self.assertEqual(data["rating"]["direction"], "neutral")

    # ---- list filters ----
    def test_list_filters_by_search_query(self):
        self.make_post(title="Bike")
        self.make_post(title="Camera", description="Mirrorless", preferred_barter="Drone")

        self.assertEqual(self.list_titles(q="mirror"), ["Camera"])
        self.assertEqual(self.list_titles(q="drone"), ["Camera"])

    def test_list_filters_by_location_code_and_label(self):
        self.make_post(title="Depok item", location="Depok", location_code="32.76")
        self.make_post(title="Bogor item", location="Kota Bogor", location_code="32.71")
        self.make_post(title="Bandung item", location="Bandung", location_code="32.73")

        self.assertEqual(self.list_titles(location_code="32.76"), ["Depok item"])
        self.assertEqual(self.list_titles(location="bogor"), ["Bogor item"])
        self.assertCountEqual(
            self.list_titles(location_code="32.76", location="bogor"),
            ["Depok item", "Bogor item"],
        )

    def test_list_filters_by_condition_and_status(self):
        self.make_post(title="New one", condition=Post.ConditionChoices.NEW)
        self.make_post(title="Broken", condition=Post.ConditionChoices.REPAIR,
                       status=Post.StatusChoices.NEGOTIATING)

        self.assertEqual(self.list_titles(condition=Post.ConditionChoices.NEW), ["New one"])
        self.assertEqual(self.list_titles(status=Post.StatusChoices.NEGOTIATING), ["Broken"])

    def test_list_sorts_oldest_first(self):
        first = self.make_post(title="First")
        Post.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(days=2))
        self.make_post(title="Second")

        self.assertEqual(self.list_titles(sort="oldest"), ["First", "Second"])
        self.assertEqual(self.list_titles(), ["Second", "First"])

    def test_list_serializes_selected_offer_and_reviews(self):
        post = self.make_post(status=Post.StatusChoices.BARTERED)
        BarterOffer.objects.create(
            post=post, offerer=self.other, offered_item_title="Guitar",
            offered_item_description="Acoustic", is_selected=True,
        )
        BarterReview.objects.create(
            post=post, reviewer=self.user, reviewee=self.other,
            role=BarterReview.RoleChoices.OWNER_TO_OFFERER, rating=4, comment="Nice",
        )
        BarterReview.objects.create(
            post=post, reviewer=self.other, reviewee=self.user,
            role=BarterReview.RoleChoices.OFFERER_TO_OWNER, rating=5, comment="Great",
        )

        data = self.client.get(reverse("profile_post:get_posts_json")).json()["posts"][0]

        self.assertEqual(data["selected_offer"]["offerer_contact"], "@other")
        self.assertEqual(data["selected_offer"]["offerer_name"], "endpoint-other")
        self.assertEqual(data["reviews"]["to_offerer"], {"rating": 4, "comment": "Nice"})
        self.assertEqual(data["reviews"]["to_owner"], {"rating": 5, "comment": "Great"})

    def test_list_paginates_five_per_page(self):
        for i in range(6):
            self.make_post(title=f"Item {i}")

        first = self.client.get(reverse("profile_post:get_posts_json")).json()
        second = self.client.get(reverse("profile_post:get_posts_json"), {"page": 2}).json()

        self.assertEqual(len(first["posts"]), 5)
        self.assertTrue(first["has_next"])
        self.assertEqual(len(second["posts"]), 1)
        self.assertFalse(second["has_next"])
        self.assertEqual(second["current_page"], 2)

    # ---- forum ----
    def test_forum_lists_only_available_profile_posts(self):
        self.make_post(owner=self.other, title="Open", category=Profile.CATEGORY_CHOICES[0][0])
        self.make_post(owner=self.other, title="Busy", status=Post.StatusChoices.NEGOTIATING)
        Post.objects.create(
            owner=self.other, title="Marketplace", description="x", item_location="Depok",
        )

        response = self.client.get(reverse("profile_post:get_forum_posts"))

        self.assertEqual(response.status_code, 200)
        forum = response.json()["forum_posts"]
        self.assertEqual([p["title"] for p in forum], ["Open"])
        self.assertEqual(forum[0]["owner"], "endpoint-other")
        self.assertEqual(forum[0]["status"], "Tersedia")
        self.assertEqual(forum[0]["category_label"], Profile.CATEGORY_CHOICES[0][1])

    # ---- create/edit fallbacks ----
    def create_payload(self, **overrides):
        payload = {
            "title": "Toaster",
            "description": "Two slots",
            "location": "Depok",
            "location_code": "",
            "category": Profile.CATEGORY_CHOICES[0][0],
            "condition": Post.ConditionChoices.GOOD,
            "preferred_barter": "Kettle",
            "image_url": "",
        }
        payload.update(overrides)
        return payload

    def test_create_assigns_placeholder_image_when_missing(self):
        response = self.client.post(reverse("profile_post:create_post"), self.create_payload())

        self.assertEqual(response.status_code, 201)
        post = Post.objects.get(title="Toaster")
        self.assertIn("placehold.co", post.image_url)
        self.assertEqual(post.owner, self.user)
        self.assertEqual(post.status, Post.StatusChoices.AVAILABLE)

    def test_create_rejects_post_when_region_label_cannot_be_resolved(self):
        # item_location is a required model field, so the view's "inherit default
        # region" fallback (views.py:429-434) is unreachable through PostForm.
        with mock.patch("profile_post.forms.resolve_region_from_accounts", return_value=("3171", "")):
            response = self.client.post(
                reverse("profile_post:create_post"), self.create_payload(location_code="3171"),
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Lokasi", response.json()["errors"])
        self.assertFalse(Post.objects.filter(title="Toaster").exists())

    def test_edit_rejects_posts_that_are_not_available(self):
        post = self.make_post(status=Post.StatusChoices.NEGOTIATING)

        response = self.client.post(
            reverse("profile_post:edit_post", args=[post.id]), self.create_payload(title="Changed"),
        )

        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertEqual(post.title, "Bike")

    def test_edit_returns_localized_errors_for_invalid_data(self):
        post = self.make_post()

        response = self.client.post(
            reverse("profile_post:edit_post", args=[post.id]), self.create_payload(title=""),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["Nama barang"], ["Nama barang: Wajib diisi."])

    def test_edit_of_another_users_post_is_404(self):
        post = self.make_post(owner=self.other)

        response = self.client.post(
            reverse("profile_post:edit_post", args=[post.id]), self.create_payload(title="Hijack"),
        )

        self.assertEqual(response.status_code, 404)
        post.refresh_from_db()
        self.assertEqual(post.title, "Bike")

    # ---- delete ----
    def test_delete_removes_available_post(self):
        post = self.make_post()

        response = self.client.post(reverse("profile_post:delete_post", args=[post.id]))

        self.assertEqual(response.json(), {"status": "success"})
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_delete_rejects_post_in_negotiation(self):
        post = self.make_post(status=Post.StatusChoices.NEGOTIATING)

        response = self.client.post(reverse("profile_post:delete_post", args=[post.id]))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    def test_delete_requires_post_method(self):
        post = self.make_post()
        self.assertEqual(
            self.client.get(reverse("profile_post:delete_post", args=[post.id])).status_code, 405,
        )


class BarterWorkflowCoverageTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="flow-owner")
        self.offerer = User.objects.create_user(username="flow-offerer")
        self.post = Post.objects.create(
            user=self.owner, title="Drill", description="Cordless", location="Depok",
        )
        self.offer = BarterOffer.objects.create(
            post=self.post, offerer=self.offerer,
            offered_item_title="Saw", offered_item_description="Hand saw",
        )
        self.other_offer = BarterOffer.objects.create(
            post=self.post, offerer=self.offerer,
            offered_item_title="Hammer", offered_item_description="Claw", is_selected=True,
        )
        self.client.force_login(self.owner)

    def url(self, name):
        return reverse(f"profile_post:{name}", args=[self.post.id])

    def set_status(self, status, selected=None):
        self.post.status = status
        self.post.save()
        BarterOffer.objects.filter(post=self.post).update(is_selected=False)
        if selected:
            BarterOffer.objects.filter(pk=selected.pk).update(is_selected=True)

    # ---- lock ----
    def test_lock_selects_exactly_one_offer_and_starts_negotiation(self):
        response = self.client.post(self.url("lock_barter"), {"offer_id": self.offer.id})

        self.assertEqual(response.json(), {"status": "success"})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.StatusChoices.NEGOTIATING)
        self.assertEqual(list(self.post.offers.filter(is_selected=True)), [self.offer])

    def test_lock_rejects_bartered_post(self):
        self.set_status(Post.StatusChoices.BARTERED)

        response = self.client.post(self.url("lock_barter"), {"offer_id": self.offer.id})

        self.assertEqual(response.status_code, 400)

    def test_lock_rejects_offer_from_another_post(self):
        other_post = Post.objects.create(
            user=self.owner, title="Other", description="x", location="Depok",
        )
        foreign = BarterOffer.objects.create(
            post=other_post, offerer=self.offerer,
            offered_item_title="X", offered_item_description="Y",
        )

        response = self.client.post(self.url("lock_barter"), {"offer_id": foreign.id})

        self.assertEqual(response.status_code, 404)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.StatusChoices.AVAILABLE)

    def test_non_owner_cannot_lock(self):
        self.client.force_login(self.offerer)
        response = self.client.post(self.url("lock_barter"), {"offer_id": self.offer.id})
        self.assertEqual(response.status_code, 404)

    # ---- cancel ----
    def test_cancel_negotiation_resets_status_and_selection(self):
        self.set_status(Post.StatusChoices.NEGOTIATING, selected=self.offer)

        response = self.client.post(self.url("cancel_negotiation"))

        self.assertEqual(response.json(), {"status": "success"})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.StatusChoices.AVAILABLE)
        self.assertFalse(self.post.offers.filter(is_selected=True).exists())

    def test_cancel_rejects_post_not_in_negotiation(self):
        response = self.client.post(self.url("cancel_negotiation"))
        self.assertEqual(response.status_code, 400)

    # ---- complete ----
    def test_complete_marks_post_bartered(self):
        self.set_status(Post.StatusChoices.NEGOTIATING, selected=self.offer)

        response = self.client.post(self.url("complete_barter"))

        self.assertEqual(response.json(), {"status": "success"})
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.StatusChoices.BARTERED)
        self.assertIsNotNone(self.post.completed_at)

    def test_complete_rejects_available_post(self):
        self.set_status(Post.StatusChoices.AVAILABLE)
        response = self.client.post(self.url("complete_barter"))
        self.assertEqual(response.status_code, 400)

    def test_complete_requires_selected_offer(self):
        self.set_status(Post.StatusChoices.NEGOTIATING)

        response = self.client.post(self.url("complete_barter"))

        self.assertEqual(response.status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.StatusChoices.NEGOTIATING)

    # ---- owner review ----
    def test_owner_review_requires_selected_offer(self):
        self.set_status(Post.StatusChoices.BARTERED)

        response = self.client.post(self.url("submit_review"), {"rating": 4})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BarterReview.objects.exists())

    def test_owner_review_defaults_invalid_rating_and_clamps_range(self):
        self.set_status(Post.StatusChoices.BARTERED, selected=self.offer)

        self.client.post(self.url("submit_review"), {"rating": "abc", "comment": "<b>ok</b>"})
        review = BarterReview.objects.get(post=self.post)
        self.assertEqual((review.rating, review.comment), (5, "ok"))
        self.assertEqual(review.reviewee, self.offerer)

        self.client.post(self.url("submit_review"), {"rating": "-3"})
        review.refresh_from_db()
        self.assertEqual(review.rating, 1)
        self.assertEqual(BarterReview.objects.filter(post=self.post).count(), 1)

    def test_owner_review_is_404_before_barter_is_complete(self):
        self.set_status(Post.StatusChoices.NEGOTIATING, selected=self.offer)
        response = self.client.post(self.url("submit_review"), {"rating": 4})
        self.assertEqual(response.status_code, 404)

    # ---- bidder review ----
    def bidder_post(self, data):
        self.set_status(Post.StatusChoices.BARTERED, selected=self.offer)
        self.client.force_login(self.offerer)
        return self.client.post(self.url("submit_bidder_review"), data)

    def flashed(self, response):
        return [str(m) for m in response.wsgi_request._messages]

    def test_bidder_review_is_saved_once(self):
        response = self.bidder_post({"rating": "4", "comment": "<i>Smooth</i>"})

        self.assertRedirects(response, reverse("keranjang:keranjang"), fetch_redirect_response=False)
        review = BarterReview.objects.get(role=BarterReview.RoleChoices.OFFERER_TO_OWNER)
        self.assertEqual((review.rating, review.comment), (4, "Smooth"))
        self.assertEqual((review.reviewer, review.reviewee), (self.offerer, self.owner))
        self.assertIn("Ulasan berhasil dikirim.", self.flashed(response))

        again = self.client.post(self.url("submit_bidder_review"), {"rating": "1"})
        self.assertIn("Kamu sudah mengirim ulasan untuk barter ini.", self.flashed(again))
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)

    def test_bidder_review_rejects_non_numeric_rating(self):
        response = self.bidder_post({"rating": "great"})

        self.assertIn("Pilih rating dari 1 sampai 5.", self.flashed(response))
        self.assertFalse(BarterReview.objects.exists())

    def test_bidder_review_rejects_out_of_range_rating(self):
        response = self.bidder_post({"rating": "9"})

        self.assertIn("Pilih rating dari 1 sampai 5.", self.flashed(response))
        self.assertFalse(BarterReview.objects.exists())

    def test_non_selected_bidder_cannot_review(self):
        stranger = User.objects.create_user(username="flow-stranger")
        self.set_status(Post.StatusChoices.BARTERED, selected=self.offer)
        self.client.force_login(stranger)

        response = self.client.post(self.url("submit_bidder_review"), {"rating": "5"})

        self.assertEqual(response.status_code, 404)
