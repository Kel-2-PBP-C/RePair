#!/usr/bin/env python3
"""Block sensitive files and recognizable credentials before commits and pushes.

Only Git objects are inspected; working-copy environment files are never read.
Run with --index, --head, or --pre-push (Git's ref updates on standard input).
"""

from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
import re
import subprocess
import sys


class SafetyError(Exception):
    pass


BLOCKED_DIRECTORIES = {
    ".git", ".venv", "venv", "env", ".test-artifacts", ".uv-cache",
    "staticfiles", "__pycache__",
}
BLOCKED_EXTENSIONS = {".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx"}
CREDENTIAL_PATTERNS = (
    ("Google OAuth client secret", re.compile(rb"GOCSPX-[A-Za-z0-9_-]{12,}")),
    ("BogorTech API key", re.compile(rb"SLK-ENT-[0-9]{8,}")),
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("Google access token", re.compile(rb"ya29\.[A-Za-z0-9_-]{30,}")),
    ("AWS access key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("URL containing credentials", re.compile(rb"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|https?)://[^\s/:<>\"']+:[^\s/@<>\"']+@", re.I)),
)


def git(*arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise SafetyError("Git is unavailable; the safety check could not run.") from exc
    if result.returncode:
        # Git diagnostics can include repository URLs. Do not echo them.
        raise SafetyError("Git objects could not be inspected. Resolve Git errors or fetch the destination branch, then retry.")
    return result.stdout


def decode_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def path_problem(path: str, mode: str) -> str | None:
    parts = PurePosixPath(path).parts
    lowered = [part.lower() for part in parts]
    if mode == "160000":
        return "embedded repository / Git submodule"
    if not parts:
        return "invalid Git path"
    if any(part.startswith(".env") for part in lowered) and path != ".env.example":
        return "environment file (only root .env.example is allowed)"
    if any(part in BLOCKED_DIRECTORIES for part in lowered):
        return "local environment or generated artifacts"
    if any(part.startswith("repair-") for part in lowered[:-1]):
        return "nested repair-* worktree"
    if PurePosixPath(path).suffix.lower() in BLOCKED_EXTENSIONS:
        return "database, private key, or certificate bundle"
    return None


def credential_problems(data: bytes, path: str) -> list[str]:
    if b"\0" in data:
        return []  # Binary images/fonts are not text credentials.
    problems = [label for label, pattern in CREDENTIAL_PATTERNS if pattern.search(data)]
    if path == ".env.example":
        for raw in data.decode("utf-8", errors="replace").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            name, value = raw.split("=", 1)
            name = name.strip().upper()
            value = value.strip().strip("\"'")
            if not re.search(r"(?:SECRET|TOKEN|PASSWORD|(?:^|_)KEY)(?:$|_)", name):
                continue
            placeholder = (
                not value or value.lower() in {"changeme", "change-me", "example", "placeholder"}
                or value.lower().startswith(("your-", "your_", "replace-", "replace_", "<"))
            )
            if not placeholder:
                problems.append("nonempty credential in .env.example; leave it blank or use a placeholder")
                break
    return problems


class Scanner:
    def __init__(self) -> None:
        self.issues: set[tuple[str, str]] = set()
        self.blobs: dict[str, bytes] = {}
        self.checked_trees: set[str] = set()

    def check_entries(self, entries: list[tuple[str, str, str]], contents: set[str] | None = None) -> None:
        for mode, oid, path in entries:
            problem = path_problem(path, mode)
            if problem:
                self.issues.add((path, problem))
                continue
            if contents is not None and path not in contents:
                continue
            if oid not in self.blobs:
                self.blobs[oid] = git("cat-file", "blob", oid)
            for problem in credential_problems(self.blobs[oid], path):
                self.issues.add((path, problem))

    def index(self) -> None:
        entries = []
        for raw in git("ls-files", "--stage", "-z").split(b"\0"):
            if not raw:
                continue
            metadata, path_bytes = raw.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = decode_path(path_bytes)
            if stage != "0":
                self.issues.add((path, "unresolved merge conflict"))
                continue
            entries.append((mode, oid, path))
        changed = {
            decode_path(path) for path in git(
                "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z",
            ).split(b"\0") if path
        }
        self.check_entries(entries, changed)

    def commit(self, revision: str) -> None:
        oid = git("rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
        if oid in self.checked_trees:
            return
        self.checked_trees.add(oid)
        entries = []
        for raw in git("ls-tree", "-r", "-z", oid).split(b"\0"):
            if not raw:
                continue
            metadata, path = raw.split(b"\t", 1)
            mode, _kind, blob_oid = metadata.decode("ascii").split()
            entries.append((mode, blob_oid, decode_path(path)))
        self.check_entries(entries)

    def pre_push(self, lines: list[str]) -> None:
        for line in lines:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) != 4:
                raise SafetyError("Invalid pre-push reference input; refusing an unchecked push.")
            _local_ref, local_oid, _remote_ref, remote_oid = fields
            for oid in (local_oid, remote_oid):
                if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", oid):
                    raise SafetyError("Invalid Git object ID; refusing an unchecked push.")
            if set(local_oid) == {"0"}:
                continue  # Deleting a remote branch sends no new content.
            self.commit(local_oid)
            if set(remote_oid) != {"0"}:
                try:
                    remote_commit = git("rev-parse", "--verify", remote_oid + "^{commit}").decode("ascii").strip()
                except SafetyError:
                    remote_commit = None
            else:
                remote_commit = None
            if remote_commit:
                introduced = git("rev-list", local_oid, "^" + remote_commit)
            else:
                introduced = git("rev-list", local_oid, "--not", "--remotes")
            for oid in introduced.decode("ascii").splitlines():
                # Scan intermediate commits too: committing then deleting .env
                # must never bypass the guard.
                self.commit(oid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--index", action="store_true", help="check index paths and changed staged text")
    modes.add_argument("--head", action="store_true", help="check all HEAD paths and text")
    modes.add_argument("--pre-push", action="store_true", help="check pushed tips and newly introduced commits")
    args = parser.parse_args(argv)
    scanner = Scanner()
    try:
        if args.index:
            scanner.index()
        elif args.head:
            scanner.commit("HEAD")
        else:
            scanner.pre_push(sys.stdin.read().splitlines())
    except (SafetyError, ValueError, UnicodeError) as exc:
        message = str(exc) if isinstance(exc, SafetyError) else "Malformed Git data; the safety check could not complete."
        print("Git safety BLOCKED: " + message, file=sys.stderr)
        return 2
    if scanner.issues:
        print("Git safety BLOCKED. No credential values are printed:", file=sys.stderr)
        for path, reason in sorted(scanner.issues)[:100]:
            print("  " + json.dumps(path, ensure_ascii=True) + ": " + reason, file=sys.stderr)
        if len(scanner.issues) > 100:
            print(f"  ... {len(scanner.issues) - 100} additional issues.", file=sys.stderr)
        print("Remove sensitive files/credentials from the staged changes or unpublished commits, then retry.", file=sys.stderr)
        return 1
    print("Git safety: passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
