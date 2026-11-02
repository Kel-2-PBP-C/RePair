"""Unit tests for the Git guard's parsers and failure paths; no project Git mutations."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import runpy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import call, patch

from scripts import check_git_safety as guard


OID = "a" * 40
REMOTE = "b" * 40
ZERO = "0" * 40


class GitCommandTests(TestCase):
    @patch.object(guard.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"data"))
    def test_git_returns_raw_bytes_on_success(self, run):
        self.assertEqual(guard.git("cat-file", "blob", OID), b"data")
        self.assertEqual(run.call_args.args[0], ["git", "cat-file", "blob", OID])
        self.assertFalse(run.call_args.kwargs["check"])

    @patch.object(guard.subprocess, "run", side_effect=OSError("private path"))
    def test_missing_git_fails_closed_without_exposing_os_details(self, run):
        with self.assertRaisesRegex(guard.SafetyError, "Git is unavailable") as raised:
            guard.git("status")
        self.assertNotIn("private path", str(raised.exception))

    @patch.object(guard.subprocess, "run", return_value=SimpleNamespace(returncode=128, stderr=b"private remote URL"))
    def test_failed_git_command_does_not_echo_credentials_from_stderr(self, run):
        with self.assertRaisesRegex(guard.SafetyError, "could not be inspected") as raised:
            guard.git("fetch")
        self.assertNotIn("private remote URL", str(raised.exception))


class GitPathAndCredentialTests(TestCase):
    def test_paths_reject_case_variants_nested_environments_and_worktrees(self):
        for path in (".ENV", "nested/.env.example", "ENV/config.py", "nested/repair-feature/a.py", "BACKUP.DB"):
            with self.subTest(path=path):
                self.assertIsNotNone(guard.path_problem(path, "100644"))
        self.assertEqual(guard.path_problem("", "100644"), "invalid Git path")
        self.assertEqual(guard.path_problem("vendor/lib", "160000"), "embedded repository / Git submodule")

    def test_regular_source_root_example_and_similarly_named_files_are_allowed(self):
        for path in ("accounts/views.py", ".env.example", "repair-guide.md", "environment/docs.md"):
            with self.subTest(path=path):
                self.assertIsNone(guard.path_problem(path, "100644"))

    def test_non_utf8_git_path_roundtrips_without_losing_bytes(self):
        encoded = b"file-\xff.py"
        self.assertEqual(guard.decode_path(encoded).encode("utf-8", errors="surrogateescape"), encoded)

    def test_binary_payload_is_not_mistaken_for_text_credentials(self):
        fake_secret = b"GOC" + b"SPX-" + b"x" * 16
        self.assertEqual(guard.credential_problems(b"\x00" + fake_secret, "icon.png"), [])

    def test_all_supported_credential_families_are_recognized_without_returning_values(self):
        fixtures = (
            (b"GOC" + b"SPX-" + b"x" * 16, "Google OAuth client secret"),
            (b"SLK" + b"-ENT-" + b"1" * 8, "BogorTech API key"),
            (b"-----BEGIN " + b"RSA PRIVATE KEY-----", "private key"),
            (b"ya" + b"29." + b"x" * 30, "Google access token"),
            (b"AK" + b"IA" + b"A" * 16, "AWS access key"),
            (b"gh" + b"p_" + b"x" * 30, "GitHub token"),
            (b"https://" + b"test-user:test-password@example.invalid", "URL containing credentials"),
        )
        for credential, label in fixtures:
            with self.subTest(label=label):
                self.assertEqual(guard.credential_problems(credential, "config.txt"), [label])

    def test_environment_example_accepts_blank_and_explicit_placeholders(self):
        for placeholder in ("", "changeme", "change-me", "example", "placeholder", "your-secret", "your_secret", "replace-me", "replace_me", "<secret>"):
            with self.subTest(placeholder=placeholder):
                data = f"# SECRET=private\nHOST=example.invalid\nCOMMENT\nAPI_KEY='{placeholder}'\n".encode()
                self.assertEqual(guard.credential_problems(data, ".env.example"), [])

    def test_environment_example_rejects_secret_names_but_not_public_values(self):
        for name in ("TOKEN", "DB_PASSWORD", "CLIENT_SECRET", "API_KEY", "SECRET_VALUE"):
            with self.subTest(name=name):
                issues = guard.credential_problems(f"{name}=private-value\n".encode(), ".env.example")
                self.assertEqual(len(issues), 1)
                self.assertNotIn("private-value", issues[0])
        self.assertEqual(guard.credential_problems(b"PUBLIC_URL=https://example.invalid\n", ".env.example"), [])


class GitScannerTests(TestCase):
    @patch.object(guard, "git", return_value=b"safe source")
    def test_scan_blocks_paths_even_when_unchanged_and_reads_each_selected_blob_once(self, git):
        scanner = guard.Scanner()
        scanner.check_entries([
            ("100644", OID, ".env"),
            ("100644", OID, "first.py"),
            ("100644", OID, "second.py"),
            ("100644", REMOTE, "unchanged.py"),
        ], {"first.py", "second.py"})
        git.assert_called_once_with("cat-file", "blob", OID)
        self.assertEqual({path for path, _ in scanner.issues}, {".env"})

    @patch.object(guard, "git")
    def test_scan_credential_reports_only_path_and_type(self, git):
        git.return_value = b"GOC" + b"SPX-" + b"x" * 16
        scanner = guard.Scanner()
        scanner.check_entries([("100644", OID, "config.py")])
        self.assertEqual(scanner.issues, {("config.py", "Google OAuth client secret")})

    @patch.object(guard, "git")
    def test_index_reports_unmerged_entries_and_scans_only_changed_content(self, git):
        git.side_effect = [
            f"100644 {OID} 1\tconflict.py\0".encode()
            + f"100644 {OID} 0\tchanged.py\0".encode()
            + f"100644 {REMOTE} 0\tunchanged.py\0".encode(),
            b"changed.py\0", b"safe source",
        ]
        scanner = guard.Scanner()
        scanner.index()
        self.assertEqual(scanner.issues, {("conflict.py", "unresolved merge conflict")})
        self.assertEqual(git.call_args_list[-1], call("cat-file", "blob", OID))
        self.assertEqual(git.call_count, 3)

    @patch.object(guard, "git")
    def test_commit_cache_prevents_duplicate_tree_and_blob_scans(self, git):
        git.side_effect = [
            OID.encode(), f"100644 blob {REMOTE}\tREADME.md\0".encode(), b"safe source", OID.encode(),
        ]
        scanner = guard.Scanner()
        scanner.commit("HEAD")
        scanner.commit("HEAD")
        self.assertEqual(scanner.checked_trees, {OID})
        self.assertEqual(scanner.blobs, {REMOTE: b"safe source"})
        self.assertEqual(git.call_count, 4)

    def test_pre_push_rejects_malformed_lines_and_object_ids(self):
        for line in ("not valid", f"local invalid remote {REMOTE}", f"local {OID} remote invalid"):
            with self.subTest(line=line), self.assertRaises(guard.SafetyError):
                guard.Scanner().pre_push([line])

    @patch.object(guard, "git")
    def test_empty_push_and_deleted_refs_do_not_read_git_objects(self, git):
        scanner = guard.Scanner()
        scanner.pre_push(["", "  ", f"(delete) {ZERO} refs/heads/main {REMOTE}"])
        git.assert_not_called()
        self.assertFalse(scanner.issues)

    @patch.object(guard, "git")
    def test_push_scans_tip_and_every_new_commit_relative_to_known_remote(self, git):
        git.side_effect = [REMOTE.encode(), f"{OID}\n{'c' * 40}\n".encode()]
        scanner = guard.Scanner()
        with patch.object(scanner, "commit") as commit:
            scanner.pre_push([f"refs/heads/main {OID} refs/heads/main {REMOTE}"])
        self.assertEqual(commit.call_args_list, [call(OID), call(OID), call("c" * 40)])
        self.assertEqual(git.call_args_list[-1], call("rev-list", OID, "^" + REMOTE))

    @patch.object(guard, "git")
    def test_unknown_remote_scans_history_against_available_remote_refs(self, git):
        git.side_effect = [guard.SafetyError("missing object"), (OID + "\n").encode()]
        scanner = guard.Scanner()
        with patch.object(scanner, "commit") as commit:
            scanner.pre_push([f"refs/heads/main {OID} refs/heads/main {REMOTE}"])
        self.assertEqual(commit.call_args_list, [call(OID), call(OID)])
        self.assertEqual(git.call_args_list[-1], call("rev-list", OID, "--not", "--remotes"))

    @patch.object(guard, "git", return_value=b"")
    def test_new_branch_and_sha256_object_ids_are_supported(self, git):
        scanner = guard.Scanner()
        new_oid = "a" * 64
        with patch.object(scanner, "commit") as commit:
            scanner.pre_push([f"refs/heads/new {new_oid} refs/heads/new {'0' * 64}"])
        commit.assert_called_once_with(new_oid)
        git.assert_called_once_with("rev-list", new_oid, "--not", "--remotes")


class GitSafetyCLITests(TestCase):
    def run_main(self, arguments, stdin=""):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), patch.object(guard.sys, "stdin", StringIO(stdin)):
            status = guard.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    @patch.object(guard.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b""))
    def test_script_entry_point_exits_successfully_for_an_empty_safe_index(self, run):
        output = StringIO()
        with patch.object(guard.sys, "argv", [guard.__file__, "--index"]), redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(guard.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue(), "Git safety: passed.\n")
        self.assertEqual(run.call_count, 2)

    @patch.object(guard, "Scanner")
    def test_cli_dispatches_each_mode_and_reports_success(self, scanner_class):
        scanner = scanner_class.return_value
        scanner.issues = set()
        for argument, method, expected in (
            ("--index", "index", ()), ("--head", "commit", ("HEAD",)),
            ("--pre-push", "pre_push", (["ref update"],)),
        ):
            with self.subTest(argument=argument):
                scanner.reset_mock()
                status, stdout, stderr = self.run_main([argument], "ref update\n")
                self.assertEqual(status, 0)
                self.assertEqual(stdout, "Git safety: passed.\n")
                self.assertEqual(stderr, "")
                getattr(scanner, method).assert_called_once_with(*expected)

    @patch.object(guard, "Scanner")
    def test_git_and_malformed_data_errors_fail_closed_with_safe_messages(self, scanner_class):
        scanner = scanner_class.return_value
        for error in (guard.SafetyError("safe diagnostic"), ValueError("private data"), UnicodeError("private data")):
            with self.subTest(error=error.__class__):
                scanner.index.side_effect = error
                status, stdout, stderr = self.run_main(["--index"])
                self.assertEqual(status, 2)
                self.assertEqual(stdout, "")
                self.assertIn("Git safety BLOCKED:", stderr)
                self.assertNotIn("private data", stderr)

    @patch.object(guard, "Scanner")
    def test_unsafe_paths_are_json_escaped_and_issue_output_is_bounded(self, scanner_class):
        scanner = scanner_class.return_value
        scanner.issues = {(f"file-{index:03d}.py", "unsafe") for index in range(101)}
        scanner.issues.add(("\nmalicious\tpath", "unsafe"))
        status, stdout, stderr = self.run_main(["--head"])
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn('"\\nmalicious\\tpath": unsafe', stderr)
        self.assertIn("2 additional issues", stderr)
        self.assertEqual(stderr.count(": unsafe"), 100)

    @patch.object(guard, "Scanner")
    def test_single_issue_has_no_truncation_notice(self, scanner_class):
        scanner_class.return_value.issues = {(".env", "environment file")}
        status, stdout, stderr = self.run_main(["--index"])
        self.assertEqual(status, 1)
        self.assertIn('".env": environment file', stderr)
        self.assertNotIn("additional issues", stderr)
