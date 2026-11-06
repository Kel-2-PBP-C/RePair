"""Boundary and failure tests for account support services, without external HTTP."""

import logging
from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import google_auth, regions
from .deletion import permanently_delete_account
from .logging import OAuthCallbackFilter
from .models import GoogleIdentity, GoogleLoginAttempt, Profile


@override_settings(
    BOGORTECH_API_KEY="test-region-key",
    BOGORTECH_CA_BUNDLE="",
    CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "region-boundary-tests",
    }},
)
class RegionBoundaryTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        network = patch("requests.sessions.Session.send", side_effect=AssertionError("Unexpected HTTP"))
        network.start()
        self.addCleanup(network.stop)

    @patch("accounts.regions.requests.get")
    def test_custom_ca_bundle_is_trimmed_and_passed_to_tls_verification(self, get):
        get.return_value = Mock(status_code=200, content=b"{}")
        get.return_value.json.return_value = {"data": []}
        with override_settings(BOGORTECH_CA_BUNDLE="  /test/trusted-ca.pem  "):
            self.assertEqual(regions._request_records("provinces"), [])
        self.assertEqual(get.call_args.kwargs["verify"], "/test/trusted-ca.pem")

    @patch("accounts.regions.requests.get")
    def test_invalid_api_key_types_fail_before_http(self, get):
        for key in (None, 42, [], "   "):
            with self.subTest(key=key), override_settings(BOGORTECH_API_KEY=key):
                with self.assertRaises(regions.RegionServiceError):
                    regions.search_regions("Depok")
        get.assert_not_called()

    @patch("accounts.regions.requests.get")
    def test_response_size_limit_rejects_body_before_json_decode(self, get):
        response = Mock(status_code=200, content=b"x" * (2 * 1024 * 1024 + 1))
        get.return_value = response
        with self.assertRaises(regions.RegionServiceError):
            regions._request_records("search")
        response.json.assert_not_called()

    @patch("accounts.regions.requests.get")
    def test_provider_record_count_is_bounded(self, get):
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {"data": [None] * 20001}
        get.return_value = response
        with self.assertRaises(regions.RegionServiceError):
            regions._request_records("search")

    @patch("accounts.regions.requests.get")
    def test_tls_and_decoding_errors_do_not_leak_provider_details(self, get):
        for error in (requests.exceptions.SSLError, OSError, TypeError, ValueError):
            with self.subTest(error=error):
                get.side_effect = error("private provider details")
                with self.assertRaises(regions.RegionServiceError) as raised:
                    regions._request_records("search")
                self.assertNotIn("private provider details", str(raised.exception))

    def test_provider_records_require_valid_names_and_codes(self):
        invalid = (
            {"code": 32, "name": "Depok"},
            {"code": "32.76", "name": None},
            {"code": "32.76", "name": "x" * 121},
            {"code": "32.76", "name": "Depok\x00"},
            {"code": "32.76", "name": " \t "},
        )
        for record in invalid:
            with self.subTest(record=record):
                self.assertIsNone(regions._record(record, regions.REGION_CODE_RE))
        self.assertEqual(
            regions._record({"code": "32.76", "name": " Kota \t Depok "}, regions.REGION_CODE_RE),
            {"code": "32.76", "name": "Kota Depok"},
        )

    @patch("accounts.regions.requests.get")
    def test_invalid_search_queries_are_rejected_without_http(self, get):
        for query in (None, [], 32, "x" * (regions.MAX_QUERY_LENGTH + 1)):
            with self.subTest(query=query), self.assertRaises(ValueError):
                regions.search_regions(query)
        get.assert_not_called()

    @patch("accounts.regions._provinces", return_value={"32": "Jawa Barat"})
    @patch("accounts.regions._search_provider")
    def test_result_limits_are_clamped_and_bad_limits_use_default(self, search, provinces):
        search.return_value = [
            {"code": f"32.{index:02d}", "name": f"Kota {index:02d}", "label": f"Kota {index:02d}, Jawa Barat"}
            for index in range(60)
        ]
        for limit, expected in ((0, 1), (-2, 1), (100, 50), ("2", 2), (None, 30), ("bad", 30)):
            with self.subTest(limit=limit):
                self.assertEqual(len(regions.search_regions("Kota Depok", limit=limit)), expected)
        self.assertTrue(all(call.args[0] == "Kota Depok" for call in search.call_args_list))

    @patch("accounts.regions._provinces", return_value={"32": "Jawa Barat"})
    @patch("accounts.regions._search_provider", side_effect=regions.RegionServiceUnavailable)
    def test_worker_failure_does_not_return_partial_results(self, search, provinces):
        with self.assertRaises(regions.RegionServiceUnavailable):
            regions.search_regions("Depok")

    @patch("accounts.regions._request_records", return_value=[{"code": "32", "name": "Jawa Barat"}])
    def test_unknown_province_does_not_request_a_regency_directory(self, records):
        self.assertIsNone(regions.lookup_region("99.01"))
        records.assert_called_once_with("provinces")

    @patch("accounts.regions._request_records")
    def test_empty_or_wrong_province_regency_directory_is_unavailable_and_not_cached(self, records):
        records.side_effect = [
            [{"code": "32", "name": "Jawa Barat"}, {"code": "31", "name": "Jakarta"}],
            [{"code": "31.01", "name": "Kota Jakarta"}, None],
            [{"code": "32.76", "name": "Kota Depok"}],
        ]
        with self.assertRaises(regions.RegionServiceUnavailable):
            regions.lookup_region("32.76")
        self.assertEqual(regions.lookup_region("32.76")["name"], "Kota Depok")
        self.assertEqual(records.call_count, 3)


