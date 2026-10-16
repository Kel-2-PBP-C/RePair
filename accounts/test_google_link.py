import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from joserfc.jwk import RSAKey

from . import google_auth, test_google_auth as oidc
from .models import GoogleAccountLinkChallenge, GoogleIdentity, Profile

User = get_user_model()


@override_settings(**oidc.GOOGLE_SETTINGS)
class GoogleAccountLinkTests(TestCase):
    password = " old-password!729 "
    metadata_url = oidc.GoogleOIDCTests.metadata_url
    token_url = oidc.GoogleOIDCTests.token_url
    jwks_url = oidc.GoogleOIDCTests.jwks_url
    setUp = oidc.GoogleOIDCTests.setUp
    google_transport = oidc.GoogleOIDCTests.google_transport
    begin = oidc.GoogleOIDCTests.begin
    issue_token = oidc.GoogleOIDCTests.issue_token
    callback = oidc.GoogleOIDCTests.callback
    assert_storage_unavailable = oidc.GoogleOIDCTests.assert_storage_unavailable
    assert_stored_sessions_unauthenticated = oidc.GoogleOIDCTests.assert_stored_sessions_unauthenticated

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signing_key = RSAKey.generate_key(2048, {"kid": "google-test-key"})
        cls.untrusted_key = RSAKey.generate_key(2048, {"kid": "google-test-key"})

    def legacy_user(self, complete=True, **changes):
        values = {
            "username": "legacy-member", "email": "MEMBER@example.com",
            "password": self.password, "first_name": "Nama Lama", "last_name": "Tetap",
            "is_staff": True,
        }
        values.update(changes)
        user = User.objects.create_user(**values)
        Profile.objects.create(
            user=user, domicile="Bandung" if complete else "",
            birth_date="2001-01-01" if complete else None,
            social_contact="@legacy", email_notifications=False, language="en",
        )
        return user

    def challenge(self, client=None, **query):
        client = client or self.client
        _, context = self.begin(client=client, **query)
        self.issue_token(context)
        response = self.callback(context, client=client)
        self.assertRedirects(response, reverse("accounts:google_link"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, client.session)
        self.assertFalse(GoogleIdentity.objects.exists())
        return GoogleAccountLinkChallenge.objects.get(), dict(client.session[google_auth.LINK_SESSION_KEY])

    def submit(self, client=None, **changes):
        data = {"username": "legacy-member", "password": self.password, "confirm": "on"}
        data.update(changes)
        return (client or self.client).post(reverse("accounts:google_link"), data)

    def assert_not_linked(self, response, client=None):
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn(SESSION_KEY, (client or self.client).session)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_verified_google_callback_requires_old_password_before_preserving_original_account(self):
        user = self.legacy_user()
        group = Group.objects.create(name="legacy-role")
        user.groups.add(group)
        profile = Profile.objects.get(user=user)
        original_password_hash = user.password
        proof, session_data = self.challenge(next="/accounts/profile/?tab=settings#settings")
        before_login_key = self.client.session.session_key
        self.assertEqual(proof.user_id, user.pk)
        self.assertEqual(proof.subject, "google-subject-123")
        self.assertEqual(proof.email, "member@example.com")
        self.assertNotEqual(proof.token_digest, session_data["key"])
        self.assertEqual(proof.token_digest, google_auth.digest(session_data["key"]))
        self.assertEqual(proof.session_digest, google_auth.digest(before_login_key))
        self.assertIsNone(proof.consumed_at)
        self.assertEqual(set(session_data), {"key", "next"})
        serialized = json.dumps(dict(self.client.session.items()))
        for secret in ("google-subject-123", user.email, "test-access-token", self.token_payload["id_token"]):
            self.assertNotIn(secret, serialized)
        page = self.client.get(reverse("accounts:google_link"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="username"')
        self.assertContains(page, 'name="password"')
        self.assertContains(page, 'name="confirm"')
        response = self.submit()
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], session_data["next"])
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertNotEqual(self.client.session.session_key, before_login_key)
        self.assertFalse(Session.objects.filter(session_key=before_login_key).exists())
        self.assertNotIn(google_auth.LINK_SESSION_KEY, self.client.session)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        self.assertEqual(User.objects.count(), 1)
        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(user.password, original_password_hash)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.get_full_name(), "Nama Lama Tetap")
        self.assertTrue(user.is_staff)
        self.assertEqual(list(user.groups.values_list("pk", flat=True)), [group.pk])
        self.assertEqual(profile.domicile, "Bandung")
        self.assertEqual(profile.social_contact, "@legacy")
        self.assertFalse(profile.email_notifications)
        self.assertEqual(profile.language, "en")
        page = self.client.get(reverse("accounts:complete_profile"))
        self.assertEqual(page.context["completion_form"]["username"].value(), user.username)
        self.assertEqual(page.context["completion_form"]["domicile"].value(), "Bandung")
        self.assertRedirects(
            self.client.get(reverse("core:landing")), reverse("accounts:complete_profile"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("accounts:credentials")), reverse("accounts:complete_profile"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.post(reverse("accounts:complete_profile"), {"action": "skip"}),
            session_data["next"], fetch_redirect_response=False,
        )
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_linked_legacy_user_without_complete_profile_goes_through_onboarding(self):
        user = self.legacy_user(complete=False)
        self.challenge(next=reverse("accounts:profile"))
        response = self.submit()
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(self.client.session["google_profile_next"], reverse("accounts:profile"))
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], user.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_wrong_password_is_recorded_without_linking_and_correct_retry_succeeds(self):
        user = self.legacy_user()
        proof, _ = self.challenge()
        response = self.submit(password="wrong-password")
        self.assertEqual(response.status_code, 200)
        self.assert_not_linked(response)
        proof.refresh_from_db()
        self.assertEqual(proof.failed_attempts, 1)
        self.assertIsNone(proof.consumed_at)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_confirmation_and_password_are_required_before_a_password_attempt(self):
        self.legacy_user()
        proof, _ = self.challenge()
        for data in (
            {"username": "legacy-member", "password": self.password},
            {"username": "legacy-member", "confirm": "on"},
            {"password": self.password, "confirm": "on"},
            {},
        ):
            with self.subTest(data=data):
                response = self.client.post(reverse("accounts:google_link"), data)
                self.assertEqual(response.status_code, 200)
                self.assert_not_linked(response)
                proof.refresh_from_db()
                self.assertEqual(proof.failed_attempts, 0)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)

    def test_link_requires_the_verified_legacy_username_and_cannot_switch_accounts(self):
        user = self.legacy_user()
        other = User.objects.create_user(username="other-member", email="other@example.com", password=self.password)
        proof, _ = self.challenge()
        for username in (other.username, user.email):
            with self.subTest(username=username):
                self.assert_not_linked(self.submit(username=username))
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)

    def test_get_and_post_without_verified_google_proof_do_not_offer_password_login(self):
        self.legacy_user()
        for method in (self.client.get, self.client.post):
            response = method(reverse("accounts:google_link"), {"password": self.password, "confirm": "on"})
            self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
            self.assert_not_linked(response)
        self.assertFalse(GoogleAccountLinkChallenge.objects.exists())

    def test_expired_google_proof_cannot_link(self):
        self.legacy_user()
        proof, _ = self.challenge()
        proof.expires_at = timezone.now() - timedelta(seconds=1)
        proof.save(update_fields=["expires_at"])
        self.assert_not_linked(self.submit())

    def test_stolen_opaque_proof_in_another_browser_cannot_link_or_revoke_its_owner(self):
        user = self.legacy_user()
        proof, session_data = self.challenge()
        stranger = Client()
        session = stranger.session
        session[google_auth.LINK_SESSION_KEY] = session_data
        session.save()
        self.assert_not_linked(self.submit(client=stranger), client=stranger)
        proof.refresh_from_db()
        self.assertIsNone(proof.consumed_at)
        self.assertEqual(proof.failed_attempts, 0)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_malformed_or_tampered_session_proof_is_rejected(self):
        self.legacy_user()
        for value in (None, "forged", {}, {"key": "forged", "next": "/"}, {"key": 1}):
            with self.subTest(value=value):
                self.client = Client()
                self.challenge()
                session = self.client.session
                session[google_auth.LINK_SESSION_KEY] = value
                session.save()
                self.assert_not_linked(self.submit())

    def test_posted_user_email_subject_and_destination_cannot_change_verified_proof(self):
        user = self.legacy_user()
        other = User.objects.create_user(username="unrelated", email="other@example.com", password=self.password)
        self.challenge(next=reverse("accounts:profile"))
        response = self.submit(
            user_id=other.pk, email=other.email, subject="attacker-subject", key="forged",
            next="https://attacker.example/steal",
        )
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], reverse("accounts:profile"))
        identity = GoogleIdentity.objects.get()
        self.assertEqual(identity.user_id, user.pk)
        self.assertEqual(identity.email, "member@example.com")
        self.assertEqual(identity.subject, "google-subject-123")

    def test_session_destination_is_rechecked_before_link_success(self):
        self.legacy_user()
        self.challenge(next=reverse("accounts:profile"))
        session = self.client.session
        session[google_auth.LINK_SESSION_KEY]["next"] = "https://attacker.example/steal"
        session.save()
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertRedirects(
            self.client.post(reverse("accounts:complete_profile"), {"action": "skip"}),
            reverse("core:landing"), fetch_redirect_response=False,
        )

    def test_link_page_is_not_a_permitted_post_login_destination(self):
        self.legacy_user()
        self.challenge(next=reverse("accounts:google_link"))
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertRedirects(
            self.client.post(reverse("accounts:complete_profile"), {"action": "skip"}),
            reverse("core:landing"), fetch_redirect_response=False,
        )

    def test_consumed_proof_replay_cannot_authenticate_restored_browser_snapshot(self):
        user = self.legacy_user()
        proof, _ = self.challenge()
        old_key = self.client.session.session_key
        old_data = dict(self.client.session.items())
        self.submit()
        restored = Client()
        Session.objects.create(
            session_key=old_key, session_data=SessionStore().encode(old_data),
            expire_date=timezone.now() + timedelta(minutes=10),
        )
        restored.cookies[settings.SESSION_COOKIE_NAME] = old_key
        response = self.submit(client=restored)
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn(SESSION_KEY, restored.session)
        self.assertEqual(GoogleIdentity.objects.count(), 1)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)

    def test_email_change_after_google_verification_prevents_linking(self):
        user = self.legacy_user()
        self.challenge()
        user.email = "new@example.com"
        user.save(update_fields=["email"])
        self.assert_not_linked(self.submit())

    def test_deactivation_after_google_verification_prevents_linking(self):
        user = self.legacy_user()
        self.challenge()
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assert_not_linked(self.submit())

    def test_duplicate_email_added_after_google_verification_prevents_linking(self):
        self.legacy_user()
        self.challenge()
        User.objects.create_user(username="same-email", email="member@EXAMPLE.COM", password="another")
        self.assert_not_linked(self.submit())

    def test_password_disabled_after_google_verification_prevents_linking(self):
        user = self.legacy_user()
        self.challenge()
        user.set_unusable_password()
        user.save(update_fields=["password"])
        self.assert_not_linked(self.submit())

    def test_changed_password_is_rechecked_from_database_before_linking(self):
        user = self.legacy_user()
        self.challenge()
        user.set_password("replacement-password")
        user.save(update_fields=["password"])
        self.assert_not_linked(self.submit())
        response = self.submit(password="replacement-password")
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_user_linked_to_another_google_identity_while_proof_pending_is_not_replaced(self):
        user = self.legacy_user()
        self.challenge()
        identity = GoogleIdentity.objects.create(user=user, subject="other-google", email="other@example.com")
        response = self.submit()
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn(SESSION_KEY, self.client.session)
        identity.refresh_from_db()
        self.assertEqual(identity.subject, "other-google")
        self.assertEqual(identity.email, "other@example.com")

    def test_google_subject_taken_by_another_user_while_proof_pending_does_not_switch_accounts(self):
        self.legacy_user()
        self.challenge()
        other = User.objects.create_user(username="other-google", email="other@example.com", password=None)
        GoogleIdentity.objects.create(user=other, subject="google-subject-123", email=other.email)
        response = self.submit()
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(GoogleIdentity.objects.count(), 1)
        self.assertEqual(GoogleIdentity.objects.get().user_id, other.pk)

    def test_callback_does_not_offer_link_for_inactive_unusable_or_ambiguous_legacy_accounts(self):
        user = self.legacy_user()
        for case in ("inactive", "unusable", "ambiguous"):
            with self.subTest(case=case):
                self.client = Client()
                user.is_active = case != "inactive"
                user.set_password(self.password)
                if case == "unusable":
                    user.set_unusable_password()
                user.save(update_fields=["is_active", "password"])
                if case == "ambiguous":
                    User.objects.create_user(username="duplicate", email="member@example.com", password="another")
                _, context = self.begin()
                self.issue_token(context)
                response = self.callback(context)
                self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
                self.assert_not_linked(response)
                self.assertNotIn(google_auth.LINK_SESSION_KEY, self.client.session)
                self.assertFalse(GoogleAccountLinkChallenge.objects.exists())

    def test_five_failed_passwords_remain_blocked_across_fresh_google_sessions_and_browsers(self):
        self.legacy_user()
        original_pk = None
        for attempt in range(1, 6):
            self.client = Client()
            proof, _ = self.challenge()
            original_pk = original_pk or proof.pk
            self.assertEqual(proof.pk, original_pk)
            self.assert_not_linked(self.submit(password="wrong"))
            proof.refresh_from_db()
            self.assertEqual(proof.failed_attempts, attempt)
        self.client = Client()
        _, context = self.begin()
        self.issue_token(context)
        response = self.callback(context)
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assert_not_linked(response)
        proof.refresh_from_db()
        self.assertEqual(proof.failed_attempts, 5)
        self.assertNotIn(google_auth.LINK_SESSION_KEY, self.client.session)
        proof.window_started = timezone.now() - timedelta(minutes=16)
        proof.save(update_fields=["window_started"])
        proof, _ = self.challenge()
        self.assertEqual(proof.failed_attempts, 0)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)

    def test_password_attempt_window_resets_after_fifteen_minutes(self):
        user = self.legacy_user()
        proof, _ = self.challenge()
        proof.failed_attempts = 5
        proof.window_started = timezone.now() - timedelta(minutes=16)
        proof.save(update_fields=["failed_attempts", "window_started"])
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_cancel_revokes_proof_and_requires_new_google_verification(self):
        self.legacy_user()
        proof, _ = self.challenge()
        response = self.client.post(reverse("accounts:google_link"), {"action": "cancel"})
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(google_auth.LINK_SESSION_KEY, self.client.session)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)
        self.assert_not_linked(self.submit())

    def test_new_google_start_revokes_pending_link_proof(self):
        self.legacy_user()
        proof, _ = self.challenge()
        self.begin()
        self.assertNotIn(google_auth.LINK_SESSION_KEY, self.client.session)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)
        self.assert_not_linked(self.submit())

    def test_new_verified_challenge_invalidates_prior_browser_proof(self):
        user = self.legacy_user()
        _, prior_data = self.challenge()
        prior_browser = self.client
        self.client = Client()
        proof, new_data = self.challenge()
        self.assertNotEqual(prior_data["key"], new_data["key"])
        self.assert_not_linked(self.submit(client=prior_browser), client=prior_browser)
        proof.refresh_from_db()
        self.assertIsNone(proof.consumed_at)
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_account_link_form_and_cancel_require_csrf(self):
        user = self.legacy_user()
        client = Client(enforce_csrf_checks=True)
        proof, _ = self.challenge(client=client)
        for data in ({"password": self.password, "confirm": "on"}, {"action": "cancel"}):
            self.assertEqual(client.post(reverse("accounts:google_link"), data).status_code, 403)
        proof.refresh_from_db()
        self.assertIsNone(proof.consumed_at)
        self.assertEqual(proof.failed_attempts, 0)
        self.assertEqual(client.get(reverse("accounts:google_link")).status_code, 200)
        token = client.cookies["csrftoken"].value
        response = self.submit(client=client, csrfmiddlewaretoken=token)
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(client.session[SESSION_KEY], str(user.pk))

    def test_identity_write_failure_rolls_back_consumption_for_a_safe_retry(self):
        user = self.legacy_user()
        proof, _ = self.challenge()
        with patch("accounts.google_auth.GoogleIdentity.objects.create", side_effect=DatabaseError("test write failure")):
            self.assert_storage_unavailable(self.submit())
        proof.refresh_from_db()
        self.assertIsNone(proof.consumed_at)
        self.assertFalse(GoogleIdentity.objects.exists())
        self.assertEqual(User.objects.count(), 1)
        self.challenge()
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)

    def test_session_store_failure_preserves_valid_link_without_authenticated_success(self):
        user = self.legacy_user()
        proof, _ = self.challenge()
        original_save = SessionStore.save
        failed = False

        def fail_authenticated_save(store, *args, **kwargs):
            nonlocal failed
            if SESSION_KEY in store and not failed:
                failed = True
                raise DatabaseError("test session persistence failure")
            return original_save(store, *args, **kwargs)

        with patch.object(SessionStore, "save", fail_authenticated_save):
            self.assert_storage_unavailable(self.submit())
        self.assertTrue(failed)
        self.assert_stored_sessions_unauthenticated()
        proof.refresh_from_db()
        self.assertIsNotNone(proof.consumed_at)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        self.assertEqual(User.objects.count(), 1)
        _, context = self.begin()
        self.issue_token(context)
        response = self.callback(context)
        self.assertRedirects(response, reverse("accounts:credentials"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_normal_password_endpoints_remain_blocked_for_a_linked_legacy_account(self):
        self.legacy_user()
        self.challenge()
        self.submit()
        self.client.post(reverse("accounts:logout"))
        for route in ("auth", "login", "register"):
            response = self.client.post(reverse(f"accounts:{route}"), {
                "username": "legacy-member", "password": self.password,
                "mode": "register", "password1": self.password, "password2": self.password,
            })
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(GoogleIdentity.objects.count(), 1)

    @override_settings(GOOGLE_ALLOW_REGISTRATION=False)
    def test_disabled_registration_still_allows_verified_link_to_existing_legacy_account(self):
        user = self.legacy_user()
        self.challenge()
        self.assertRedirects(self.submit(), reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(User.objects.count(), 1)
