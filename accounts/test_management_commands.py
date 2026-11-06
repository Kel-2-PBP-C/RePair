"""Administrative command failure paths use temporary files and synthetic identities."""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings

from .models import GoogleIdentity


class GoogleLinkCommandBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="command-member", email="command@example.com")

    def link(self, **overrides):
        options = {
            "username": self.user.username, "subject": "new-subject", "email": self.user.email,
            "confirm_verified": True, "stdout": StringIO(),
        }
        options.update(overrides)
        call_command("link_google_account", **options)
        return options["stdout"].getvalue()

    def test_missing_account_is_reported_without_creating_identity(self):
        with self.assertRaisesMessage(CommandError, "Username akun lama tidak ditemukan"):
            self.link(username="missing-member")
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_subject_must_be_ascii_and_fit_storage(self):
        for subject in ("subject-\u2603", "s" * 256):
            with self.subTest(subject=subject), self.assertRaisesMessage(CommandError, "subject tidak valid"):
                self.link(subject=subject)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_existing_identity_cannot_be_replaced(self):
        identity = GoogleIdentity.objects.create(user=self.user, subject="original", email=self.user.email)
        with self.assertRaisesMessage(CommandError, "identitas Google lain"):
            self.link(subject="replacement")
        identity.refresh_from_db()
        self.assertEqual(identity.subject, "original")
        self.assertEqual(GoogleIdentity.objects.count(), 1)

    @patch("accounts.management.commands.link_google_account.GoogleIdentity.objects.create", side_effect=IntegrityError("private database details"))
    def test_concurrent_identity_conflict_becomes_command_error(self, create):
        with self.assertRaisesMessage(CommandError, "Penautan berbenturan") as raised:
            self.link()
        self.assertNotIn("private database details", str(raised.exception))
        self.assertFalse(GoogleIdentity.objects.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_command_normalizes_identity_before_writing(self):
        output = self.link(subject="  normalized-subject  ", email="  COMMAND@EXAMPLE.COM  ")
        identity = GoogleIdentity.objects.get(user=self.user)
        self.assertEqual(identity.subject, "normalized-subject")
        self.assertEqual(identity.email, self.user.email)
        self.assertIn("berhasil ditautkan", output)


class ExportTrustedCACommandTests(SimpleTestCase):
    @patch("accounts.management.commands.export_bogortech_ca.ssl.create_default_context")
    def test_empty_system_ca_store_is_reported_without_writing_files(self, context):
        context.return_value.get_ca_certs.return_value = []
        with TemporaryDirectory(prefix="repair-ca-test-") as directory, override_settings(BASE_DIR=Path(directory)):
            with self.assertRaisesMessage(CommandError, "Tidak ada sertifikat CA"):
                call_command("export_bogortech_ca", stdout=StringIO())
            self.assertEqual(list(Path(directory).iterdir()), [])

    @patch("accounts.management.commands.export_bogortech_ca.ssl.create_default_context")
    @patch("accounts.management.commands.export_bogortech_ca.ssl.DER_cert_to_PEM_cert")
    @patch("accounts.management.commands.export_bogortech_ca.requests.certs.where")
    def test_export_combines_standard_bundle_and_trusted_system_certificates(self, where, convert, context):
        context.return_value.get_ca_certs.return_value = [b"system-der-one", b"system-der-two"]
        convert.side_effect = ["system-pem-one\n", "system-pem-two\n"]
        output = StringIO()
        with TemporaryDirectory(prefix="repair-ca-test-") as directory, override_settings(BASE_DIR=Path(directory)):
            standard = Path(directory) / "standard.pem"
            standard.write_text("standard-ca\n", encoding="ascii")
            where.return_value = str(standard)
            call_command("export_bogortech_ca", stdout=output)
            target = Path(directory) / ".test-artifacts" / "windows-ca-bundle.pem"
            self.assertEqual(target.read_text(encoding="ascii"), "standard-ca\nsystem-pem-one\nsystem-pem-two\n")
            self.assertIn(str(target.resolve()), output.getvalue())
        context.return_value.get_ca_certs.assert_called_once_with(binary_form=True)
        self.assertEqual([call.args[0] for call in convert.call_args_list], [b"system-der-one", b"system-der-two"])