@override_settings(GOOGLE_ONLY_AUTH=False)
class RegionEndpointBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="region-boundary-member")

    def setUp(self):
        self.client.force_login(self.user)

    @patch("accounts.region_views.regions.search_regions")
    def test_overlong_query_returns_400_without_invoking_provider(self, search):
        response = self.client.get(reverse("accounts:region_search"), {"q": "x" * 81})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["results"], [])
        self.assertIn("80", response.json()["error"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        search.assert_not_called()

    @patch("accounts.region_views.regions.search_regions", side_effect=ValueError("private detail"))
    def test_invalid_query_service_error_returns_safe_json(self, search):
        response = self.client.get(reverse("accounts:region_search"), {"q": "test"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Kata pencarian tidak valid.", "results": []})
        self.assertIn("no-store", response.headers["Cache-Control"])


class AccountDeletionBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="delete-boundary", password="CurrentPassword!123")
        Profile.objects.create(user=cls.user)

    def test_service_rechecks_current_password_before_deleting_any_data(self):
        self.user.set_password("ChangedPassword!456")
        self.user.save(update_fields=["password"])
        with self.assertRaisesMessage(ValidationError, "Password tidak benar"):
            permanently_delete_account(user_id=self.user.pk, password="CurrentPassword!123", google_authenticated=True)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_google_proof_cannot_delete_a_passwordless_account_without_google_identity(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        with self.assertRaisesMessage(ValidationError, "Verifikasi ulang"):
            permanently_delete_account(user_id=self.user.pk, password="", google_authenticated=True)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_passwordless_linked_account_requires_google_proof(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        GoogleIdentity.objects.create(user=self.user, subject="delete-proof", email="delete@example.com")
        with self.assertRaisesMessage(ValidationError, "Verifikasi ulang"):
            permanently_delete_account(user_id=self.user.pk, password="")
        self.assertTrue(GoogleIdentity.objects.filter(user=self.user).exists())

    def test_account_without_sessions_or_pending_attempts_can_be_deleted(self):
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GoogleLoginAttempt.objects.exists())
        permanently_delete_account(user_id=self.user.pk, password="CurrentPassword!123")
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Profile.objects.filter(user=self.user).exists())

    def test_deletion_clears_orphaned_current_login_attempt_but_keeps_unrelated_session(self):
        unrelated = SessionStore()
        unrelated[SESSION_KEY] = "999999"
        unrelated.save()
        current_key = "orphaned-current-session"
        GoogleLoginAttempt.objects.create(
            state_digest=google_auth.digest("pending-state"),
            session_digest=google_auth.digest(current_key),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        permanently_delete_account(user_id=self.user.pk, password="CurrentPassword!123", session_key=current_key)
        self.assertFalse(GoogleLoginAttempt.objects.exists())
        self.assertTrue(Session.objects.filter(session_key=unrelated.session_key).exists())
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())


class OAuthLoggingTests(SimpleTestCase):
    def test_callback_query_is_redacted_after_interpolating_log_arguments(self):
        record = logging.LogRecord(
            "django.server", logging.INFO, __file__, 1,
            '"GET %s HTTP/1.1" %s',
            ("/accounts/google/callback/?code=secret-code&state=secret-state", 302), None,
        )
        self.assertTrue(OAuthCallbackFilter().filter(record))
        self.assertEqual(record.getMessage(), '"GET /accounts/google/callback/?<redacted> HTTP/1.1" 302')
        self.assertEqual(record.args, ())
        self.assertNotIn("secret", record.getMessage())

    def test_multiple_callback_urls_are_redacted_without_altering_other_routes(self):
        record = logging.makeLogRecord({
            "msg": "/accounts/google/callback/?code=first /accounts/google/callback/?state=second /accounts/profile/?tab=profile",
        })
        OAuthCallbackFilter().filter(record)
        self.assertEqual(record.getMessage().count("?<redacted>"), 2)
        self.assertIn("/accounts/profile/?tab=profile", record.getMessage())

    def test_log_without_callback_query_is_preserved(self):
        record = logging.makeLogRecord({"msg": "GET /accounts/google/callback/ returned %s", "args": (400,)})
        OAuthCallbackFilter().filter(record)
        self.assertEqual(record.getMessage(), "GET /accounts/google/callback/ returned 400")
