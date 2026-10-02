from datetime import timedelta

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Profile

User = get_user_model()


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
        self.assertTemplateUsed(login_response, "accounts/auth.html")
        self.assertTemplateUsed(register_response, "accounts/auth.html")
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

    def test_deactivation_keeps_data_logs_out_and_blocks_login(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "action": "deactivate", "password": self.password, "confirm": "on",
        })
        self.assertRedirects(response, reverse("accounts:auth"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

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
