"""Persistence guarantees for account forms, including deferred saves and rollback."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase

from .forms import GoogleProfileCompletionForm, ProfileForm, RegistrationForm
from .models import GoogleIdentity, Profile


User = get_user_model()


class AccountFormPersistenceTests(TestCase):
    password = "RakitAkun!729Biru"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="original", email="original@example.com", password=cls.password,
            first_name="Original", last_name="Member",
        )
        cls.profile = Profile.objects.create(
            user=cls.user, domicile="Depok", birth_date="2003-05-04",
            preferred_categories=["buku"],
        )

    def registration_form(self):
        return RegistrationForm(data={
            "username": "new-member", "full_name": "New Member",
            "email": "NEW@example.com", "domicile": "Bandung",
            "birth_date": "2004-06-07", "password1": self.password,
            "password2": self.password,
        })

    def profile_form(self):
        return ProfileForm(user=self.user, instance=self.profile, data={
            "username": "updated", "full_name": "Updated Member",
            "email": "UPDATED@example.com", "domicile": "Bandung",
            "birth_date": "2003-05-04", "preferred_categories": ["hobi"],
        })

    def completion_form(self):
        return GoogleProfileCompletionForm(
            user=self.user, instance=self.profile,
            data={"username": "onboarded", "domicile": "Bandung", "preferred_categories": ["hobi"]},
        )

    def test_registration_deferred_save_hashes_password_without_writing_user_or_profile(self):
        form = self.registration_form()
        self.assertTrue(form.is_valid(), form.errors)

        new_user = form.save(commit=False)

        self.assertIsNone(new_user.pk)
        self.assertEqual(new_user.first_name, "New Member")
        self.assertEqual(new_user.email, "new@example.com")
        self.assertTrue(new_user.check_password(self.password))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)

    def test_registration_rolls_back_user_when_profile_write_fails(self):
        form = self.registration_form()
        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(Profile.objects, "update_or_create", side_effect=DatabaseError("unavailable")):
            with self.assertRaises(DatabaseError):
                form.save()

        self.assertFalse(User.objects.filter(username="new-member").exists())
        self.assertEqual(Profile.objects.count(), 1)

    def test_profile_deferred_save_updates_objects_without_persisting_either_model(self):
        form = self.profile_form()
        self.assertTrue(form.is_valid(), form.errors)

        updated_profile = form.save(commit=False)

        self.assertEqual(updated_profile.domicile, "Bandung")
        self.assertEqual(updated_profile.preferred_categories, ["hobi"])
        self.assertEqual(self.user.username, "updated")
        self.assertEqual(self.user.first_name, "Updated Member")
        self.assertEqual(self.user.last_name, "")
        self.assertEqual(self.user.email, "updated@example.com")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "original")
        self.assertEqual(self.user.last_name, "Member")
        self.assertEqual(self.profile.domicile, "Depok")
        self.assertEqual(self.profile.preferred_categories, ["buku"])

    def test_profile_write_failure_rolls_back_the_user_update(self):
        form = self.profile_form()
        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(Profile, "save", side_effect=DatabaseError("unavailable")):
            with self.assertRaises(DatabaseError):
                form.save()

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "original")
        self.assertEqual(self.user.email, "original@example.com")
        self.assertEqual(self.profile.domicile, "Depok")

    def test_onboarding_deferred_save_does_not_persist_completion_or_username(self):
        form = self.completion_form()
        self.assertTrue(form.is_valid(), form.errors)

        updated_profile = form.save(commit=False)

        self.assertTrue(updated_profile.onboarding_completed)
        self.assertEqual(self.user.username, "onboarded")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "original")
        self.assertFalse(self.profile.onboarding_completed)
        self.assertEqual(self.profile.domicile, "Depok")

    def test_onboarding_profile_failure_rolls_back_username_and_completion(self):
        form = self.completion_form()
        self.assertTrue(form.is_valid(), form.errors)

        with patch.object(Profile, "save", side_effect=DatabaseError("unavailable")):
            with self.assertRaises(DatabaseError):
                form.save()

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, "original")
        self.assertFalse(self.profile.onboarding_completed)

    def test_model_labels_identify_the_user_without_exposing_identity_secrets(self):
        identity = GoogleIdentity.objects.create(
            user=self.user, subject="private-google-subject", email=self.user.email,
        )
        self.assertEqual(str(self.profile), "Profil original")
        self.assertEqual(str(identity), "Google: original")
        self.assertNotIn(identity.subject, str(identity))

    def test_valid_region_code_does_not_erase_invalid_location_field_errors(self):
        form = ProfileForm(user=self.user, instance=self.profile, data={
            "username": self.user.username, "full_name": "Original Member",
            "email": self.user.email, "domicile": "x" * 151, "domicile_code": "32.76",
            "birth_date": "2003-05-04",
        })
        with patch("accounts.forms.regions.lookup_region", return_value={
            "code": "32.76", "label": "Kota Depok, Jawa Barat",
        }) as lookup:
            self.assertFalse(form.is_valid())
        lookup.assert_called_once_with("32.76")
        self.assertIn("domicile", form.errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.domicile, "Depok")
