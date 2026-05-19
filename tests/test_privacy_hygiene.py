import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise unittest.SkipTest("git ls-files is required for privacy hygiene checks")
    return [ROOT / line for line in output.splitlines() if line.strip() and (ROOT / line).exists()]


class PrivacyHygieneTests(unittest.TestCase):
    def test_tracked_paths_do_not_include_evidence_or_local_extracts(self):
        forbidden_path_parts = (
            "LocalState",
            "EBWebView",
            "sessions/",
            "sessions\\",
        )
        forbidden_suffixes = (
            ".db",
            ".db-shm",
            ".db-wal",
            ".sqlite",
            ".sqlite-shm",
            ".sqlite-wal",
            ".sqlite3",
            ".sqlite3-shm",
            ".sqlite3-wal",
            ".jsonl",
        )

        offenders = []
        for path in tracked_files():
            relative = path.relative_to(ROOT).as_posix()
            if any(part in relative for part in forbidden_path_parts):
                offenders.append(relative)
            elif relative.lower().endswith(forbidden_suffixes):
                offenders.append(relative)

        self.assertEqual(offenders, [])

    def test_tracked_text_does_not_contain_local_paths_or_removed_fixtures(self):
        forbidden = (
            "C:" + "\\Users\\",
            "C:" + "/Users/",
            "C:" + "\\Work" + " and Code\\",
            "Downloads" + "\\WhatsApp Desktop" + " Forensics Research.md",
            "Pri" + "yanshu",
            "Sa" + "yon",
            "At" + "if",
            "ER" + "HSS",
            "917" + "044051489",
            "700" + "1933075",
            "919" + "876543210",
            "919" + "337042874",
            "917" + "908692319",
            "918" + "708230358",
            "918" + "768831211",
            "919" + "800323983",
            "918" + "765432100",
            "947" + "5434710",
            "923" + "9359693",
            "861" + "7397473",
            "704" + "7914456",
            "990" + "7106482",
            "Chi" + "tra Sinha",
            "Na" + "itik",
            "Ru" + "pam",
            "An" + "irban",
        )

        offenders = []
        for path in tracked_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative == "tests/test_privacy_hygiene.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{relative}: {needle}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
