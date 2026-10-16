import json
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import google_auth, regions
from .forms import ProfileForm
from .models import GoogleIdentity, Profile
from .test_google_auth import GOOGLE_SETTINGS

User = get_user_model()
TEST_API_KEY = "private-test-region-api-key"
DEPOK = {
    "code": "32.76", "name": "Kota Depok", "province_code": "32",
    "province_name": "Jawa Barat", "label": "Kota Depok, Jawa Barat",
}


@override_settings(
    BOGORTECH_API_KEY=TEST_API_KEY,
    CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "isolated-region-service-tests",
    }},
)
class RegionServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        network = patch(
            "requests.sessions.Session.send",
            side_effect=AssertionError("External HTTP is disabled in region tests"),
        )
        network.start()
        self.addCleanup(network.stop)

    def response(self, payload, *, status=200):
        response = requests.Response()
        response.status_code = status
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(payload).encode("utf-8")
        return response

    def provider(self, url, **kwargs):
        if url.endswith("/provinces"):
            rows = [{"code": "32", "name": "Jawa Barat"}, {"code": "36", "name": "Banten"}]
        elif url.endswith("/search"):
            rows = [
                {"code": "32.76", "name": "Kota Depok"},
                {"code": "36.74", "name": "Kota Tangerang Selatan"},
                {"code": "32", "name": "Jawa Barat"},
                {"code": "32.76.01", "name": "Kecamatan Depok"},
                {"code": "32.76.01.1001", "name": "Kelurahan Depok"},
                {"code": "99.01", "name": "Unknown province"},
                {"code": "32.77", "name": ""},
                {"code": "32.76", "name": "Kota Depok"},
                None,
            ]
        elif url.endswith("/regencies/32"):
            rows = [{"code": "32.76", "name": "Kota Depok"}, {"code": "32.73", "name": "Kota Bandung"}]
        else:
            raise AssertionError(f"Unexpected provider path: {url}")
        return self.response({"data": rows, "meta": {"administrative_area_level": 2}})

    @patch("accounts.regions.requests.get")
    def test_search_only_returns_city_or_regency_with_known_province(self, get):
        get.side_effect = self.provider
        results = regions.search_regions("depok")
        self.assertEqual([row["code"] for row in results], ["32.76", "36.74"])
        self.assertEqual(results[0], DEPOK)
        self.assertEqual(results[1]["label"], "Kota Tangerang Selatan, Banten")

    @patch("accounts.regions.requests.get")
    def test_api_key_stays_in_server_header_with_bounded_timeout_and_no_redirects(self, get):
        get.side_effect = self.provider
        regions.search_regions("depok")
        self.assertGreater(get.call_count, 0)
        for call in get.call_args_list:
            self.assertTrue(call.args[0].startswith("https://api.bogortech.com/v1/wilayah/"))
            self.assertNotIn(TEST_API_KEY, call.args[0])
            self.assertEqual(call.kwargs["headers"]["X-API-KEY"], TEST_API_KEY)
            self.assertEqual(call.kwargs["timeout"], (3.05, 8))
            self.assertIs(call.kwargs["allow_redirects"], False)
            self.assertIsNot(call.kwargs.get("verify", True), False)
            self.assertNotIn(TEST_API_KEY, json.dumps(call.kwargs.get("params")))

    @patch("accounts.regions.requests.get")
    def test_initial_dropdown_fetches_cities_without_a_typed_query(self, get):
        def provider(url, **kwargs):
            if url.endswith("/provinces"):
                return self.provider(url, **kwargs)
            return self.response({"data": [
                {"code": "32.01", "name": "Kabupaten Bogor"},
                {"code": "32.76", "name": "Kota Depok"},
            ]})

        get.side_effect = provider
        results = regions.search_regions("")
        self.assertEqual([result["label"] for result in results], [
            "Kota Depok, Jawa Barat", "Kabupaten Bogor, Jawa Barat",
        ])
        search_queries = {
            call.kwargs["params"]["q"]
            for call in get.call_args_list if call.args[0].endswith("/search")
        }
        self.assertEqual(search_queries, {
            "Jakarta", "Depok", "Bandung", "Surabaya", "Medan", "Yogyakarta",
            "Denpasar", "Balikpapan", "Makassar", "Jayapura",
        })

    @patch("accounts.regions.requests.get")
    def test_targeted_city_queries_recover_choices_when_global_search_is_filled_by_villages(self, get):
        def provider(url, **kwargs):
            if url.endswith("/provinces"):
                rows = [{"code": "32", "name": "Jawa Barat"}]
            else:
                query = kwargs["params"]["q"]
                rows = {
                    "bogor": [{"code": f"32.01.01.{index:04d}", "name": f"Desa Bogor {index}"} for index in range(50)],
                    "Kota bogor": [{"code": "32.71", "name": "Kota Bogor"}],
                    "Kabupaten bogor": [{"code": "32.01", "name": "Kabupaten Bogor"}],
                }[query]
            return self.response({"data": rows})

        get.side_effect = provider
        results = regions.search_regions("bogor")
        self.assertEqual([result["code"] for result in results], ["32.01", "32.71"])
        self.assertEqual([result["label"] for result in results], [
            "Kabupaten Bogor, Jawa Barat", "Kota Bogor, Jawa Barat",
        ])

    @patch("accounts.regions.requests.get")
    def test_repeated_queries_use_cache_without_losing_results_to_previous_limit(self, get):
        get.side_effect = self.provider
        self.assertEqual(len(regions.search_regions(" depok ", limit=1)), 1)
        request_count = get.call_count
        self.assertEqual(len(regions.search_regions("DEPOK", limit=30)), 2)
        self.assertEqual(get.call_count, request_count)

    @patch("accounts.regions.requests.get")
    def test_code_lookup_uses_canonical_province_directory_and_cached_regencies(self, get):
        get.side_effect = self.provider
        self.assertEqual(regions.lookup_region(DEPOK["code"]), DEPOK)
        request_count = get.call_count
        self.assertEqual(regions.lookup_region(DEPOK["code"]), DEPOK)
        self.assertIsNone(regions.lookup_region("32.99"))
        self.assertEqual(get.call_count, request_count)

    @patch("accounts.regions.requests.get")
    def test_labels_that_exceed_profile_storage_limit_cannot_be_suggested_or_selected(self, get):
        province_name = "Provinsi " + "A" * 80
        rows = [
            {"code": "32.76", "name": "Kota Depok"},
            {"code": "32.77", "name": "Kota " + "B" * 100},
        ]

        def provider(url, **kwargs):
            data = [{"code": "32", "name": province_name}] if url.endswith("/provinces") else rows
            return self.response({"data": data})

        get.side_effect = provider
        results = regions.search_regions("kota")
        self.assertEqual([result["code"] for result in results], ["32.76"])
        self.assertLessEqual(len(results[0]["label"]), Profile._meta.get_field("domicile").max_length)
        self.assertIsNone(regions.lookup_region("32.77"))

    @patch("accounts.regions.requests.get")
    def test_invalid_region_codes_never_reach_the_provider(self, get):
        for code in ("", None, "32", "32.76.01", "../provinces", "https://malicious.example/", "32.76?key=secret"):
            with self.subTest(code=code):
                self.assertIsNone(regions.lookup_region(code))
        get.assert_not_called()

    @patch("accounts.regions.requests.get")
    def test_provider_timeout_and_http_errors_raise_only_generic_errors(self, get):
        failures = [
            requests.Timeout(f"Upstream request failed with {TEST_API_KEY}"),
            self.response({"error": TEST_API_KEY}, status=401),
            self.response({"error": TEST_API_KEY}, status=302),
            self.response({"error": TEST_API_KEY}, status=500),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__, status=getattr(failure, "status_code", None)):
                cache.clear()
                get.side_effect = failure if isinstance(failure, Exception) else None
                get.return_value = failure
                with self.assertRaises(regions.RegionServiceError) as raised:
                    regions.search_regions("depok")
                self.assertNotIn(TEST_API_KEY, str(raised.exception))

    @patch("accounts.regions.requests.get")
    def test_malformed_provider_payloads_are_rejected_without_exposing_contents(self, get):
        malformed = [
            [], {"data": {}}, {"data": None}, {"unexpected": TEST_API_KEY},
            {"success": False, "data": [], "error": TEST_API_KEY}, {"data": [None]},
        ]
        for payload in malformed:
            with self.subTest(payload=payload):
                cache.clear()
                get.return_value = self.response(payload)
                with self.assertRaises(regions.RegionServiceError) as raised:
                    regions.search_regions("depok")
                self.assertNotIn(TEST_API_KEY, str(raised.exception))
        invalid_json = self.response({})
        invalid_json._content = b"<html>Unavailable</html>"
        get.return_value = invalid_json
        with self.assertRaises(regions.RegionServiceError):
            regions.search_regions("depok")

    @patch("accounts.regions.requests.get")
    def test_missing_key_blocks_even_cached_search_and_never_contacts_provider(self, get):
        get.side_effect = self.provider
        regions.search_regions("depok")
        get.reset_mock()
        with override_settings(BOGORTECH_API_KEY=""):
            with self.assertRaises(regions.RegionServiceError):
                regions.search_regions("depok")
        get.assert_not_called()


