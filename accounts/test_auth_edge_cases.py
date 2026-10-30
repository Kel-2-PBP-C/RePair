"""Authentication boundaries and recovery from concurrent writes or outages."""

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from requests.exceptions import RequestException

from . import google_auth
from .forms import GoogleCredentialsForm
from .models import GoogleAccountLinkChallenge, GoogleIdentity, GoogleLoginAttempt, Profile
from .test_google_auth import GOOGLE_SETTINGS


User = get_user_model()


@override_settings(**GOOGLE_SETTINGS)
class GoogleConfigurationTests(SimpleTestCase):
    def test_callback_configuration_only_allows_https_or_local_development(self):
        cases = (
            ("https://repair.example/accounts/google/callback/", True, True),
            ("http://localhost/accounts/google/callback/", False, True),
            ("http://127.0.0.1:8000/accounts/google/callback/", False, True),
            ("http://localhost/accounts/google/callback/", True, False),
            ("http://repair.example/accounts/google/callback/", False, False),
            ("https://repair.example/wrong/", False, False),
            ("https://ops@repair.example/accounts/google/callback/", False, False),
            ("https://repair.example/accounts/google/callback/?next=/", False, False),
            ("https://repair.example/accounts/google/callback/#fragment", False, False),
            ("/accounts/google/callback/", False, False),
        )
        for uri, production, expected in cases:
            with self.subTest(uri=uri, production=production):
                with override_settings(GOOGLE_REDIRECT_URI=uri, PRODUCTION=production):
                    self.assertEqual(google_auth.configured(), expected)

    def test_missing_client_credentials_disable_google_login(self):
        for field in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
            with self.subTest(field=field), override_settings(**{field: ""}):
                self.assertFalse(google_auth.configured())


