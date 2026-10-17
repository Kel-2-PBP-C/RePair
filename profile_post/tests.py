from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from profile_post.views import show_posts


class PostsPageTests(TestCase):
    def test_posts_route_renders_shared_layout(self):
        url = reverse("profile_post:show_posts")
        self.assertEqual(url, "/posts/")
        self.assertEqual(resolve(url).func, show_posts)

        response = self.client.get(url)
        self.assertTemplateUsed(response, "profile_post/index.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "<title>Posts | RePair</title>", html=True)
        self.assertContains(response, "<h1>Posts</h1>", html=True)
        self.assertContains(response, 'aria-label="Navigasi utama"')
        self.assertContains(response, "&copy; Repair, all rights reserved.")
        self.assertNotContains(response, "THIS IS THE USER PROFILE")

    def test_old_profile_url_no_longer_renders_posts(self):
        self.assertEqual(self.client.get("/profile/").status_code, 404)

    def test_posts_navigation_is_distinct_from_account_profile(self):
        user = get_user_model().objects.create_user(username="posts-page-member")
        self.client.force_login(user)

        response = self.client.get(reverse("profile_post:show_posts"))
        items = {item["key"]: item for item in response.context["navigation"]["items"]}
        self.assertEqual(items["posts"]["url"], "/posts/")
        self.assertTrue(items["posts"]["active"])
        self.assertEqual(items["settings"]["url"], reverse("accounts:profile"))
        self.assertFalse(items["settings"]["active"])
        self.assertEqual(sum(item["active"] for item in items.values()), 1)
        self.assertContains(response, 'href="/posts/" aria-current="page"')
        self.assertContains(response, f'href="{reverse("accounts:profile")}"')
