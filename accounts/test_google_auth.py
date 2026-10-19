import base64
import hashlib
import json
import time
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
from django.contrib.auth import SESSION_KEY, get_user_model
from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import DatabaseError, IntegrityError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from joserfc import jwt
from joserfc.jwk import RSAKey

from barter_details.models import Barter
from . import google_auth
from .models import GoogleAccountLinkChallenge, GoogleIdentity, GoogleLoginAttempt, Profile

User = get_user_model()
GOOGLE_SETTINGS = {
    "GOOGLE_ONLY_AUTH": True,
    "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/accounts/google/callback/",
    "GOOGLE_ALLOW_REGISTRATION": True,
    "PRODUCTION": False,
}


@override_settings(**GOOGLE_SETTINGS)
class GoogleOIDCTests(TestCase):
    metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
    token_url = "https://oauth2.googleapis.com/token"
    jwks_url = "https://www.googleapis.com/oauth2/v3/certs"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signing_key = RSAKey.generate_key(2048, {"kid": "google-test-key"})
        cls.untrusted_key = RSAKey.generate_key(2048, {"kid": "google-test-key"})

    def setUp(self):
        google_auth._client.cache_clear()
        self.sent_requests = []
        self.token_payload = None
        self.jwks = {"keys": [self.signing_key.as_dict(private=False)]}
        transport = patch("requests.sessions.Session.send", side_effect=self.google_transport)
        transport.start()
        self.addCleanup(transport.stop)
        self.addCleanup(google_auth._client.cache_clear)

    def google_transport(self, prepared, **kwargs):
        self.sent_requests.append(prepared)
        payloads = {
            self.metadata_url: {
                "issuer": "https://accounts.google.com",
                "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_endpoint": self.token_url,
                "jwks_uri": self.jwks_url,
                "id_token_signing_alg_values_supported": ["RS256"],
                "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            },
            self.token_url: self.token_payload,
            self.jwks_url: self.jwks,
        }
        if prepared.url not in payloads or payloads[prepared.url] is None:
            raise AssertionError(f"Unexpected OAuth HTTP request: {prepared.method} {prepared.url}")
        response = requests.Response()
        response.status_code = 200
        response.url = prepared.url
        response.request = prepared
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(payloads[prepared.url]).encode()
        return response

    def begin(self, client=None, **query):
        client = client or self.client
        response = client.get(reverse("accounts:google_login"), query)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).hostname, "accounts.google.com")
        context = client.session[google_auth.TRANSACTION_KEY]
        return response, context

    def issue_token(self, context, *, signing_key=None, omit=(), **overrides):
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "google-subject-123",
            "aud": GOOGLE_SETTINGS["GOOGLE_CLIENT_ID"],
            "iat": now,
            "exp": now + 3600,
            "nonce": context["nonce"],
            "email": "member@example.com",
            "email_verified": True,
            "name": "Anggota Google",
        }
        claims.update(overrides)
        for field in omit:
            claims.pop(field, None)
        self.token_payload = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": jwt.encode(
                {"alg": "RS256", "kid": "google-test-key"},
                claims, signing_key or self.signing_key,
            ),
        }
        return claims

    def callback(self, context, client=None, **overrides):
        params = {"state": context["state"], "code": "one-time-test-code"}
        params.update(overrides)
        return (client or self.client).get(reverse("accounts:google_callback"), params)

    def make_google_user(self, complete=True, active=True):
        user = User.objects.create_user(
            username="google-existing", email="member@example.com", password=None,
            first_name="Anggota Google", is_active=active,
        )
        Profile.objects.create(
            user=user, domicile="Depok" if complete else "",
            birth_date="2003-05-04" if complete else None,
        )
        GoogleIdentity.objects.create(user=user, subject="google-subject-123", email=user.email)
        return user

    def assert_denied(self, response):
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn(google_auth.TRANSACTION_KEY, self.client.session)

    def assert_storage_unavailable(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotIn(SESSION_KEY, response.wsgi_request.session)
        self.assertNotIn(google_auth.TRANSACTION_KEY, response.wsgi_request.session)
        self.assertNotIn(google_auth.REAUTH_KEY, response.wsgi_request.session)
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["max-age"], 0)
        for secret in ("test-access-token", "one-time-test-code", GOOGLE_SETTINGS["GOOGLE_CLIENT_SECRET"]):
            self.assertNotContains(response, secret, status_code=503)
        if self.token_payload and self.token_payload.get("id_token"):
            self.assertNotContains(response, self.token_payload["id_token"], status_code=503)

    def assert_stored_sessions_unauthenticated(self):
        for session in Session.objects.all():
            self.assertNotIn(SESSION_KEY, session.get_decoded())

    def token_requests(self):
        return [request for request in self.sent_requests if request.url == self.token_url]

    def test_authorization_uses_backend_redirect_nonce_state_and_s256_pkce(self):
        response, context = self.begin(next=reverse("accounts:profile"))
        query = parse_qs(urlsplit(response.url).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], ["openid email profile"])
        self.assertEqual(query["redirect_uri"], [GOOGLE_SETTINGS["GOOGLE_REDIRECT_URI"]])
        self.assertEqual(query["prompt"], ["select_account"])
        self.assertEqual(query["state"], [context["state"]])
        self.assertEqual(query["nonce"], [context["nonce"]])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("client_secret", query)
        attempt = GoogleLoginAttempt.objects.get()
        self.assertNotEqual(attempt.state_digest, context["state"])
        self.assertNotEqual(attempt.session_digest, self.client.session.session_key)
        self.issue_token(context)
        self.callback(context)
        body = parse_qs(self.token_requests()[0].body)
        self.assertEqual(body["redirect_uri"], [GOOGLE_SETTINGS["GOOGLE_REDIRECT_URI"]])
        verifier = body["code_verifier"][0]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(query["code_challenge"], [challenge])

    def test_verified_callback_rotates_session_and_requires_credentials_before_profile(self):
        _, context = self.begin(next=reverse("accounts:profile"))
        old_key = self.client.session.session_key
        self.issue_token(context, email="MEMBER@EXAMPLE.COM")
        response = self.callback(context)
        self.assertRedirects(response, reverse("accounts:credentials"), fetch_redirect_response=False)
        user = User.objects.get()
        self.assertEqual(user.email, "member@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertNotEqual(old_key, self.client.session.session_key)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertFalse(any(key.startswith("_state_google_") for key in self.client.session.keys()))
        serialized_session = json.dumps(dict(self.client.session.items()))
        for secret in ("test-access-token", self.token_payload["id_token"], "one-time-test-code"):
            self.assertNotIn(secret, serialized_session)
        response = self.client.post(reverse("accounts:credentials"), {
            "username": "member-new", "password": "RakitAkun!729Biru",
        })
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], reverse("accounts:profile"))

    def test_real_id_token_verification_rejects_signature_issuer_audience_expiry_and_nonce(self):
        cases = [
            ("signature", {"signing_key": self.untrusted_key}),
            ("issuer", {"iss": "https://attacker.example"}),
            ("audience", {"aud": "a-different-client"}),
            ("audience-with-authorized-party", {"aud": "a-different-client", "azp": GOOGLE_SETTINGS["GOOGLE_CLIENT_ID"]}),
            ("expiry", {"exp": int(time.time()) - 600}),
            ("future-issued", {"iat": int(time.time()) + 600}),
            ("nonce", {"nonce": "another-browser-nonce"}),
            ("missing-nonce", {"omit": ("nonce",)}),
            ("provider-skips-nonce", {"nonce": "another-browser-nonce", "nonce_supported": False}),
            ("non-ascii-nonce", {"nonce": "malicious-\u2603", "nonce_supported": False}),
        ]
        for name, changes in cases:
            with self.subTest(name=name):
                self.client = Client()
                _, context = self.begin()
                self.issue_token(context, **changes)
                self.assert_denied(self.callback(context))
                self.assertFalse(User.objects.exists())
                self.assertFalse(GoogleIdentity.objects.exists())

    def test_callback_without_id_token_never_uses_access_token_as_identity(self):
        _, context = self.begin()
        self.token_payload = {"access_token": "test-access-token", "token_type": "Bearer"}
        self.assert_denied(self.callback(context))
        self.assertFalse(User.objects.exists())
        self.assertFalse(any("userinfo" in request.url for request in self.sent_requests))

    def test_signed_token_requires_valid_subject_email_and_boolean_verified_email(self):
        cases = [
            {"email_verified": False}, {"email_verified": "true"},
            {"email": "invalid-address"}, {"email": "a" * 250 + "@example.com"},
            {"sub": ""}, {"sub": "non-ascii-\u2603"}, {"sub": "x" * 256},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.client = Client()
                _, context = self.begin()
                self.issue_token(context, **changes)
                self.assert_denied(self.callback(context))
                self.assertFalse(User.objects.exists())

    def test_callback_must_match_same_browser_and_state_before_exchange(self):
        _, context = self.begin()
        self.issue_token(context)
        stranger = Client()
        response = self.callback(context, client=stranger)
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, stranger.session)
        self.assertFalse(self.token_requests())
        self.assert_denied(self.callback(context, state="wrong-state"))
        self.assertFalse(self.token_requests())
        self.assertFalse(User.objects.exists())

    def test_expired_attempt_is_rejected_before_code_exchange(self):
        _, context = self.begin()
        self.issue_token(context)
        GoogleLoginAttempt.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assert_denied(self.callback(context))
        self.assertFalse(self.token_requests())

    def test_non_ascii_and_oversized_state_fail_safely_before_exchange(self):
        for state in ("malicious-\u2603", "a" * 256):
            with self.subTest(state=state):
                self.client = Client()
                _, context = self.begin()
                self.issue_token(context)
                self.assert_denied(self.callback(context, state=state))
        self.assertFalse(self.token_requests())
        self.assertFalse(User.objects.exists())

    def test_replayed_browser_snapshot_cannot_reuse_consumed_callback(self):
        _, context = self.begin()
        snapshot = dict(self.client.session.items())
        self.token_payload = {"access_token": "test-access-token", "token_type": "Bearer"}
        self.assert_denied(self.callback(context))
        self.assertIsNotNone(GoogleLoginAttempt.objects.get().consumed_at)
        session = self.client.session
        session.update(snapshot)
        session.save()
        self.issue_token(context)
        self.assert_denied(self.callback(context))
        self.assertEqual(len(self.token_requests()), 1)
        self.assertFalse(User.objects.exists())

    def test_provider_cancellation_and_missing_code_consume_attempt_without_exchange(self):
        for params in ({"error": "access_denied", "code": ""}, {"code": ""}):
            with self.subTest(params=params):
                self.client = Client()
                _, context = self.begin()
                self.assert_denied(self.callback(context, **params))
                attempt = GoogleLoginAttempt.objects.get(state_digest=google_auth.digest(context["state"]))
                self.assertIsNotNone(attempt.consumed_at)
        self.assertFalse(self.token_requests())

    def test_existing_subject_logs_into_original_account_and_does_not_relink_by_email(self):
        user = self.make_google_user()
        other = User.objects.create_user(username="other", email="new-address@example.com", password=None)
        _, context = self.begin()
        self.issue_token(context, email=other.email, name="Changed Google name")
        response = self.callback(context)
        self.assertRedirects(response, reverse("accounts:credentials"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(User.objects.count(), 2)
        user.refresh_from_db()
        self.assertEqual(user.email, "member@example.com")

    def test_unlinked_legacy_email_collision_requires_password_link_before_login(self):
        user = User.objects.create_user(username="legacy", email="MEMBER@example.com", password="old-password")
        _, context = self.begin()
        self.issue_token(context)
        self.assertRedirects(self.callback(context), reverse("accounts:google_link"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn(google_auth.TRANSACTION_KEY, self.client.session)
        self.assertIn(google_auth.LINK_SESSION_KEY, self.client.session)
        self.assertFalse(GoogleIdentity.objects.exists())
        self.assertEqual(User.objects.count(), 1)
        user.refresh_from_db()
        self.assertTrue(user.check_password("old-password"))

    def test_inactive_google_account_cannot_log_in(self):
        self.make_google_user(active=False)
        _, context = self.begin()
        self.issue_token(context)
        self.assert_denied(self.callback(context))
        self.assertEqual(User.objects.count(), 1)

    @override_settings(GOOGLE_ALLOW_REGISTRATION=False)
    def test_disabled_registration_blocks_new_users_but_existing_subject_can_log_in(self):
        _, context = self.begin()
        self.issue_token(context)
        self.assert_denied(self.callback(context))
        self.assertFalse(User.objects.exists())
        user = self.make_google_user()
        _, context = self.begin()
        self.issue_token(context)
        self.assertRedirects(self.callback(context), reverse("accounts:credentials"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_identity_write_failure_rolls_back_new_user_and_profile(self):
        claims = {"subject": "new-subject", "email": "new@example.com", "name": "New"}
        with patch("accounts.google_auth.GoogleIdentity.objects.create", side_effect=IntegrityError):
            with self.assertRaises(google_auth.GoogleLoginError):
                google_auth.account_for_claims(claims)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Profile.objects.exists())
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_session_persistence_failure_cannot_return_authenticated_success(self):
        _, context = self.begin()
        self.issue_token(context)
        original_save = SessionStore.save
        failed = False

        def fail_authenticated_save(store, *args, **kwargs):
            nonlocal failed
            if SESSION_KEY in store and not failed:
                failed = True
                raise DatabaseError("test session persistence failure")
            return original_save(store, *args, **kwargs)

        with patch.object(SessionStore, "save", fail_authenticated_save):
            self.assert_storage_unavailable(self.callback(context))
        self.assertTrue(failed)
        self.assert_stored_sessions_unauthenticated()
        self.assertRedirects(
            self.client.get(reverse("accounts:profile")),
            reverse("accounts:auth") + "?next=" + reverse("accounts:profile"),
            fetch_redirect_response=False,
        )

    def test_session_update_error_returns_unavailable_and_expires_browser_cookie(self):
        _, context = self.begin()
        self.issue_token(context)
        with patch.object(SessionStore, "save", side_effect=UpdateError("session disappeared")):
            with patch("accounts.views.auth_logout") as logout:
                self.assert_storage_unavailable(self.callback(context))
                logout.assert_not_called()
        self.assert_stored_sessions_unauthenticated()

    def test_database_and_session_outage_does_not_attempt_database_logout(self):
        _, context = self.begin()
        self.issue_token(context)
        with patch("django.db.models.query.QuerySet.update", side_effect=DatabaseError("database unavailable")):
            with patch.object(SessionStore, "save", side_effect=UpdateError("session unavailable")) as save:
                with patch.object(SessionStore, "delete", side_effect=DatabaseError("database unavailable")) as delete:
                    with patch("accounts.views.auth_logout") as logout:
                        self.assert_storage_unavailable(self.callback(context))
                        logout.assert_not_called()
                    save.assert_not_called()
                    delete.assert_not_called()
        self.assert_stored_sessions_unauthenticated()
        self.assertFalse(self.token_requests())

    def test_safe_next_keeps_local_destinations_and_rejects_external_or_auth_loops(self):
        self.make_google_user()
        cases = [
            ("/accounts/profile/?tab=profile#profile", "/accounts/profile/?tab=profile#profile"),
            ("https://attacker.example/steal", reverse("core:landing")),
            ("//attacker.example/steal", reverse("core:landing")),
            ("/\\attacker.example/steal", reverse("core:landing")),
            ("/accounts/google/callback/", reverse("core:landing")),
            ("/accounts/complete-profile/", reverse("core:landing")),
            ("/accounts/credentials/", reverse("core:landing")),
            ("/accounts/auth/?next=/accounts/auth/", reverse("core:landing")),
        ]
        for next_url, expected in cases:
            with self.subTest(next_url=next_url):
                self.client = Client()
                _, context = self.begin(next=next_url)
                self.issue_token(context)
                self.assertRedirects(self.callback(context), reverse("accounts:credentials"), fetch_redirect_response=False)
                response = self.client.post(reverse("accounts:credentials"), {
                    "username": "safe-next-member", "password": "SafeNext!639Biru",
                })
                self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
                self.assertEqual(self.client.session["google_profile_next"], expected)
                response = self.client.post(reverse("accounts:complete_profile"), {"action": "skip"})
                self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_google_only_mode_rejects_password_login_and_registration_posts(self):
        User.objects.create_user(username="legacy", email="legacy@example.com", password="valid-password")
        for route in ("auth", "login", "register"):
            with self.subTest(route=route):
                response = self.client.post(reverse(f"accounts:{route}"), {
                    "username": "legacy", "password": "valid-password",
                    "mode": "register", "password1": "valid-password", "password2": "valid-password",
                })
                self.assertEqual(response.status_code, 400)
                self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(User.objects.count(), 1)

    @override_settings(GOOGLE_CLIENT_SECRET="")
    def test_missing_configuration_fails_locally_without_network(self):
        response = self.client.get(reverse("accounts:google_login"))
        self.assert_denied(response)
        self.assertFalse(self.sent_requests)
        self.assertFalse(GoogleLoginAttempt.objects.exists())

    def test_reauthentication_rotates_session_and_rejects_google_account_switch(self):
        user = self.make_google_user()
        self.client.force_login(user)
        session = self.client.session
        session[google_auth.REAUTH_KEY] = {"user_id": user.pk, "time": time.time()}
        session.save()
        _, context = self.begin(reauth="1", next=reverse("accounts:profile"))
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        self.issue_token(context, sub="a-different-google-account", email="different@example.com")
        response = self.callback(context)
        self.assertRedirects(response, reverse("accounts:auth"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        self.assertEqual(User.objects.count(), 1)
        _, context = self.begin(reauth="1", next=reverse("accounts:profile"))
        old_key = self.client.session.session_key
        self.issue_token(context)
        self.assertRedirects(self.callback(context), reverse("accounts:profile"), fetch_redirect_response=False)
        self.assertNotEqual(self.client.session.session_key, old_key)
        self.assertEqual(self.client.session[google_auth.REAUTH_KEY]["user_id"], user.pk)


@override_settings(**GOOGLE_SETTINGS)
class GoogleProfileAndSessionTests(TestCase):
    password = "GoogleMember!837Kuning"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="google-profile", email="profile@example.com", password=cls.password,
            first_name="Profil Google",
        )
        cls.profile = Profile.objects.create(user=cls.user)
        cls.identity = GoogleIdentity.objects.create(user=cls.user, subject="google-profile-subject", email=cls.user.email)

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[google_auth.CREDENTIALS_KEY] = {
            "user_id": self.user.pk, "auth_hash": self.user.get_session_auth_hash(),
        }
        session.save()

    def profile_data(self, **changes):
        data = {
            "username": self.user.username,
            "full_name": "Nama Lengkap", "email": "attacker@example.com",
            "domicile": "Depok", "birth_date": "2003-05-04", "social_contact": "",
        }
        data.update(changes)
        return data

    def complete_profile(self):
        self.profile.domicile = "Depok"
        self.profile.birth_date = "2003-05-04"
        self.profile.save()

    def test_incomplete_google_profile_cannot_browse_main_app_but_can_edit_and_logout(self):
        response = self.client.get(reverse("core:landing") + "?from=login")
        self.assertRedirects(response, reverse("accounts:complete_profile"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["google_profile_next"], reverse("core:landing") + "?from=login")
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:complete_profile")).status_code, 200)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:auth"), fetch_redirect_response=False)

    def test_onboarding_requires_username_and_location_and_preserves_google_identity(self):
        for changes, field in (({"username": ""}, "username"), ({"domicile": ""}, "domicile")):
            with self.subTest(field=field, changes=changes):
                response = self.client.post(reverse("accounts:complete_profile"), self.profile_data(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["completion_form"].errors)
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.domicile, "")
        session = self.client.session
        session["google_profile_next"] = "/accounts/profile/#profile"
        session.save()
        response = self.client.post(reverse("accounts:complete_profile"), self.profile_data())
        self.assertRedirects(response, "/accounts/profile/#profile", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.identity.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertEqual(self.identity.email, "profile@example.com")
        self.assertEqual(self.user.first_name, "Profil Google")
        self.assertEqual(self.profile.domicile, "Depok")
        self.assertTrue(self.profile.onboarding_completed)
        self.assertIsNone(self.profile.birth_date)
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_onboarding_rechecks_stored_next_before_redirect(self):
        session = self.client.session
        session["google_profile_next"] = "https://attacker.example/"
        session.save()
        self.assertRedirects(
            self.client.post(reverse("accounts:complete_profile"), self.profile_data()),
            reverse("core:landing"), fetch_redirect_response=False,
        )

    def test_profile_post_preserves_google_email_and_password_change_requires_current_password(self):
        self.complete_profile()
        response = self.client.post(reverse("accounts:profile"), self.profile_data(action="profile"))
        self.assertRedirects(response, reverse("accounts:profile") + "#profile", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertTrue(self.user.check_password(self.password))
        response = self.client.post(reverse("accounts:profile"), {
            "action": "password", "old_password": "", "new_password1": "new-password",
            "new_password2": "new-password",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["password_form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        response = self.client.post(reverse("accounts:profile"), {
            "action": "password", "old_password": self.password,
            "new_password1": "GoogleChanged!918Hijau", "new_password2": "GoogleChanged!918Hijau",
        })
        self.assertRedirects(response, reverse("accounts:profile") + "#settings", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("GoogleChanged!918Hijau"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_google_delete_requires_password_and_confirmation_even_after_recent_reauthentication(self):
        self.complete_profile()
        session = self.client.session
        session[google_auth.REAUTH_KEY] = {"user_id": self.user.pk, "time": time.time()}
        session.save()
        for data, field in (
            ({"action": "delete", "confirm": "on"}, "password"),
            ({"action": "delete", "password": "wrong", "confirm": "on"}, "password"),
            ({"action": "delete", "password": self.password}, "confirm"),
        ):
            with self.subTest(field=field):
                response = self.client.post(reverse("accounts:profile"), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["deactivate_form"].errors)
                self.user.refresh_from_db()
                self.assertTrue(self.user.is_active)
                self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_google_delete_is_permanent_without_fresh_reauth_and_frees_google_identity(self):
        self.complete_profile()
        user_id, email, subject = self.user.pk, self.user.email, self.identity.subject
        listing = Barter.objects.create(
            owner=self.user, thumbnail="https://example.com/item.jpg", title="Used book",
            description="A book to exchange", item_year=2024, condition=80, item_location="Depok",
        )
        session = self.client.session
        session[google_auth.REAUTH_KEY] = {"user_id": self.user.pk, "time": time.time() - 600}
        session.save()
        old_session_key = self.client.session.session_key
        anonymous_link = SessionStore()
        anonymous_link["google_account_link"] = {"key": "pending-link-proof"}
        anonymous_link.create()
        link_session_digest = google_auth.digest(anonymous_link.session_key)
        GoogleAccountLinkChallenge.objects.create(
            user=self.user, token_digest=google_auth.digest("pending-link-proof"),
            session_digest=link_session_digest, subject=subject, email=email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        GoogleLoginAttempt.objects.create(
            state_digest=google_auth.digest("delete-current-login-attempt"),
            session_digest=google_auth.digest(old_session_key),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        GoogleLoginAttempt.objects.create(
            state_digest=google_auth.digest("delete-pending-link-attempt"),
            session_digest=link_session_digest, expires_at=timezone.now() + timedelta(minutes=10),
        )
        unrelated_attempt = GoogleLoginAttempt.objects.create(
            state_digest=google_auth.digest("other-user-login-attempt"),
            session_digest=google_auth.digest("other-user-session"),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(reverse("accounts:profile"), {
            "action": "delete", "password": self.password, "confirm": "on",
        })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertFalse(GoogleIdentity.objects.filter(user_id=user_id).exists())
        self.assertFalse(GoogleAccountLinkChallenge.objects.filter(user_id=user_id).exists())
        self.assertFalse(Barter.objects.filter(pk=listing.pk).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn(google_auth.REAUTH_KEY, self.client.session)
        self.assertNotIn(google_auth.CREDENTIALS_KEY, self.client.session)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=anonymous_link.session_key).exists())
        self.assertEqual(list(GoogleLoginAttempt.objects.values_list("pk", flat=True)), [unrelated_attempt.pk])
        landing = self.client.get(reverse("home"))
        self.assertEqual(landing.status_code, 200)
        self.assertFalse(landing.wsgi_request.user.is_authenticated)
        self.assertFalse(self.client.login(username=self.user.username, password=self.password))
        replacement = google_auth.account_for_claims({"email": email, "subject": subject, "name": "New account"})
        self.assertTrue(replacement.is_active)
        self.assertNotEqual(replacement.pk, user_id)
        self.assertEqual(replacement.email, email)
        self.assertEqual(GoogleIdentity.objects.get(subject=subject).user_id, replacement.pk)
        self.assertEqual(replacement.barter_items.count(), 0)

    def test_unusable_password_google_delete_requires_recent_same_user_proof(self):
        from .forms import DeactivateAccountForm
        from .deletion import permanently_delete_account

        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        invalid = DeactivateAccountForm({"confirm": "on"}, user=self.user, google_authenticated=False)
        self.assertNotIn("password", invalid.fields)
        self.assertFalse(invalid.is_valid())
        valid = DeactivateAccountForm({"confirm": "on"}, user=self.user, google_authenticated=True)
        self.assertTrue(valid.is_valid(), valid.errors)
        permanently_delete_account(user_id=self.user.pk, password="", google_authenticated=True)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_google_account_delete_requires_csrf_even_with_recent_reauthentication(self):
        self.complete_profile()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        session = client.session
        session[google_auth.CREDENTIALS_KEY] = {
            "user_id": self.user.pk, "auth_hash": self.user.get_session_auth_hash(),
        }
        session[google_auth.REAUTH_KEY] = {"user_id": self.user.pk, "time": time.time()}
        session.save()
        self.assertEqual(client.post(reverse("accounts:profile"), {
            "action": "delete", "password": self.password, "confirm": "on",
        }).status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(client.session[SESSION_KEY], str(self.user.pk))

    def test_logout_requires_post_csrf_and_invalidates_only_session_preserving_account(self):
        self.complete_profile()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        session = client.session
        session[google_auth.CREDENTIALS_KEY] = {
            "user_id": self.user.pk, "auth_hash": self.user.get_session_auth_hash(),
        }
        session.save()
        old_key = client.session.session_key
        self.assertEqual(client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        self.assertEqual(client.get(reverse("accounts:profile")).status_code, 200)
        csrf_token = client.cookies["csrftoken"].value
        self.assertRedirects(
            client.post(reverse("accounts:logout"), {"csrfmiddlewaretoken": csrf_token}),
            reverse("accounts:auth"), fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, client.session)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk, is_active=True).exists())
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertTrue(GoogleIdentity.objects.filter(user=self.user).exists())


class GoogleLegacyLinkCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="verified-legacy", email="legacy@example.com", password="existing-password",
            first_name="Legacy Member", is_staff=True,
        )
        cls.profile = Profile.objects.create(user=cls.user, domicile="Bandung", birth_date="2001-01-01")

    def link(self, **changes):
        arguments = {
            "username": self.user.username, "subject": "verified-google-subject",
            "email": self.user.email, "confirm_verified": True, "stdout": StringIO(),
        }
        arguments.update(changes)
        call_command("link_google_account", **arguments)

    def test_link_command_requires_verified_confirmation_matching_email_and_active_user(self):
        for changes in ({"confirm_verified": False}, {"email": "another@example.com"}, {"subject": ""}):
            with self.subTest(changes=changes):
                with self.assertRaises(CommandError):
                    self.link(**changes)
                self.assertFalse(GoogleIdentity.objects.exists())
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(CommandError):
            self.link()
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_link_dry_run_and_idempotent_write_keep_existing_user_role_and_profile(self):
        self.link(dry_run=True)
        self.assertFalse(GoogleIdentity.objects.exists())
        self.link(email="LEGACY@EXAMPLE.COM")
        self.link()
        self.assertEqual(GoogleIdentity.objects.get().user_id, self.user.pk)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.check_password("existing-password"))
        self.assertEqual(self.profile.domicile, "Bandung")
        self.assertEqual(User.objects.count(), 1)

    def test_link_rejects_subject_owned_by_another_user_and_ambiguous_legacy_email(self):
        other = User.objects.create_user(username="other", email="other@example.com", password=None)
        GoogleIdentity.objects.create(user=other, subject="verified-google-subject", email=other.email)
        with self.assertRaises(CommandError):
            self.link()
        self.assertFalse(GoogleIdentity.objects.filter(user=self.user).exists())
        other.email = "LEGACY@EXAMPLE.COM"
        other.save(update_fields=["email"])
        with self.assertRaises(CommandError):
            self.link(subject="different-verified-subject")
        self.assertFalse(GoogleIdentity.objects.filter(user=self.user).exists())
