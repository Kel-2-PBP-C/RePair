from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.regions import RegionServiceError
from profile_post import views


@override_settings(BOGORTECH_API_KEY="")
class PostsApiRegressionTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="posts-regression"))

    def test_region_search_falls_back_when_region_service_is_unavailable(self):
        response = self.client.get(reverse("profile_post:search_regions"), {"q": "depok"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())

    def test_region_search_falls_back_on_overlong_query(self):
        response = self.client.get(reverse("profile_post:search_regions"), {"q": "x" * 200})
        self.assertEqual(response.status_code, 200)

    def test_region_search_falls_back_on_provider_error(self):
        def failing_search(query):
            raise RegionServiceError("down")

        with mock.patch("accounts.regions.search_regions", failing_search):
            results = views._query_accounts_regions("")
        self.assertEqual(results, views.FALLBACK_REGIONS[:25])

    def test_posts_list_ignores_non_numeric_page(self):
        response = self.client.get(reverse("profile_post:get_posts_json"), {"page": "abc"})
        self.assertEqual(response.status_code, 200)

