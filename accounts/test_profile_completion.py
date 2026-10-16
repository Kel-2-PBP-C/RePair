import time
from datetime import date

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import google_auth
from .models import GoogleIdentity, Profile
from .test_google_auth import GOOGLE_SETTINGS

User = get_user_model()


@override_settings(**GOOGLE_SETTINGS)
class GoogleProfileCompletionTests(TestCase):
    password = "ProfilMember!837Kuning"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="member-profile", email="profile@example.com",
            first_name="Nama Google", last_name="Anggota", password=cls.password,
        )
        cls.profile = Profile.objects.create(
            user=cls.user, birth_date=date(2002, 6, 3),
            social_contact="@member-original", email_notifications=False,
        )
        cls.identity = GoogleIdentity.objects.create(
            user=cls.user, subject="profile-onboarding-subject", email=cls.user.email,
        )

    def setUp(self):
        self.sign_in(self.client)

    def sign_in(self, client, *, credentials=True):
        client.force_login(self.user)
        session = client.session
        session[google_auth.REAUTH_KEY] = {"user_id": self.user.pk, "time": time.time()}
        if credentials:
            session[google_auth.CREDENTIALS_KEY] = {
                "user_id": self.user.pk,
                "auth_hash": self.user.get_session_auth_hash(),
            }
            session[google_auth.PROFILE_REVIEW_KEY] = self.user.pk
        else:
            session.pop(google_auth.CREDENTIALS_KEY, None)
        session.save()

    def data(self, **changes):
        data = {
            "action": "save", "username": self.user.username,
            "domicile": "Depok, Jawa Barat",
            "preferred_categories": ["elektronik", "buku"],
        }
        data.update(changes)
        return data

    def post(self, *, client=None, **changes):
        return (client or self.client).post(
            reverse("accounts:complete_profile"), self.data(**changes),
        )

    def assert_profile_unchanged(self):
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "member-profile")
        self.assertEqual(self.profile.domicile, "")
        self.assertEqual(self.profile.preferred_categories, [])
        self.assertFalse(self.profile.onboarding_completed)

    def test_incomplete_member_is_gated_until_onboarding_finishes(self):
        self.assertFalse(self.profile.onboarding_completed)
        response = self.client.get(reverse("core:landing"))
        self.assertRedirects(
            response, reverse("accounts:complete_profile"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.get(reverse("accounts:complete_profile")).status_code, 200,
        )
        self.assert_profile_unchanged()

    def test_save_changes_only_owned_username_location_and_category_preferences(self):
        other = User.objects.create_user(
            username="other-member", email="other@example.com", password=self.password,
        )
        other_profile = Profile.objects.create(user=other, domicile="Bandung")
        original_hash = self.user.password
        response = self.post(
            username="repair-new-name", user_id=other.pk, profile_id=other_profile.pk,
            email=other.email, full_name="Forged Name", first_name="Forged",
            last_name="Changed", password="Replaced!Password123",
            birth_date="1999-01-01", social_contact="@replacement",
            email_notifications="on", is_staff="on",
        )
        self.assertRedirects(
            response, reverse("core:landing"), fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.identity.refresh_from_db()
        other.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertEqual(self.user.username, "repair-new-name")
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertEqual(self.user.first_name, "Nama Google")
        self.assertEqual(self.user.last_name, "Anggota")
        self.assertEqual(self.user.password, original_hash)
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.identity.user_id, self.user.pk)
        self.assertEqual(self.identity.email, "profile@example.com")
        self.assertEqual(self.identity.subject, "profile-onboarding-subject")
        self.assertEqual(self.profile.domicile, "Depok, Jawa Barat")
        self.assertEqual(self.profile.preferred_categories, ["elektronik", "buku"])
        self.assertTrue(self.profile.onboarding_completed)
        self.assertEqual(self.profile.birth_date, date(2002, 6, 3))
        self.assertEqual(self.profile.social_contact, "@member-original")
        self.assertFalse(self.profile.email_notifications)
        self.assertEqual(other.username, "other-member")
        self.assertEqual(other_profile.domicile, "Bandung")
        self.assertFalse(other_profile.onboarding_completed)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertEqual(self.client.session[google_auth.CREDENTIALS_KEY], {
            "user_id": self.user.pk, "auth_hash": self.user.get_session_auth_hash(),
        })
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_saved_values_are_available_when_revisiting_onboarding(self):
        self.post(username="member-updated")
        response = self.client.get(reverse("accounts:complete_profile"))
        self.assertEqual(response.status_code, 200)
        form = response.context["completion_form"]
        self.assertEqual(form["username"].value(), "member-updated")
        self.assertEqual(form["domicile"].value(), "Depok, Jawa Barat")
        self.assertCountEqual(form["preferred_categories"].value(), ["elektronik", "buku"])

    def test_category_preferences_allow_multiple_choices_and_an_empty_selection(self):
        all_categories = ["elektronik", "buku", "pakaian", "perabot", "hobi"]
        self.assertEqual(self.post(preferred_categories=all_categories).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferred_categories, all_categories)
        data = self.data()
        data.pop("preferred_categories")
        self.assertEqual(
            self.client.post(reverse("accounts:complete_profile"), data).status_code, 302,
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferred_categories, [])

    def test_username_uses_django_normalization(self):
        response = self.post(username="ｒｅｐａｉｒ-ｎｅｗ")
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "repair-new")

    def test_invalid_username_and_location_do_not_partially_save(self):
        cases = [
            ({"username": ""}, "username"),
            ({"username": "invalid name"}, "username"),
            ({"username": "x" * 151}, "username"),
            ({"domicile": ""}, "domicile"),
            ({"domicile": " "}, "domicile"),
            ({"domicile": "x" * 151}, "domicile"),
        ]
        for changes, field in cases:
            with self.subTest(changes=changes):
                response = self.post(**changes)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["completion_form"].errors)
                self.assert_profile_unchanged()
                self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)

    def test_duplicate_username_including_normalized_duplicate_is_rejected(self):
        User.objects.create_user(username="taken-member", password=self.password)
        for username in ("taken-member", "ｔａｋｅｎ-ｍｅｍｂｅｒ"):
            with self.subTest(username=username):
                response = self.post(username=username)
                self.assertEqual(response.status_code, 200)
                self.assertIn("username", response.context["completion_form"].errors)
                self.assert_profile_unchanged()

    def test_unknown_category_rejects_whole_profile_update(self):
        response = self.post(
            username="changed-name", preferred_categories=["buku", "not-a-category"],
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("preferred_categories", response.context["completion_form"].errors)
        self.assert_profile_unchanged()
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)

    def test_completed_profile_still_requires_valid_save_to_finish_current_review(self):
        self.profile.domicile = "Bogor"
        self.profile.preferred_categories = ["hobi"]
        self.profile.onboarding_completed = True
        self.profile.save()
        session = self.client.session
        session["google_profile_next"] = "/accounts/profile/?tab=profile#profile"
        session.save()
        self.assertRedirects(
            self.client.get(reverse("core:landing")), reverse("accounts:complete_profile"),
            fetch_redirect_response=False,
        )
        response = self.post(username="invalid username")
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["completion_form"].errors)
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, "Bogor")
        self.assertEqual(self.profile.preferred_categories, ["hobi"])
        response = self.post(username="reviewed-member")
        self.assertRedirects(
            response, "/accounts/profile/?tab=profile#profile", fetch_redirect_response=False,
        )
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, self.client.session)
        self.user.refresh_from_db()
        self.identity.refresh_from_db()
        self.assertEqual(self.user.username, "reviewed-member")
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.identity.user_id, self.user.pk)
        self.assertEqual(self.identity.subject, "profile-onboarding-subject")
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_skip_marks_completion_without_saving_partial_or_invalid_fields(self):
        session = self.client.session
        session["google_profile_next"] = "/accounts/profile/#profile"
        session.save()
        response = self.post(
            action="skip", username="invalid username", domicile="Changed location",
            preferred_categories=["buku", "unknown"], email="forged@example.com",
        )
        self.assertRedirects(
            response, "/accounts/profile/#profile", fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "member-profile")
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.profile.domicile, "")
        self.assertEqual(self.profile.preferred_categories, [])
        self.assertEqual(self.profile.birth_date, date(2002, 6, 3))
        self.assertTrue(self.profile.onboarding_completed)
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse("core:landing")).status_code, 200)

    def test_previous_skip_is_preserved_but_review_is_required_after_new_credentials(self):
        self.assertEqual(self.post(action="skip").status_code, 302)
        client = Client()
        self.sign_in(client, credentials=False)
        self.assertRedirects(
            client.get(reverse("core:landing")), reverse("accounts:credentials"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            client.post(reverse("accounts:credentials"), {
                "username": self.user.username, "password": self.password,
            }),
            reverse("accounts:complete_profile"), fetch_redirect_response=False,
        )
        self.assertEqual(client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)
        self.assertRedirects(
            client.get(reverse("core:landing")), reverse("accounts:complete_profile"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            client.get(reverse("accounts:complete_profile")).context["completion_form"]["domicile"].value(), "",
        )
        self.assertEqual(self.post(client=client, action="skip").status_code, 302)
        self.assertNotIn(google_auth.PROFILE_REVIEW_KEY, client.session)
        self.assertEqual(client.get(reverse("core:landing")).status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.onboarding_completed)
        self.assertEqual(self.profile.domicile, "")

    def test_get_with_skip_query_does_not_change_profile(self):
        response = self.client.get(reverse("accounts:complete_profile"), {"action": "skip"})
        self.assertEqual(response.status_code, 200)
        self.assert_profile_unchanged()
        self.assertEqual(self.client.session[google_auth.PROFILE_REVIEW_KEY], self.user.pk)

    def test_stored_next_is_sanitized_for_save_and_skip(self):
        for action in ("save", "skip"):
            for next_url in (
                "https://attacker.example/", "//attacker.example/",
                "/\\attacker.example/", reverse("accounts:complete_profile"),
                reverse("accounts:credentials"),
            ):
                with self.subTest(action=action, next_url=next_url):
                    session = self.client.session
                    session["google_profile_next"] = next_url
                    session.save()
                    self.assertRedirects(
                        self.post(action=action), reverse("core:landing"),
                        fetch_redirect_response=False,
                    )
                    self.assertNotIn("google_profile_next", self.client.session)

    def test_save_and_skip_require_csrf_even_after_google_and_credentials(self):
        for action in ("save", "skip"):
            with self.subTest(action=action):
                client = Client(enforce_csrf_checks=True)
                self.sign_in(client)
                self.assertEqual(self.post(client=client, action=action).status_code, 403)
                self.assert_profile_unchanged()
                self.assertEqual(
                    client.get(reverse("accounts:complete_profile")).status_code, 200,
                )
                response = self.post(
                    client=client, action=action,
                    csrfmiddlewaretoken=client.cookies["csrftoken"].value,
                )
                self.assertEqual(response.status_code, 302)
                self.profile.refresh_from_db()
                self.profile.domicile = ""
                self.profile.preferred_categories = []
                self.profile.onboarding_completed = False
                self.profile.save()

    def test_onboarding_cannot_bypass_the_credential_gate(self):
        client = Client()
        self.sign_in(client, credentials=False)
        for method in (client.get, client.post):
            with self.subTest(method=method.__name__):
                response = method(reverse("accounts:complete_profile"), self.data(action="skip"))
                self.assertRedirects(
                    response, reverse("accounts:credentials"), fetch_redirect_response=False,
                )
                self.assert_profile_unchanged()

    def test_guest_cannot_submit_or_skip_another_users_profile(self):
        client = Client()
        for method in (client.get, client.post):
            response = method(
                reverse("accounts:complete_profile"), self.data(action="skip", user_id=self.user.pk),
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:auth")))
            self.assertNotIn(SESSION_KEY, client.session)
            self.assert_profile_unchanged()

    def test_onboarding_rejects_other_http_methods(self):
        self.assertEqual(self.client.put(reverse("accounts:complete_profile"), {}).status_code, 405)
        self.assert_profile_unchanged()
