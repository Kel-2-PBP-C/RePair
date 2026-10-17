from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.models import Session
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from barter_details.models import Barter
from .models import Profile

User = get_user_model()


@override_settings(GOOGLE_ONLY_AUTH=False)
class AccountTests(TestCase):
    password = "RakitAkun!729Biru"
    replacement_password = "GantiSandi!938Hijau"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="noe", email="noe@example.com", password=cls.password, first_name="Noe Andrew"
        )
        cls.profile = Profile.objects.create(
            user=cls.user, domicile="Depok", birth_date="2003-05-04", social_contact="@noe"
        )

    def registration_data(self, **overrides):
        data = {
            "mode": "register", "username": "anggota", "full_name": "Anggota Baru",
            "email": "anggota@example.com", "domicile": "Jakarta", "birth_date": "2004-03-02",
            "social_contact": "", "password1": self.password, "password2": self.password,
        }
        data.update(overrides)
        return data

    def profile_data(self, **overrides):
        data = {
            "action": "profile", "full_name": "Noe Baru", "email": "baru@example.com",
            "domicile": "Bandung", "birth_date": "2002-08-09", "social_contact": "@baru",
        }
        data.update(overrides)
        return data

    def login(self, **overrides):
        data = {"username": "noe", "password": self.password}
        data.update(overrides)
        return self.client.post(reverse("accounts:auth"), data)

    def test_entry_redirects_guest_to_auth(self):
        self.assertRedirects(self.client.get("/"), reverse("accounts:auth"))

    def test_entry_redirects_member_to_landing(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get("/"), reverse("core:landing"))

    def test_auth_has_login_and_register_on_one_screen(self):
        login_response = self.client.get(reverse("accounts:auth"))
        register_response = self.client.get(reverse("accounts:auth"), {"mode": "register"})
        self.assertTemplateUsed(login_response, "accounts/legacy_auth.html")
        self.assertTemplateUsed(register_response, "accounts/legacy_auth.html")
        self.assertEqual(login_response.context["auth_mode"], "login")
        self.assertEqual(register_response.context["auth_mode"], "register")

    def test_login_establishes_django_session_and_opens_landing(self):
        self.assertRedirects(self.login(), reverse("core:landing"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_login_accepts_case_insensitive_email(self):
        self.assertRedirects(self.login(username="NOE@EXAMPLE.COM"), reverse("core:landing"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_ambiguous_legacy_email_cannot_choose_an_account(self):
        User.objects.create_user(username="other", email="NOE@example.com", password=self.password)
        response = self.login(username="noe@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["auth_form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def create_identifier_collision(self):
        return User.objects.create_user(
            username="noe@example.com", email="username-owner@example.com",
            password=self.replacement_password,
        )

    def test_exact_username_authenticates_when_another_account_uses_it_as_email(self):
        username_owner = self.create_identifier_collision()
        response = self.login(username="noe@example.com", password=self.replacement_password)
        self.assertRedirects(response, reverse("core:landing"))
        self.assertEqual(self.client.session[SESSION_KEY], str(username_owner.pk))

    def test_email_owner_can_login_when_email_also_matches_another_username(self):
        self.create_identifier_collision()
        response = self.login(username="noe@example.com", password=self.password)
        self.assertRedirects(response, reverse("core:landing"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_identifier_collision_with_wrong_password_returns_generic_error(self):
        self.create_identifier_collision()
        response = self.login(username="noe@example.com", password="wrong")
        errors = response.context["auth_form"].non_field_errors().as_data()
        self.assertEqual(errors[0].code, "invalid_login")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_identifier_collision_does_not_allow_inactive_username_owner(self):
        username_owner = self.create_identifier_collision()
        username_owner.is_active = False
        username_owner.save(update_fields=["is_active"])
        response = self.login(username="noe@example.com", password=self.replacement_password)
        self.assertTrue(response.context["auth_form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_identifier_collision_does_not_allow_inactive_email_owner(self):
        self.create_identifier_collision()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.login(username="noe@example.com", password=self.password)
        self.assertTrue(response.context["auth_form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_wrong_password_is_rejected(self):
        response = self.login(password="wrong")
        self.assertTrue(response.context["auth_form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_account_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.login()
        self.assertTrue(response.context["auth_form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_empty_login_returns_required_field_errors(self):
        response = self.client.post(reverse("accounts:auth"), {})
        self.assertIn("username", response.context["auth_form"].errors)
        self.assertIn("password", response.context["auth_form"].errors)

    def test_registration_saves_profile_and_logs_in(self):
        response = self.client.post(reverse("accounts:auth"), self.registration_data())
        self.assertRedirects(response, reverse("core:landing"))
        user = User.objects.get(username="anggota")
        self.assertEqual(user.first_name, "Anggota Baru")
        self.assertEqual(user.profile.domicile, "Jakarta")
        self.assertEqual(user.profile.social_contact, "")
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_registration_rejects_duplicate_email_ignoring_case(self):
        response = self.client.post(
            reverse("accounts:auth"), self.registration_data(email="NOE@EXAMPLE.COM")
        )
        self.assertIn("email", response.context["auth_form"].errors)
        self.assertFalse(User.objects.filter(username="anggota").exists())

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(reverse("accounts:auth"), self.registration_data(username="noe"))
        self.assertIn("username", response.context["auth_form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rejects_future_birth_date(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.client.post(
            reverse("accounts:auth"), self.registration_data(birth_date=tomorrow.isoformat())
        )
        self.assertIn("birth_date", response.context["auth_form"].errors)
        self.assertFalse(User.objects.filter(username="anggota").exists())

    def test_registration_rejects_invalid_email_and_mismatched_password(self):
        response = self.client.post(
            reverse("accounts:auth"), self.registration_data(email="invalid", password2="different")
        )
        errors = response.context["auth_form"].errors
        self.assertIn("email", errors)
        self.assertIn("password2", errors)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_registration_uses_django_password_validation(self):
        response = self.client.post(
            reverse("accounts:auth"), self.registration_data(password1="123", password2="123")
        )
        self.assertIn("password2", response.context["auth_form"].errors)
        self.assertFalse(User.objects.filter(username="anggota").exists())

    def test_empty_registration_preserves_errors_in_register_mode(self):
        response = self.client.post(reverse("accounts:auth"), {"mode": "register"})
        self.assertEqual(response.context["auth_mode"], "register")
        self.assertIn("full_name", response.context["auth_form"].errors)
        self.assertIn("username", response.context["auth_form"].errors)

    def test_login_can_return_to_safe_local_page(self):
        self.assertRedirects(self.login(next=reverse("accounts:profile")), reverse("accounts:profile"))

    def test_login_blocks_external_and_auth_loop_redirects(self):
        targets = [
            "https://malicious.example/", "//malicious.example/", "\\\\malicious.example/",
            "javascript:alert(1)", reverse("accounts:auth") + "?mode=register",
        ]
        for target in targets:
            with self.subTest(target=target):
                self.client.logout()
                self.assertRedirects(self.login(next=target), reverse("core:landing"))

    def test_register_uses_safe_next(self):
        response = self.client.post(
            reverse("accounts:auth"), self.registration_data(next=reverse("accounts:profile"))
        )
        self.assertRedirects(response, reverse("accounts:profile"))

    def test_authenticated_auth_visit_redirects_to_landing(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("accounts:auth")), reverse("core:landing"))

    def test_legacy_auth_urls_redirect_to_canonical_screen(self):
        for name in ("login", "register"):
            with self.subTest(name=name):
                self.assertRedirects(
                    self.client.get(reverse(f"accounts:{name}")),
                    f"{reverse('accounts:auth')}?mode={name}",
                )

    def test_legacy_login_post_still_authenticates(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "noe", "password": self.password,
        })
        self.assertRedirects(response, reverse("core:landing"))

    def test_legacy_register_post_still_registers(self):
        self.assertRedirects(
            self.client.post(reverse("accounts:register"), self.registration_data()),
            reverse("core:landing"),
        )

    def test_profile_requires_authentication_for_get_and_post(self):
        target = reverse("accounts:profile")
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(target)
                self.assertRedirects(response, f"{reverse('accounts:auth')}?next={target}")

    def test_profile_and_settings_share_one_screen(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertTemplateUsed(response, "accounts/profile_settings.html")
        for name in ("profile_form", "preferences_form", "password_form", "deactivate_form"):
            self.assertIn(name, response.context)
        self.assertRedirects(
            self.client.get(reverse("accounts:settings")), f"{reverse('accounts:profile')}#settings"
        )

    def test_preexisting_user_without_profile_gets_profile(self):
        self.profile.delete()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_profile_update_changes_only_logged_in_user(self):
        other = User.objects.create_user(username="other", email="other@example.com", password=self.password)
        other_profile = Profile.objects.create(user=other, domicile="Bogor")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"), self.profile_data(user=other.pk, profile_id=other_profile.pk)
        )
        self.assertRedirects(response, f"{reverse('accounts:profile')}#profile")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        other.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Noe Baru")
        self.assertEqual(self.user.email, "baru@example.com")
        self.assertEqual(self.profile.domicile, "Bandung")
        self.assertEqual(other.email, "other@example.com")
        self.assertEqual(other_profile.domicile, "Bogor")

    def test_settings_profile_can_update_username_and_categories_only_for_current_user(self):
        other = User.objects.create_user(
            username="other", email="other@example.com", password=self.password,
        )
        other_profile = Profile.objects.create(
            user=other, domicile="Bogor", preferred_categories=["perabot"],
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            username="noe-baru", preferred_categories=["elektronik", "buku"],
            preferred_categories_present="1", user=other.pk, profile_id=other_profile.pk,
        ))
        self.assertRedirects(response, f"{reverse('accounts:profile')}#profile")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        other.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertEqual(self.user.username, "noe-baru")
        self.assertEqual(self.profile.preferred_categories, ["elektronik", "buku"])
        self.assertEqual(other.username, "other")
        self.assertEqual(other_profile.preferred_categories, ["perabot"])
        self.assertEqual(other_profile.domicile, "Bogor")

    def test_legacy_profile_post_omitting_username_and_categories_preserves_them(self):
        self.profile.preferred_categories = ["buku", "hobi"]
        self.profile.save(update_fields=["preferred_categories"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data())
        self.assertRedirects(response, f"{reverse('accounts:profile')}#profile")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "noe")
        self.assertEqual(self.profile.preferred_categories, ["buku", "hobi"])
        self.assertEqual(self.profile.domicile, "Bandung")

    def test_settings_profile_allows_deselecting_all_categories(self):
        self.profile.preferred_categories = ["buku", "hobi"]
        self.profile.save(update_fields=["preferred_categories"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            username=self.user.username, preferred_categories_present="1",
        ))
        self.assertRedirects(response, f"{reverse('accounts:profile')}#profile")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferred_categories, [])

    def test_settings_profile_rejects_duplicate_username_without_partial_save(self):
        User.objects.create_user(username="other", password=self.password)
        self.profile.preferred_categories = ["hobi"]
        self.profile.save(update_fields=["preferred_categories"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            username="other", preferred_categories=["buku"], preferred_categories_present="1",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "noe")
        self.assertEqual(self.user.first_name, "Noe Andrew")
        self.assertEqual(self.user.email, "noe@example.com")
        self.assertEqual(self.profile.domicile, "Depok")
        self.assertEqual(self.profile.preferred_categories, ["hobi"])

    def test_settings_profile_explicit_empty_username_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(username="  "))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "noe")
        self.assertEqual(self.user.first_name, "Noe Andrew")

    def test_settings_profile_rejects_invalid_username_format(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            username="name with spaces",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "noe")

    def test_settings_profile_rejects_unknown_category_without_partial_save(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            username="noe-baru", preferred_categories=["unknown-category"],
            preferred_categories_present="1",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("preferred_categories", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "noe")
        self.assertEqual(self.profile.domicile, "Depok")

    def test_settings_summary_uses_identity_initials_and_unknown_statistics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.context["profile_initials"], "NA")
        self.assertEqual(response.context["profile_stats"], {
            "items_exchanged": None, "reputation_percent": None,
        })

    def test_profile_cannot_use_another_users_email(self):
        User.objects.create_user(username="other", email="other@example.com", password=self.password)
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(email="OTHER@EXAMPLE.COM"))
        self.assertIn("email", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, "noe@example.com")
        self.assertEqual(self.profile.domicile, "Depok")

    def test_profile_can_keep_its_own_email(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(email="NOE@example.com"))
        self.assertRedirects(response, f"{reverse('accounts:profile')}#profile")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "noe@example.com")

    def test_invalid_profile_retains_input_without_partial_save(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(birth_date="bad-date"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "profile")
        self.assertEqual(response.context["profile_form"]["full_name"].value(), "Noe Baru")
        self.assertIn("birth_date", response.context["profile_form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Noe Andrew")

    def test_profile_rejects_future_birth_date(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), self.profile_data(
            birth_date=(timezone.localdate() + timedelta(days=1)).isoformat()
        ))
        self.assertIn("birth_date", response.context["profile_form"].errors)

    def test_preferences_save_and_do_not_change_other_profile_fields(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "action": "preferences", "language": "en", "profile_visibility": "on",
        })
        self.assertRedirects(response, f"{reverse('accounts:profile')}#settings")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.email_notifications)
        self.assertTrue(self.profile.profile_visibility)
        self.assertEqual(self.profile.language, "en")
        self.assertEqual(self.profile.domicile, "Depok")

    def test_invalid_language_does_not_save_preferences(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {"action": "preferences", "language": "xx"})
        self.assertIn("language", response.context["preferences_form"].errors)
        self.assertEqual(response.context["active_section"], "settings")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_notifications)
        self.assertEqual(self.profile.language, "id")

    def test_password_change_checks_old_password_and_preserves_current_session(self):
        self.client.force_login(self.user)
        other_session = Client()
        other_session.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "action": "password", "old_password": self.password,
            "new_password1": self.replacement_password, "new_password2": self.replacement_password,
        })
        self.assertRedirects(response, f"{reverse('accounts:profile')}#settings")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.replacement_password))
        self.assertFalse(self.user.check_password(self.password))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertEqual(other_session.get(reverse("accounts:profile")).status_code, 302)

    def test_wrong_old_password_does_not_change_password(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "action": "password", "old_password": "wrong",
            "new_password1": self.replacement_password, "new_password2": self.replacement_password,
        })
        self.assertIn("old_password", response.context["password_form"].errors)
        self.assertEqual(response.context["active_section"], "settings")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_password_form_validated_before_account_deletion_cannot_recreate_user(self):
        from .deletion import permanently_delete_account

        self.client.force_login(self.user)
        user_id = self.user.pk
        original_clean = PasswordChangeForm.clean

        def delete_after_validation(form):
            cleaned = original_clean(form)
            self.assertFalse(form.errors)
            permanently_delete_account(user_id=user_id, password=self.password)
            return cleaned

        with patch.object(PasswordChangeForm, "clean", delete_after_validation):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "password", "old_password": self.password,
                "new_password1": self.replacement_password, "new_password2": self.replacement_password,
            })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(User.objects.filter(email=self.user.email).exists())
        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_password_change_rechecks_old_password_changed_after_form_validation(self):
        self.client.force_login(self.user)
        original_clean = PasswordChangeForm.clean
        concurrent_password = "OtherDevice!572Kuning"

        def change_after_validation(form):
            cleaned = original_clean(form)
            self.assertFalse(form.errors)
            current_user = User.objects.get(pk=self.user.pk)
            current_user.set_password(concurrent_password)
            current_user.save(update_fields=["password"])
            return cleaned

        with patch.object(PasswordChangeForm, "clean", change_after_validation):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "password", "old_password": self.password,
                "new_password1": self.replacement_password, "new_password2": self.replacement_password,
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["password_form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(concurrent_password))
        self.assertFalse(self.user.check_password(self.replacement_password))

    def test_deactivate_requires_password_and_confirmation(self):
        self.client.force_login(self.user)
        for data, field in (
            ({"action": "deactivate", "password": "wrong", "confirm": "on"}, "password"),
            ({"action": "deactivate", "password": self.password}, "confirm"),
        ):
            with self.subTest(field=field):
                response = self.client.post(reverse("accounts:profile"), data)
                self.assertIn(field, response.context["deactivate_form"].errors)
                self.user.refresh_from_db()
                self.assertTrue(self.user.is_active)
                self.assertIn(SESSION_KEY, self.client.session)

    def test_delete_requires_password_confirmation_and_csrf(self):
        self.client.force_login(self.user)
        for data, field in (
            ({"action": "delete", "password": "wrong", "confirm": "on"}, "password"),
            ({"action": "delete", "password": self.password}, "confirm"),
        ):
            with self.subTest(field=field):
                response = self.client.post(reverse("accounts:profile"), data)
                self.assertIn(field, response.context["deactivate_form"].errors)
                self.user.refresh_from_db()
                self.assertTrue(self.user.is_active)
                self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse("accounts:profile"), {
            "action": "delete", "password": self.password, "confirm": "on",
        }).status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(csrf_client.session[SESSION_KEY], str(self.user.pk))

    def test_deactivate_alias_permanently_removes_account_data_and_blocks_login(self):
        self.client.force_login(self.user)
        user_id = self.user.pk
        response = self.client.post(reverse("accounts:profile"), {
            "action": "deactivate", "password": self.password, "confirm": "on",
        })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_delete_uses_current_user_preserves_other_account_and_clears_session(self):
        other = User.objects.create_user(username="other", email="other@example.com", password=self.password)
        other_profile = Profile.objects.create(user=other, domicile="Bogor")
        own_listing = Barter.objects.create(
            owner=self.user, thumbnail="https://example.com/own.jpg", title="Own listing",
            description="A used book", item_year=2024, condition=80, item_location="Depok",
        )
        other_listing = Barter.objects.create(
            owner=other, thumbnail="https://example.com/other.jpg", title="Other listing",
            description="Another used book", item_year=2023, condition=70, item_location="Bogor",
        )
        self.client.force_login(self.user)
        another_device = Client()
        another_device.force_login(self.user)
        other_client = Client()
        other_client.force_login(other)
        other_session_key = other_client.session.session_key
        another_device_key = another_device.session.session_key
        user_id = self.user.pk
        session = self.client.session
        session["private_session_marker"] = "must-be-cleared"
        session.save()
        old_session_key = session.session_key
        response = self.client.post(reverse("accounts:profile"), {
            "action": "delete", "password": self.password, "confirm": "on",
            "user": other.pk, "profile_id": other_profile.pk,
        })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertFalse(Barter.objects.filter(pk=own_listing.pk).exists())
        other.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertTrue(other.is_active)
        self.assertEqual(other.email, "other@example.com")
        self.assertEqual(other_profile.domicile, "Bogor")
        self.assertTrue(Barter.objects.filter(pk=other_listing.pk).exists())
        self.assertTrue(Session.objects.filter(session_key=other_session_key).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn("private_session_marker", self.client.session)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=another_device_key).exists())
        with override_settings(GOOGLE_ONLY_AUTH=True):
            landing = self.client.get(reverse("home"))
        self.assertEqual(landing.status_code, 200)
        self.assertFalse(landing.wsgi_request.user.is_authenticated)
        self.assertContains(landing, "data-account-deleted-notifications")
        self.assertContains(landing, "data-notification")
        self.assertContains(landing, 'role="status"')
        self.assertContains(
            landing,
            "Akun dan data milikmu berhasil dihapus permanen. "
            "Kamu dapat mendaftar lagi dengan email yang sama.",
            count=1,
        )
        self.assertNotContains(landing, 'class="brand-messages"')
        self.assertFalse(self.client.login(username=self.user.username, password=self.password))

    def test_delete_failure_rolls_back_account_data_and_sessions(self):
        self.client.force_login(self.user)
        old_session_key = self.client.session.session_key
        with patch.object(User, "delete", side_effect=DatabaseError("simulated storage failure")):
            response = self.client.post(reverse("accounts:profile"), {
                "action": "delete", "password": self.password, "confirm": "on",
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["deactivate_form"].non_field_errors())
        self.assertTrue(User.objects.filter(pk=self.user.pk, is_active=True).exists())
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertTrue(Session.objects.filter(session_key=old_session_key).exists())
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_unknown_settings_action_is_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("accounts:profile"), {"action": "admin"}).status_code, 400)

    def test_logout_is_post_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:auth"))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_csrf_required_for_login_register_profile_and_logout(self):
        csrf_client = Client(enforce_csrf_checks=True)
        auth_url = reverse("accounts:auth")
        for data in ({"username": "noe", "password": self.password}, self.registration_data()):
            with self.subTest(mode=data.get("mode", "login")):
                self.assertEqual(csrf_client.post(auth_url, data).status_code, 403)
        csrf_client.get(auth_url)
        csrf_token = csrf_client.cookies["csrftoken"].value
        self.assertRedirects(csrf_client.post(auth_url, {
            "username": "noe", "password": self.password, "csrfmiddlewaretoken": csrf_token,
        }), reverse("core:landing"))
        self.assertEqual(csrf_client.post(reverse("accounts:profile"), self.profile_data()).status_code, 403)
        self.assertEqual(csrf_client.post(reverse("accounts:logout")).status_code, 403)
        csrf_token = csrf_client.cookies["csrftoken"].value
        self.assertRedirects(csrf_client.post(reverse("accounts:logout"), {
            "csrfmiddlewaretoken": csrf_token,
        }), reverse("accounts:auth"))
