"""Integration checks using temporary repositories, never the project's .git."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


GUARD = Path(__file__).with_name("check_git_safety.py").resolve()
ZERO = "0" * 40


class GitSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="repair-git-safety-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Safety Test")
        self.git("config", "user.email", "safety-test@example.invalid")
        self.write("README.md", "Safe initial content.\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "initial")
        self.initial = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True)

    def write(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def guard(self, mode="--index", input=None):
        return subprocess.run([sys.executable, str(GUARD), mode], cwd=self.root,
                              input=input, text=True, capture_output=True)

    def test_working_environment_is_not_inspected(self):
        self.write(".env", "DO_NOT_READ=private-local-value\n")
        self.assertEqual(self.guard().returncode, 0)

    def test_environment_file_is_blocked_even_without_known_secret(self):
        self.write(".env.production", "LOCAL=arbitrary\n")
        self.git("add", ".env.production")
        result = self.guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".env.production", result.stderr)
        self.assertNotIn("arbitrary", result.stderr)

    def test_database_worktree_and_certificate_paths_are_blocked(self):
        for name in ("backup.sqlite3", "repair-shared-navbar/a.py", "private.p12", ".test-artifacts/report.txt"):
            self.write(name, "safe content")
            self.git("add", name)
        result = self.guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("embedded", self.gitlink_result())

    def gitlink_result(self):
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.initial + ",nested-repository")
        return self.guard().stderr

    def test_blank_environment_example_is_allowed(self):
        self.write(".env.example", "GOOGLE_CLIENT_SECRET=\nBOGORTECH_API_KEY=\n")
        self.git("add", ".env.example")
        self.assertEqual(self.guard().returncode, 0)

    def test_environment_example_rejects_nonplaceholder_secret(self):
        self.write(".env.example", "BOGORTECH_API_KEY=arbitrary-private-value\n")
        self.git("add", ".env.example")
        result = self.guard()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("arbitrary-private-value", result.stderr)

    def test_credential_is_scanned_from_staged_blob_only(self):
        fake = "GOC" + "SPX-" + "synthetic-value-for-safety-test"
        self.write("config.py", 'SECRET = "' + fake + '"\n')
        self.git("add", "config.py")
        self.write("config.py", "# working copy was cleaned, index still unsafe\n")
        result = self.guard()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(fake, result.stderr)

    def test_deleted_environment_commit_is_blocked_during_push(self):
        self.write(".env", "SENSITIVE=removed-later\n")
        self.git("add", ".env")
        self.git("commit", "-qm", "unsafe intermediate")
        self.git("rm", "-q", ".env")
        self.git("commit", "-qm", "remove unsafe file")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.guard("--head").returncode, 0)
        result = self.guard("--pre-push", f"refs/heads/test {tip} refs/heads/test {self.initial}\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn(".env", result.stderr)

    def test_new_branch_push_checks_history_without_remote_old_oid(self):
        self.write("README.md", "Safe update\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "safe update")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.guard("--pre-push", f"refs/heads/test {tip} refs/heads/test {ZERO}\n")
        self.assertEqual(result.returncode, 0)

    def test_invalid_hook_input_fails_closed(self):
        self.assertEqual(self.guard("--pre-push", "not valid\n").returncode, 2)

    def test_deleting_remote_branch_sends_no_content(self):
        result = self.guard("--pre-push", f"(delete) {ZERO} refs/heads/test {self.initial}\n")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