@override_settings(**GOOGLE_SETTINGS)
class GoogleAuthenticationBoundaryTests(TestCase):
    password = "RakitAkun!729Biru"

    def make_request(self, *, user=None):
        request = RequestFactory().get(reverse("accounts:google_login"))
        request.user = user or AnonymousUser()
        request.session = SessionStore()
        request.session.create()
        return request

    def make_user(self, *, google=False, usable=True):
        user = User.objects.create_user(
            username="member", email="member@example.com",
            password=self.password if usable else None,
        )
        Profile.objects.create(user=user)
        if google:
            GoogleIdentity.objects.create(user=user, subject="subject-member", email=user.email)
        return user

    def test_login_limit_is_per_session_and_rejects_provider_call(self):
        request = self.make_request()
        now = timezone.now()
        GoogleLoginAttempt.objects.bulk_create([
            GoogleLoginAttempt(
                state_digest=google_auth.digest(f"state-{index}"),
                session_digest=google_auth.digest(request.session.session_key),
                expires_at=now + timedelta(minutes=10),
            )
            for index in range(10)
        ])

        with patch("accounts.google_auth.get_google_client") as provider:
            with self.assertRaisesMessage(google_auth.GoogleLoginError, "Terlalu banyak"):
                google_auth.begin_login(request, "/landing/")

        provider.assert_not_called()
        self.assertNotIn(google_auth.TRANSACTION_KEY, request.session)
        self.assertEqual(GoogleLoginAttempt.objects.count(), 10)

    def test_new_login_removes_expired_attempts_and_only_google_session_state(self):
        request = self.make_request()
        request.session["_state_google_old"] = {"private": "old-provider-state"}
        request.session["_state_other_provider"] = {"keep": True}
        request.session[google_auth.TRANSACTION_KEY] = {"state": "old"}
        GoogleLoginAttempt.objects.create(
            state_digest=google_auth.digest("expired"), session_digest="other-browser",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        provider = Mock()
        provider.authorize_redirect.return_value = HttpResponseRedirect("https://accounts.google.com/")

        with patch("accounts.google_auth.get_google_client", return_value=provider):
            response = google_auth.begin_login(request, "/landing/")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_state_google_old", request.session)
        self.assertEqual(request.session["_state_other_provider"], {"keep": True})
        self.assertNotEqual(request.session[google_auth.TRANSACTION_KEY]["state"], "old")
        self.assertFalse(GoogleLoginAttempt.objects.filter(state_digest=google_auth.digest("expired")).exists())
        self.assertEqual(GoogleLoginAttempt.objects.count(), 1)

    def test_account_creation_handles_nontext_names_and_caps_provider_name_length(self):
        for index, name in enumerate((None, {"unexpected": "object"}, "  " + "A" * 200 + "  ")):
            with self.subTest(name_type=type(name).__name__):
                user = google_auth.account_for_claims({
                    "subject": f"subject-{index}", "email": f"user{index}@example.com", "name": name,
                })
                self.assertEqual(user.first_name, "A" * 150 if isinstance(name, str) else "")
                self.assertFalse(user.has_usable_password())
                self.assertEqual(user.google_identity.email, user.email)
                self.assertFalse(user.profile.onboarding_completed)

    def test_concurrent_identity_creation_returns_existing_subject_owner(self):
        user = self.make_user(google=True)
        # The first lookup represents the snapshot before the other request commits.
        lookup_results = [GoogleIdentity.objects.none(), GoogleIdentity.objects.select_related("user")]
        with patch.object(GoogleIdentity.objects, "select_related", side_effect=lookup_results), patch.object(
            User.objects, "create_user", side_effect=IntegrityError("concurrent registration"),
        ):
            resolved = google_auth.account_for_claims({
                "subject": "subject-member", "email": "new-provider-address@example.com", "name": "Member",
            })
        self.assertEqual(resolved.pk, user.pk)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(GoogleIdentity.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)

    def test_link_cannot_start_after_user_is_removed_or_loses_eligibility(self):
        user = self.make_user()
        claims = {"subject": "subject-member", "email": user.email}
        for user_id in (user.pk + 1, user.pk):
            with self.subTest(user_id=user_id):
                User.objects.filter(pk=user.pk).update(is_active=False)
                request = self.make_request()
                with self.assertRaisesMessage(google_auth.GoogleLoginError, "belum dapat ditautkan"):
                    google_auth.begin_account_link(request, user_id, claims, "/landing/")
                self.assertNotIn(google_auth.LINK_SESSION_KEY, request.session)
                self.assertFalse(GoogleAccountLinkChallenge.objects.exists())

    def test_complete_link_rechecks_expiry_and_consumption_after_page_was_opened(self):
        user = self.make_user()
        request = self.make_request()
        google_auth.begin_account_link(
            request, user.pk, {"subject": "subject-member", "email": user.email}, "/landing/",
        )
        challenge = GoogleAccountLinkChallenge.objects.get(user=user)
        self.assertIsNotNone(google_auth.get_account_link_challenge(request))

        for change in (
            {"expires_at": timezone.now() - timedelta(seconds=1)},
            {"expires_at": timezone.now() + timedelta(minutes=5), "consumed_at": timezone.now()},
        ):
            with self.subTest(change=list(change)):
                GoogleAccountLinkChallenge.objects.filter(pk=challenge.pk).update(**change)
                with self.assertRaisesMessage(google_auth.GoogleLoginError, "dipakai atau kedaluwarsa"):
                    google_auth.complete_account_link(request, self.password, user.username)
                self.assertFalse(GoogleIdentity.objects.exists())
        challenge.refresh_from_db()
        self.assertEqual(challenge.failed_attempts, 0)

    def test_complete_link_without_a_challenge_never_authenticates(self):
        request = self.make_request()
        with self.assertRaisesMessage(google_auth.GoogleLoginError, "Sesi penautan tidak valid"):
            google_auth.complete_account_link(request, self.password, "member")
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_link_attempt_limit_is_checked_again_when_a_form_is_submitted(self):
        user = self.make_user()
        request = self.make_request()
        google_auth.begin_account_link(
            request, user.pk, {"subject": "subject-member", "email": user.email}, "/landing/",
        )
        GoogleAccountLinkChallenge.objects.filter(user=user).update(failed_attempts=5)

        with self.assertRaisesMessage(google_auth.GoogleLoginError, "Terlalu banyak"):
            google_auth.complete_account_link(request, self.password, user.username)

        challenge = GoogleAccountLinkChallenge.objects.get(user=user)
        self.assertEqual(challenge.failed_attempts, 5)
        self.assertIsNone(challenge.consumed_at)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_identity_collision_rolls_back_link_consumption_and_attempt_counter(self):
        user = self.make_user()
        request = self.make_request()
        google_auth.begin_account_link(
            request, user.pk, {"subject": "subject-member", "email": user.email}, "/landing/",
        )

        with patch.object(GoogleIdentity.objects, "create", side_effect=IntegrityError("concurrent identity")):
            with self.assertRaisesMessage(google_auth.GoogleLoginError, "berbenturan"):
                google_auth.complete_account_link(request, self.password, user.username)

        challenge = GoogleAccountLinkChallenge.objects.get(user=user)
        self.assertEqual(challenge.failed_attempts, 0)
        self.assertIsNone(challenge.consumed_at)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_user_deleted_between_link_snapshot_and_lock_returns_safe_error(self):
        user = self.make_user()
        request = self.make_request()
        google_auth.begin_account_link(
            request, user.pk, {"subject": "subject-member", "email": user.email}, "/landing/",
        )
        with patch.object(User.objects, "select_for_update") as locked:
            locked.return_value.get.side_effect = User.DoesNotExist
            with self.assertRaisesMessage(google_auth.GoogleLoginError, "belum dapat ditautkan"):
                google_auth.complete_account_link(request, self.password, user.username)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_credentials_marker_rejects_malformed_and_foreign_hashes(self):
        user = self.make_user(google=True)
        request = self.make_request(user=user)
        for marker in (None, [], "complete", {}, {"user_id": user.pk, "auth_hash": 123},
                       {"user_id": user.pk, "auth_hash": "non-ascii-\u00e9"},
                       {"user_id": user.pk, "auth_hash": "wrong"}):
            with self.subTest(marker=marker):
                request.session[google_auth.CREDENTIALS_KEY] = marker
                self.assertFalse(google_auth.credentials_complete(request))
        google_auth.mark_credentials_complete(request)
        self.assertTrue(google_auth.credentials_complete(request))
        request.user = AnonymousUser()
        self.assertFalse(google_auth.credentials_complete(request))

    def test_recent_auth_rejects_non_mapping_markers_and_nan(self):
        request = self.make_request(user=self.make_user())
        for marker in ([], "recent", None, {"user_id": request.user.pk, "time": float("nan")}):
            with self.subTest(marker=marker):
                request.session[google_auth.REAUTH_KEY] = marker
                self.assertFalse(google_auth.recent_google_auth(request))


@override_settings(**GOOGLE_SETTINGS)
class AccountViewRecoveryTests(TestCase):
    password = "RakitAkun!729Biru"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="member", email="member@example.com", password=cls.password, first_name="Member",
        )
        cls.profile = Profile.objects.create(user=cls.user, domicile="Depok", birth_date="2003-05-04")

    def sign_in(self, *, google=False, credentials=True):
        if google:
            GoogleIdentity.objects.create(user=self.user, subject="subject-member", email=self.user.email)
        self.client.force_login(self.user)
        session = self.client.session
        session[google_auth.REAUTH_KEY] = {"user_id": self.user.pk, "time": time.time()}
        if credentials:
            google_auth.mark_credentials_complete(SimpleNamespace(user=self.user, session=session))
        session.save()

    def test_guest_auth_page_renders_google_configuration_and_safe_destination(self):
        response = self.client.get(reverse("accounts:auth"), {"next": "/posts/?sort=newest"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/auth.html")
        self.assertTrue(response.context["google_configured"])
        self.assertEqual(response.context["next_url"], "/posts/?sort=newest")

    def test_google_only_legacy_get_redirect_preserves_safe_destination(self):
        from urllib.parse import parse_qs, urlsplit

        for endpoint in ("login", "register"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(reverse(f"accounts:{endpoint}"), {"next": "/posts/"})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.url).path, reverse("accounts:auth"))
                self.assertEqual(parse_qs(urlsplit(response.url).query), {"next": ["/posts/"]})

    @override_settings(GOOGLE_ONLY_AUTH=False)
    def test_legacy_get_redirect_preserves_mode_and_sanitizes_destination(self):
        from urllib.parse import parse_qs, urlsplit

        for endpoint in ("login", "register"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(reverse(f"accounts:{endpoint}"), {"next": "https://external.example/"})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.url).path, reverse("accounts:auth"))
                self.assertEqual(parse_qs(urlsplit(response.url).query), {
                    "mode": [endpoint], "next": [reverse("core:landing")],
                })

    def test_google_start_network_error_returns_safe_feedback_and_clears_state(self):
        session = self.client.session
        session[google_auth.TRANSACTION_KEY] = {"state": "stale"}
        session["_state_google_old"] = {"private": "hidden"}
        session.save()
        with patch("accounts.google_auth.begin_login", side_effect=RequestException("private-provider-message")):
            with self.assertLogs("accounts.views", level="WARNING") as captured:
                response = self.client.get(reverse("accounts:google_login"))
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(google_auth.TRANSACTION_KEY, self.client.session)
        self.assertNotIn("_state_google_old", self.client.session)
        self.assertIn("stage=start", captured.output[0])
        self.assertNotIn("private-provider-message", " ".join(captured.output))

    def test_google_start_storage_error_expires_browser_session(self):
        with patch("accounts.google_auth.begin_login", side_effect=DatabaseError("private-db-error")):
            with self.assertLogs("accounts.views", level="WARNING"):
                response = self.client.get(reverse("accounts:google_login"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.cookies["sessionid"]["max-age"], 0)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotContains(response, "private-db-error", status_code=503)

    def test_signed_in_google_endpoints_without_reauth_preserve_existing_session(self):
        self.sign_in()
        with patch("accounts.google_auth.begin_login") as begin, patch("accounts.google_auth.consume_login") as consume:
            for endpoint, target in (("google_login", "core:landing"), ("google_callback", "core:landing"),
                                     ("google_link", "accounts:profile"), ("auth", "core:landing")):
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(reverse(f"accounts:{endpoint}"))
                    self.assertRedirects(response, reverse(target), fetch_redirect_response=False)
            begin.assert_not_called()
            consume.assert_not_called()
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    @override_settings(GOOGLE_ONLY_AUTH=False)
    def test_registration_username_race_returns_form_error_without_authentication(self):
        data = {
            "mode": "register", "username": "new-member", "full_name": "New Member",
            "email": "new@example.com", "domicile": "Depok", "birth_date": "2003-05-04",
            "password1": self.password, "password2": self.password,
        }
        with patch("accounts.views.RegistrationForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("accounts:auth"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["auth_form"].errors)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertFalse(User.objects.filter(username="new-member").exists())

    def test_profile_username_race_keeps_database_and_displays_field_error(self):
        self.sign_in()
        with patch("accounts.views.ProfileForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "profile", "username": "updated", "full_name": "Updated",
                "email": "member@example.com", "domicile": "Bandung", "birth_date": "2003-05-04",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "member")
        self.assertEqual(self.profile.domicile, "Depok")

    def test_onboarding_username_race_retains_pending_review(self):
        self.sign_in(google=True)
        session = self.client.session
        session[google_auth.PROFILE_REVIEW_KEY] = self.user.pk
        session.save()
        with patch("accounts.views.GoogleProfileCompletionForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("accounts:complete_profile"), {
                "username": "updated", "domicile": "Bandung", "preferred_categories": ["buku"],
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["completion_form"].errors)
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "member")

    def test_legacy_user_onboarding_redirects_to_profile_without_changes(self):
        self.sign_in()
        response = self.client.post(reverse("accounts:complete_profile"), {"action": "skip"})
        self.assertRedirects(response, reverse("accounts:profile"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.onboarding_completed)

    def test_password_database_failure_preserves_password_and_session(self):
        self.sign_in()
        with patch.object(User, "save", side_effect=DatabaseError("write unavailable")):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "password", "old_password": self.password,
                "new_password1": "NewSecret!764Orange", "new_password2": "NewSecret!764Orange",
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["password_form"].non_field_errors())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_delete_revalidation_failure_preserves_account_and_reports_error(self):
        self.sign_in()
        with patch("accounts.views.permanently_delete_account", side_effect=ValidationError("Verifikasi ulang diperlukan.")):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "delete", "password": self.password, "confirm": "on",
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["deactivate_form"].non_field_errors())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_credential_setup_username_race_does_not_mark_session_complete(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        self.sign_in(google=True, credentials=False)
        with patch.object(User, "save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("accounts:credentials"), {
                "username": "updated", "password": self.password,
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["credentials_form"].errors)
        self.assertNotIn(google_auth.CREDENTIALS_KEY, self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())
        self.assertEqual(self.user.username, "member")

    def test_credential_storage_failure_clears_browser_identity(self):
        self.sign_in(google=True, credentials=False)
        with patch.object(Profile, "save", side_effect=DatabaseError("write unavailable")):
            with self.assertLogs("accounts.views", level="WARNING"):
                response = self.client.post(reverse("accounts:credentials"), {
                    "username": self.user.username, "password": self.password,
                })
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotIn(google_auth.CREDENTIALS_KEY, response.wsgi_request.session)
        self.assertEqual(response.cookies["sessionid"]["max-age"], 0)

    def test_credential_submission_rechecks_activation_after_form_validation(self):
        self.sign_in(google=True, credentials=False)
        original_validate = GoogleCredentialsForm.is_valid

        def deactivate_after_validation(form):
            valid = original_validate(form)
            User.objects.filter(pk=self.user.pk).update(is_active=False)
            return valid

        with patch.object(GoogleCredentialsForm, "is_valid", deactivate_after_validation):
            response = self.client.post(reverse("accounts:credentials"), {
                "username": self.user.username, "password": self.password,
            })

        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn(google_auth.CREDENTIALS_KEY, self.client.session)

    def test_concurrent_credential_setup_preserves_first_password_and_requires_new_login(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        self.sign_in(google=True, credentials=False)
        original_validate = GoogleCredentialsForm.is_valid
        concurrent_password = "ConcurrentSecret!743Green"

        def configure_after_validation(form):
            valid = original_validate(form)
            User.objects.filter(pk=self.user.pk).update(password=make_password(concurrent_password))
            return valid

        with patch.object(GoogleCredentialsForm, "is_valid", configure_after_validation):
            response = self.client.post(reverse("accounts:credentials"), {
                "username": "changed", "password": self.password,
            })

        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(concurrent_password))
        self.assertEqual(self.user.username, "member")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_completed_credentials_redirect_to_saved_destination_without_review(self):
        self.sign_in(google=True)
        session = self.client.session
        session["google_credentials_next"] = "/posts/?sort=oldest"
        session.save()
        response = self.client.get(reverse("accounts:credentials"))
        self.assertRedirects(response, "/posts/?sort=oldest", fetch_redirect_response=False)
        self.assertNotIn("google_credentials_next", self.client.session)

    def test_google_account_without_password_cannot_use_password_change_action(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        self.sign_in(google=True)
        response = self.client.post(reverse("accounts:profile"), {
            "action": "password", "old_password": "", "new_password1": self.password,
            "new_password2": self.password,
        })
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())

    def test_password_change_after_concurrent_deactivation_logs_out_without_writing_password(self):
        self.sign_in()
        original_validate = PasswordChangeForm.is_valid

        def deactivate_after_validation(form):
            valid = original_validate(form)
            User.objects.filter(pk=self.user.pk).update(is_active=False)
            return valid

        with patch.object(PasswordChangeForm, "is_valid", deactivate_after_validation):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "password", "old_password": self.password,
                "new_password1": "NewSecret!764Orange", "new_password2": "NewSecret!764Orange",
            })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def callback_context(self, *, reauth):
        session = self.client.session
        session[google_auth.TRANSACTION_KEY] = {"state": "pending"}
        session.pop(google_auth.REAUTH_KEY, None)
        session.save()
        return {"user_id": self.user.pk if reauth else None, "next": reverse("core:landing")}

    def test_normal_callback_cannot_switch_an_already_authenticated_account(self):
        self.sign_in()
        context = self.callback_context(reauth=False)
        with patch("accounts.google_auth.consume_login", return_value=context), patch(
            "accounts.google_auth.verified_claims", return_value={"subject": "another-subject"}
        ), patch("accounts.google_auth.account_for_claims") as account:
            response = self.client.get(reverse("accounts:google_callback"))
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        account.assert_not_called()
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        self.assertNotIn(google_auth.TRANSACTION_KEY, self.client.session)

    def test_reauthentication_rechecks_account_activation_after_google_verification(self):
        self.sign_in(google=True)
        context = self.callback_context(reauth=True)

        def deactivate_during_exchange(request, context):
            request.user.is_active = False
            User.objects.filter(pk=self.user.pk).update(is_active=False)
            return {"subject": "subject-member"}

        with patch("accounts.google_auth.consume_login", return_value=context), patch(
            "accounts.google_auth.verified_claims", side_effect=deactivate_during_exchange,
        ):
            response = self.client.get(reverse("accounts:google_callback"))
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        self.assertNotIn(google_auth.TRANSACTION_KEY, self.client.session)

    def test_reauthentication_of_incomplete_profile_returns_to_onboarding(self):
        self.sign_in(google=True)
        context = self.callback_context(reauth=True)
        Profile.objects.filter(user=self.user).update(domicile="", birth_date=None)
        with patch("accounts.google_auth.consume_login", return_value=context), patch(
            "accounts.google_auth.verified_claims", return_value={"subject": "subject-member"},
        ):
            response = self.client.get(reverse("accounts:google_callback"))
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], reverse("core:landing"))
        self.assertEqual(self.client.session[google_auth.REAUTH_KEY]["user_id"], self.user.pk)

    def test_unknown_path_and_post_are_gated_with_safe_return_destination(self):
        self.sign_in(google=True, credentials=False)
        response = self.client.get("/missing-private-page/?filter=book")
        self.assertRedirects(response, reverse("accounts:credentials"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_credentials_next"], "/missing-private-page/?filter=book")
        response = self.client.post("/missing-private-page/", {"sensitive": "value"})
        self.assertRedirects(response, reverse("accounts:credentials"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_credentials_next"], reverse("core:landing"))

    def test_profile_review_gate_does_not_replay_post_payload_or_replace_saved_destination(self):
        self.sign_in(google=True)
        session = self.client.session
        session[google_auth.PROFILE_REVIEW_KEY] = self.user.pk
        session.save()
        response = self.client.post("/missing-private-page/", {"sensitive": "value"})
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], reverse("core:landing"))
        session = self.client.session
        session["google_profile_next"] = "/posts/?filter=book"
        session.save()
        response = self.client.get("/different-private-page/")
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], "/posts/?filter=book")