@override_settings(**GOOGLE_SETTINGS, BOGORTECH_API_KEY=TEST_API_KEY)
class RegionProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="region-member", email="region@example.com",
            password="RegionMember!285Hijau", first_name="Anggota Wilayah",
        )
        cls.profile = Profile.objects.create(user=cls.user)
        GoogleIdentity.objects.create(
            user=cls.user, subject="google-region-subject", email=cls.user.email,
        )

    def setUp(self):
        network = patch(
            "requests.sessions.Session.send",
            side_effect=AssertionError("External HTTP is disabled in region tests"),
        )
        network.start()
        self.addCleanup(network.stop)

    def login_after_credentials(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[google_auth.CREDENTIALS_KEY] = {
            "user_id": self.user.pk, "auth_hash": self.user.get_session_auth_hash(),
        }
        session[google_auth.PROFILE_REVIEW_KEY] = self.user.pk
        session.save()

    def completion_data(self, **changes):
        data = {
            "username": self.user.username, "domicile": DEPOK["label"],
            "domicile_code": DEPOK["code"], "preferred_categories": ["elektronik"],
        }
        data.update(changes)
        return data

    def settings_data(self, **changes):
        data = {
            "action": "profile", "username": self.user.username,
            "full_name": "Anggota Wilayah", "email": self.user.email,
            "domicile": DEPOK["label"], "domicile_code": DEPOK["code"],
            "birth_date": "2001-01-01", "social_contact": "",
            "preferred_categories": ["elektronik"], "preferred_categories_present": "1",
        }
        data.update(changes)
        return data

    @patch("accounts.region_views.regions.search_regions")
    def test_guest_cannot_search_or_trigger_provider_requests(self, search):
        response = self.client.get(reverse("accounts:region_search"), {"q": "depok"})
        self.assertIn(response.status_code, (302, 401, 403))
        search.assert_not_called()
        self.assertNotContains(response, TEST_API_KEY, status_code=response.status_code)

    @patch("accounts.region_views.regions.search_regions")
    def test_google_member_must_finish_credentials_before_searching(self, search):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:region_search"), {"q": "depok"})
        self.assertRedirects(
            response, reverse("accounts:credentials"), fetch_redirect_response=False,
        )
        search.assert_not_called()

    @patch("accounts.region_views.regions.search_regions", return_value=[DEPOK])
    def test_incomplete_profile_can_search_after_credentials_without_finishing_review(self, search):
        self.login_after_credentials()
        response = self.client.get(reverse("accounts:region_search"), {"q": "depok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": [DEPOK]})
        self.assertEqual(search.call_args.args[0], "depok")
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.onboarding_completed)
        self.assertNotContains(response, TEST_API_KEY)

    @patch("accounts.region_views.regions.search_regions")
    def test_search_endpoint_does_not_accept_mutations(self, search):
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:region_search"), {"q": "depok"})
        self.assertEqual(response.status_code, 405)
        search.assert_not_called()

    @patch("accounts.region_views.regions.search_regions", side_effect=regions.RegionServiceUnavailable)
    def test_provider_outage_is_generic_json_and_does_not_reveal_key(self, search):
        self.login_after_credentials()
        response = self.client.get(reverse("accounts:region_search"), {"q": "depok"})
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json().get("error"))
        self.assertNotContains(response, TEST_API_KEY, status_code=503)
        self.assertNotContains(response, "Traceback", status_code=503)

    def test_profile_html_exposes_only_internal_endpoint_and_hidden_region_code(self):
        self.login_after_credentials()
        response = self.client.get(reverse("accounts:complete_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:region_search"))
        self.assertContains(response, 'name="domicile_code"')
        self.assertNotContains(response, TEST_API_KEY)
        self.assertNotContains(response, "api.bogortech.com")

    def test_settings_location_picker_exposes_only_internal_endpoint_and_region_code(self):
        self.login_after_credentials()
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:region_search"))
        self.assertContains(response, 'name="domicile_code"')
        self.assertNotContains(response, TEST_API_KEY)
        self.assertNotContains(response, "api.bogortech.com")

    @patch("accounts.forms.regions.lookup_region", return_value=DEPOK)
    def test_selected_city_is_saved_with_code_and_server_canonical_name(self, lookup):
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"),
            self.completion_data(domicile="Forged city label, Another province"),
        )
        self.assertRedirects(response, reverse("core:landing"), fetch_redirect_response=False)
        lookup.assert_called_once_with(DEPOK["code"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile_code, DEPOK["code"])
        self.assertEqual(self.profile.domicile, DEPOK["label"])
        self.assertTrue(self.profile.onboarding_completed)
        self.assertEqual(self.profile.preferred_categories, ["elektronik"])

    @patch("accounts.forms.regions.lookup_region", side_effect=regions.RegionServiceError)
    def test_unchanged_selected_city_can_be_kept_when_provider_is_unavailable(self, lookup):
        self.profile.domicile = DEPOK["label"]
        self.profile.domicile_code = DEPOK["code"]
        self.profile.save()
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:complete_profile"), self.completion_data())
        self.assertRedirects(response, reverse("core:landing"), fetch_redirect_response=False)
        lookup.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, DEPOK["label"])
        self.assertEqual(self.profile.domicile_code, DEPOK["code"])

    @patch("accounts.forms.regions.lookup_region", return_value=DEPOK)
    def test_editing_stored_city_label_still_requires_canonical_lookup(self, lookup):
        self.profile.domicile = DEPOK["label"]
        self.profile.domicile_code = DEPOK["code"]
        self.profile.save()
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"), self.completion_data(domicile="Forged province"),
        )
        self.assertRedirects(response, reverse("core:landing"), fetch_redirect_response=False)
        lookup.assert_called_once_with(DEPOK["code"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, DEPOK["label"])

    @patch("accounts.forms.regions.lookup_region", return_value=DEPOK)
    def test_editing_stored_city_code_still_requires_canonical_lookup(self, lookup):
        self.profile.domicile = "Kota Bandung, Jawa Barat"
        self.profile.domicile_code = "32.73"
        self.profile.save()
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"), self.completion_data(domicile=self.profile.domicile),
        )
        self.assertRedirects(response, reverse("core:landing"), fetch_redirect_response=False)
        lookup.assert_called_once_with(DEPOK["code"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, DEPOK["label"])
        self.assertEqual(self.profile.domicile_code, DEPOK["code"])

    @patch("accounts.forms.regions.lookup_region")
    def test_oversized_region_code_shows_error_without_partial_profile_save(self, lookup):
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"), self.completion_data(domicile_code="1" * 21),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("domicile", response.context["completion_form"].errors)
        lookup.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile_code, "")
        self.assertEqual(self.profile.domicile, "")

    @patch("accounts.forms.regions.lookup_region", return_value=None)
    def test_unknown_city_code_cannot_save_a_forged_name(self, lookup):
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"), self.completion_data(domicile_code="99.99"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["completion_form"].errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, "")
        self.assertEqual(self.profile.domicile_code, "")
        self.assertFalse(self.profile.onboarding_completed)

    @patch("accounts.forms.regions.lookup_region", side_effect=regions.RegionServiceUnavailable)
    def test_selected_city_cannot_be_saved_unverified_during_provider_outage(self, lookup):
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:complete_profile"), self.completion_data())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["completion_form"].errors)
        self.assertNotContains(response, TEST_API_KEY)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile_code, "")
        self.assertEqual(self.profile.domicile, "")

    @patch("accounts.forms.regions.lookup_region")
    def test_user_can_keep_typing_a_location_and_clear_old_selection(self, lookup):
        self.profile.domicile = DEPOK["label"]
        self.profile.domicile_code = DEPOK["code"]
        self.profile.save()
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"),
            self.completion_data(domicile="  Tangerang Selatan, Banten  ", domicile_code=""),
        )
        self.assertRedirects(response, reverse("core:landing"), fetch_redirect_response=False)
        lookup.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, "Tangerang Selatan, Banten")
        self.assertEqual(self.profile.domicile_code, "")

    @patch("accounts.forms.regions.lookup_region")
    def test_blank_typed_location_remains_required(self, lookup):
        self.login_after_credentials()
        response = self.client.post(
            reverse("accounts:complete_profile"),
            self.completion_data(domicile="   ", domicile_code=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("domicile", response.context["completion_form"].errors)
        lookup.assert_not_called()

    @patch("accounts.forms.regions.lookup_region", return_value=DEPOK)
    def test_settings_selected_city_uses_server_label_and_preserves_google_email(self, lookup):
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:profile"), self.settings_data(
            domicile="Forged city, Forged province", email="attacker@example.com",
        ))
        self.assertRedirects(
            response, reverse("accounts:profile") + "#profile", fetch_redirect_response=False,
        )
        lookup.assert_called_once_with(DEPOK["code"])
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.domicile, DEPOK["label"])
        self.assertEqual(self.profile.domicile_code, DEPOK["code"])
        self.assertEqual(self.profile.preferred_categories, ["elektronik"])
        self.assertEqual(self.user.email, "region@example.com")

    @patch("accounts.forms.regions.lookup_region", side_effect=regions.RegionServiceUnavailable)
    def test_settings_can_keep_unchanged_city_during_provider_outage(self, lookup):
        self.profile.domicile = DEPOK["label"]
        self.profile.domicile_code = DEPOK["code"]
        self.profile.save(update_fields=["domicile", "domicile_code"])
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:profile"), self.settings_data())
        self.assertRedirects(
            response, reverse("accounts:profile") + "#profile", fetch_redirect_response=False,
        )
        lookup.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, DEPOK["label"])
        self.assertEqual(self.profile.domicile_code, DEPOK["code"])

    @patch("accounts.forms.regions.lookup_region", return_value=None)
    def test_settings_unknown_city_code_does_not_partially_update_account(self, lookup):
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:profile"), self.settings_data(
            username="renamed-region-member", domicile="Forged city", domicile_code="99.99",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("domicile", response.context["profile_form"].errors)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "region-member")
        self.assertEqual(self.profile.domicile, "")
        self.assertEqual(self.profile.domicile_code, "")
        self.assertEqual(self.profile.preferred_categories, [])

    @patch("accounts.forms.regions.lookup_region", side_effect=regions.RegionServiceUnavailable)
    def test_settings_unverified_new_city_is_not_saved_during_provider_outage(self, lookup):
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:profile"), self.settings_data(
            username="renamed-region-member",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("domicile", response.context["profile_form"].errors)
        self.assertNotContains(response, TEST_API_KEY)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "region-member")
        self.assertEqual(self.profile.domicile, "")
        self.assertEqual(self.profile.domicile_code, "")

    @patch("accounts.forms.regions.lookup_region")
    def test_settings_manual_location_clears_previous_code(self, lookup):
        self.profile.domicile = DEPOK["label"]
        self.profile.domicile_code = DEPOK["code"]
        self.profile.save(update_fields=["domicile", "domicile_code"])
        self.login_after_credentials()
        response = self.client.post(reverse("accounts:profile"), self.settings_data(
            domicile="  Bandung, Jawa Barat  ", domicile_code="",
        ))
        self.assertRedirects(
            response, reverse("accounts:profile") + "#profile", fetch_redirect_response=False,
        )
        lookup.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, "Bandung, Jawa Barat")
        self.assertEqual(self.profile.domicile_code, "")

    def test_manual_profile_edit_clears_stale_code_but_unchanged_city_keeps_it(self):
        for domicile, expected_code in (
            (DEPOK["label"], DEPOK["code"]), ("Bandung, Jawa Barat", ""),
        ):
            with self.subTest(domicile=domicile):
                self.profile.domicile = DEPOK["label"]
                self.profile.domicile_code = DEPOK["code"]
                self.profile.save()
                form = ProfileForm({
                    "full_name": "Anggota Wilayah", "email": self.user.email,
                    "domicile": domicile, "birth_date": "2001-01-01", "social_contact": "",
                }, user=self.user, instance=self.profile)
                self.assertTrue(form.is_valid(), form.errors)
                form.save()
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.domicile_code, expected_code)
