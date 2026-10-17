import json
import time
from datetime import timedelta

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import google_auth
from .models import GoogleIdentity, Profile
from .test_google_auth import GOOGLE_SETTINGS

User = get_user_model()


@override_settings(**GOOGLE_SETTINGS)
class GoogleCredentialTests(TestCase):
    password = "RakitAkun!729Biru"
    replacement_password = "GantiSandi!938Hijau"

    def google_user(self, *, configured=False, complete=False, **changes):
        values = {
            "username": "repair-member" if configured else "google_pending-member",
            "email": "member@example.com", "first_name": "Nama Anggota",
            "password": self.password if configured else None,
        }
        values.update(changes)
        user = User.objects.create_user(**values)
        Profile.objects.create(
            user=user,
            domicile="Depok" if complete else "",
            birth_date="2003-05-04" if complete else None,
        )
        GoogleIdentity.objects.create(user=user, subject=f"subject-{user.pk}", email=user.email)
        return user

    def verified_session(self, user, *, client=None, marker=None):
        client = client or self.client
        client.force_login(user)
        session = client.session
        session[google_auth.REAUTH_KEY] = marker or {"user_id": user.pk, "time": time.time()}
        session.save()
        return client

    def submit(self, *, client=None, **changes):
        data = {"username": "repair-member", "password": self.password}
        data.update(changes)
        return (client or self.client).post(reverse("accounts:credentials"), data)

    def assert_setup_unchanged(self, user, original_username):
        user.refresh_from_db()
        self.assertEqual(user.username, original_username)
        self.assertFalse(user.has_usable_password())

    def finish_profile_review(self, *, client=None, expected=None):
        client = client or self.client
        response = client.post(reverse("accounts:complete_profile"), {"action": "skip"})
        self.assertRedirects(
            response, expected or reverse("core:landing"), fetch_redirect_response=False,
        )
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, client.session)

    def test_guest_cannot_create_credentials_without_google(self):
        user = self.google_user()
        for method in (self.client.get, self.client.post):
            response = method(reverse("accounts:credentials"), {
                "username": "repair-member", "password": self.password,
            })
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:auth")))
            self.assertNotIn(SESSION_KEY, self.client.session)
        self.assert_setup_unchanged(user, "google_pending-member")

    def test_an_authenticated_session_without_recent_google_proof_cannot_configure(self):
        user = self.google_user()
        self.client.force_login(user)
        response = self.submit()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:auth")))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assert_setup_unchanged(user, "google_pending-member")

    def test_non_google_member_cannot_configure_or_replace_credentials_through_this_endpoint(self):
        user = User.objects.create_user(username="legacy-member", email="legacy@example.com", password=self.password)
        Profile.objects.create(user=user)
        self.verified_session(user)
        response = self.submit(username="replacement-name", password=self.replacement_password)
        self.assertIn(response.status_code, (302, 400))
        user.refresh_from_db()
        self.assertEqual(user.username, "legacy-member")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_expired_future_wrong_user_and_malformed_google_proof_cannot_configure(self):
        user = self.google_user()
        markers = [
            {"user_id": user.pk, "time": time.time() - 600},
            {"user_id": user.pk, "time": time.time() + 600},
            {"user_id": user.pk + 1, "time": time.time()},
            {"user_id": user.pk, "time": "now"},
            {"user_id": user.pk, "time": None},
            {"user_id": user.pk, "time": float("inf")},
            {"user_id": user.pk, "time": True},
            {"user_id": user.pk},
        ]
        for marker in markers:
            with self.subTest(marker=marker):
                self.client = Client()
                self.verified_session(user, marker=marker)
                response = self.submit()
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("accounts:auth")))
                self.assertNotIn(SESSION_KEY, self.client.session)
                self.assert_setup_unchanged(user, "google_pending-member")

    def test_new_member_creates_username_and_hashed_password_then_completes_profile(self):
        user = self.google_user()
        self.verified_session(user)
        response = self.submit(email="attacker@example.com", user_id=user.pk + 1)
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.username, "repair-member")
        self.assertEqual(user.email, "member@example.com")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        self.assertNotIn(self.password, json.dumps(dict(self.client.session.items())))
        self.assertEqual(self.client.get(reverse("accounts:complete_profile")).status_code, 200)
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)

    def test_existing_google_member_without_username_keeps_completed_profile(self):
        user = self.google_user(complete=True)
        self.verified_session(user)
        response = self.submit()
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.domicile, "Depok")
        self.assertEqual(profile.birth_date.isoformat(), "2003-05-04")
        page = self.client.get(reverse("accounts:complete_profile"))
        self.assertEqual(page.context["completion_form"]["username"].value(), "repair-member")
        self.assertEqual(page.context["completion_form"]["domicile"].value(), "Depok")
        self.finish_profile_review()
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_invalid_username_duplicate_and_weak_password_do_not_partially_configure(self):
        user = self.google_user()
        User.objects.create_user(username="taken-member", email="other@example.com", password=self.password)
        self.verified_session(user)
        cases = [
            {"username": "taken-member"}, {"username": "invalid name"},
            {"username": "x" * 151}, {"username": ""},
            {"password": "123"}, {"password": "password"}, {"password": ""},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.client = Client()
                self.verified_session(user)
                self.assertEqual(self.submit(**changes).status_code, 200)
                self.assert_setup_unchanged(user, "google_pending-member")
        self.assertEqual(User.objects.count(), 2)

    def test_credentials_cannot_be_reconfigured_by_replaying_successful_setup(self):
        user = self.google_user(complete=True)
        self.verified_session(user)
        self.submit()
        self.submit(username="replacement-name", password=self.replacement_password)
        user.refresh_from_db()
        self.assertEqual(user.username, "repair-member")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.check_password(self.replacement_password))

    def test_returning_member_uses_existing_credentials_without_replacing_account_or_roles(self):
        user = self.google_user(configured=True, complete=True, is_staff=True)
        group = Group.objects.create(name="existing-role")
        user.groups.add(group)
        original_hash = user.password
        self.verified_session(user)
        response = self.submit()
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertTrue(user.is_staff)
        self.assertEqual(list(user.groups.values_list("pk", flat=True)), [group.pk])
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)
        page = self.client.get(reverse("accounts:complete_profile"))
        self.assertEqual(page.context["completion_form"]["username"].value(), user.username)
        self.assertEqual(page.context["completion_form"]["domicile"].value(), "Depok")
        self.finish_profile_review()
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_returning_member_cannot_switch_to_another_account_or_use_email_as_username(self):
        user = self.google_user(configured=True, complete=True)
        other = User.objects.create_user(username="other-member", email="other@example.com", password=self.password)
        self.verified_session(user)
        for username in (other.username, user.email):
            with self.subTest(username=username):
                response = self.submit(username=username)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
                self.assertRedirects(
                    self.client.get(reverse("core:landing")), reverse("accounts:credentials"),
                    fetch_redirect_response=False,
                )
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)

    def test_wrong_existing_password_blocks_business_pages_until_success(self):
        user = self.google_user(configured=True, complete=True)
        self.verified_session(user)
        self.assertEqual(self.submit(password="wrong-password").status_code, 200)
        for route in ("core:landing", "accounts:profile"):
            with self.subTest(route=route):
                self.assertRedirects(
                    self.client.get(reverse(route)), reverse("accounts:credentials"),
                    fetch_redirect_response=False,
                )
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.finish_profile_review(expected=reverse("accounts:profile"))
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_five_failed_credentials_remain_blocked_across_google_sessions_until_window_resets(self):
        user = self.google_user(configured=True, complete=True)
        self.verified_session(user)
        for _ in range(5):
            self.submit(password="wrong-password")
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        response = self.submit()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:auth")))
        self.assertNotIn(SESSION_KEY, self.client.session)
        fresh_client = Client()
        self.verified_session(user, client=fresh_client)
        response = self.submit(client=fresh_client)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:auth")))
        self.assertNotIn(SESSION_KEY, fresh_client.session)
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.credential_failed_attempts, 5)
        profile.credential_window_started = timezone.now() - timedelta(minutes=16)
        profile.save(update_fields=["credential_window_started"])
        self.verified_session(user, client=fresh_client)
        self.assertRedirects(self.submit(client=fresh_client), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(fresh_client.session[SESSION_KEY], str(user.pk))
        profile.refresh_from_db()
        self.assertEqual(profile.credential_failed_attempts, 0)

    def test_pending_review_cannot_be_skipped_by_credentials_refresh_or_direct_app_url(self):
        user = self.google_user(configured=True, complete=True)
        self.verified_session(user)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        for response in (
            self.client.get(reverse("accounts:credentials")),
            self.submit(username="replacement-name", password=self.replacement_password),
            self.client.get(reverse("core:landing")),
        ):
            self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
            self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)
        user.refresh_from_db()
        self.assertEqual(user.username, "repair-member")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.check_password(self.replacement_password))
        self.finish_profile_review()
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_previously_skipped_member_reviews_existing_preferences_after_each_login(self):
        user = self.google_user(configured=True)
        profile = Profile.objects.get(user=user)
        profile.onboarding_completed = True
        profile.preferred_categories = ["buku", "hobi"]
        profile.save()
        for _ in range(2):
            self.client = Client()
            self.verified_session(user)
            self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
            self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)
            page = self.client.get(reverse("accounts:complete_profile"))
            self.assertEqual(page.context["completion_form"]["username"].value(), user.username)
            self.assertEqual(page.context["completion_form"]["domicile"].value(), "")
            self.assertEqual(page.context["completion_form"]["preferred_categories"].value(), ["buku", "hobi"])
            self.finish_profile_review()
            self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)
            self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
            self.assertEqual(User.objects.count(), 1)

    def test_completion_marker_is_bound_to_the_current_user_and_password_hash(self):
        user = self.google_user(configured=True, complete=True)
        self.verified_session(user)
        self.submit()
        for marker in (
            {"user_id": user.pk + 1, "auth_hash": user.get_session_auth_hash()},
            {"user_id": user.pk, "auth_hash": "forged-password-hash"},
        ):
            with self.subTest(marker=marker):
                session = self.client.session
                session[google_auth.CREDENTIALS_KEY] = marker
                session.save()
                self.assertRedirects(
                    self.client.get(reverse("core:landing")), reverse("accounts:credentials"),
                    fetch_redirect_response=False,
                )

    def test_form_post_requires_csrf_even_with_recent_google_authentication(self):
        user = self.google_user()
        client = Client(enforce_csrf_checks=True)
        self.verified_session(user, client=client)
        self.assertEqual(self.submit(client=client).status_code, 403)
        self.assert_setup_unchanged(user, "google_pending-member")
        self.assertEqual(client.get(reverse("accounts:credentials")).status_code, 200)
        response = self.submit(client=client, csrfmiddlewaretoken=client.cookies["csrftoken"].value)
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)


@override_settings(**GOOGLE_SETTINGS)
class PublicEntryAndLegalTests(TestCase):
    def test_guest_homepage_and_legal_urls_are_public_without_google_session(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, reverse("accounts:google_login"))
        self.assertContains(home, "/terms/")
        self.assertContains(home, 'href="/privacy/"')
        self.assertContains(home, 'id="public-app-name">RePair</h2>')
        self.assertContains(home, 'id="tentang-repair"')
        self.assertContains(home, 'href="/terms/">Syarat &amp; Ketentuan dan Kebijakan Privasi.</a>')
        self.assertNotContains(home, "brand-public-links")
        self.assertNotContains(home, 'href="#tentang-repair"')
        for url in ("/terms/", "/privacy/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "16 Oktober 2026" if url == "/privacy/" else "9 Oktober 2026")
                self.assertContains(response, "RePair")
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_incomplete_google_member_can_read_legal_pages_without_credentials(self):
        user = User.objects.create_user(username="google_public-member", email="public@example.com", password=None)
        Profile.objects.create(user=user)
        GoogleIdentity.objects.create(user=user, subject="public-subject", email=user.email)
        self.client.force_login(user)
        for url in ("/terms/", "/privacy/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
