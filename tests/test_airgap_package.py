import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from airgap import build_airgap_package


class AirgapPackageTests(unittest.TestCase):
    def test_manifest_redacts_generated_outputs_and_includes_core_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "airgap").mkdir()
            (root / "waren6-reader" / "src").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "LocalState").mkdir()
            (root / "sessions").mkdir()
            (root / "EBWebView_Default").mkdir()
            for name in (
                "waren6.ps1",
                "waren6.py",
                "waren6_unify_case.py",
                "requirements-lock.txt",
                "BouncyCastle.Cryptography.dll",
                "README.md",
                "LLM.txt",
                "fieldkit-version.json",
                ".editorconfig",
            ):
                (root / name).write_text(name, encoding="utf-8")
            (root / "BREAKTHROUGHS.md").write_text("internal", encoding="utf-8")
            (root / "RESEARCH.md").write_text("internal", encoding="utf-8")
            (root / "FORME.md").write_text("internal", encoding="utf-8")
            (root / "airgap" / "README.md").write_text("airgap", encoding="utf-8")
            (root / "waren6-reader" / "src" / "main.js").write_text("reader", encoding="utf-8")
            (root / "tests" / "test_release.py").write_text("test", encoding="utf-8")
            (root / ".github" / "workflows" / "reader-release.yml").write_text("workflow", encoding="utf-8")
            (root / "WAren6_20260510010308.zip").write_text("generated", encoding="utf-8")
            (root / "WAren6_20260510010308").mkdir()
            (root / "contacts_stitch.html").write_text("mockup", encoding="utf-8")
            (root / "genericStorage.dec.db").write_text("db", encoding="utf-8")
            (root / "genericStorage.dec.db-wal").write_text("wal", encoding="utf-8")
            (root / "runtime_capture.jsonl").write_text("jsonl", encoding="utf-8")

            plan = build_airgap_package.build_file_plan(root)
            relative_paths = {item.relative_path for item in plan}

            self.assertIn("waren6.ps1", relative_paths)
            self.assertIn("waren6.py", relative_paths)
            self.assertIn("waren6_unify_case.py", relative_paths)
            self.assertIn("LLM.txt", relative_paths)
            self.assertIn("fieldkit-version.json", relative_paths)
            self.assertIn("airgap/README.md", relative_paths)
            self.assertNotIn("BREAKTHROUGHS.md", relative_paths)
            self.assertNotIn("RESEARCH.md", relative_paths)
            self.assertNotIn("FORME.md", relative_paths)
            self.assertNotIn("waren6-reader/src/main.js", relative_paths)
            self.assertNotIn("tests/test_release.py", relative_paths)
            self.assertNotIn(".github/workflows/reader-release.yml", relative_paths)
            self.assertNotIn("contacts_stitch.html", relative_paths)
            self.assertNotIn("WAren6_20260510010308.zip", relative_paths)
            self.assertNotIn("WAren6_20260510010308", relative_paths)
            self.assertNotIn("LocalState", relative_paths)
            self.assertNotIn("sessions", relative_paths)
            self.assertNotIn("EBWebView_Default", relative_paths)
            self.assertNotIn("genericStorage.dec.db", relative_paths)
            self.assertNotIn("genericStorage.dec.db-wal", relative_paths)
            self.assertNotIn("runtime_capture.jsonl", relative_paths)

    def test_package_zip_contains_fieldkit_manifest_and_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "dist"
            (root / "airgap").mkdir()
            for name in (
                "waren6.ps1",
                "waren6.py",
                "waren6_unify_case.py",
                "requirements-lock.txt",
                "BouncyCastle.Cryptography.dll",
                "README.md",
                "LLM.txt",
                "fieldkit-version.json",
            ):
                (root / name).write_text(name, encoding="utf-8")
            (root / "airgap" / "README.md").write_text("airgap", encoding="utf-8")

            package = build_airgap_package.build_package(root, output, package_name="WAren6-FieldKit-v1.1.0")

            self.assertTrue(package.archive_path.exists())
            self.assertTrue(package.sha256_path.exists())
            with zipfile.ZipFile(package.archive_path) as archive:
                names = set(archive.namelist())
                self.assertIn("WAren6-FieldKit/WAren6.fieldkit.manifest.json", names)
                self.assertIn("WAren6-FieldKit/waren6.ps1", names)
                self.assertIn("WAren6-FieldKit/README_FIELDKIT.md", names)
                self.assertIn("WAren6-FieldKit/fieldkit-version.json", names)
                manifest = json.loads(archive.read("WAren6-FieldKit/WAren6.fieldkit.manifest.json"))
            self.assertEqual(manifest["schema"], "waren6.fieldkit.manifest.v1")
            self.assertEqual(manifest["package_root"], "WAren6-FieldKit")
            self.assertFalse(manifest["include_reader"])
            self.assertGreaterEqual(manifest["file_count"], 5)


if __name__ == "__main__":
    unittest.main()
