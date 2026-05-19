import json
import tempfile
import unittest
from pathlib import Path

from tools import workspace_hygiene


class WorkspaceHygieneTests(unittest.TestCase):
    def test_classifies_generated_case_artifacts_without_touching_source_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = [
                root / "WAren6_20260510010308",
                root / "__pycache__",
            ]
            for folder in generated:
                folder.mkdir()
            for name in (
                "WAren6_20260510010308.zip",
                "WAren6_20260510010308.sha256.txt",
                "WAren6_20260510010308.tar.zst.sha256.txt",
                "WAren6_20260510010308.tar.zst.md5.txt",
                "WAren6_20260510010308.manifest.json",
                "WAren6_20260510010308.logs.txt",
            ):
                (root / name).write_text("x", encoding="utf-8")
            (root / "runtime").mkdir()
            (root / "waren6.py").write_text("source", encoding="utf-8")
            (root / "README.md").write_text("source", encoding="utf-8")

            plan = workspace_hygiene.build_move_plan(root)
            planned_names = {item.source.name for item in plan}

        self.assertIn("WAren6_20260510010308", planned_names)
        self.assertIn("__pycache__", planned_names)
        self.assertIn("WAren6_20260510010308.zip", planned_names)
        self.assertIn("WAren6_20260510010308.sha256.txt", planned_names)
        self.assertIn("WAren6_20260510010308.tar.zst.sha256.txt", planned_names)
        self.assertIn("WAren6_20260510010308.tar.zst.md5.txt", planned_names)
        self.assertIn("WAren6_20260510010308.manifest.json", planned_names)
        self.assertIn("WAren6_20260510010308.logs.txt", planned_names)
        self.assertIn("runtime", planned_names)
        self.assertNotIn("waren6.py", planned_names)
        self.assertNotIn("README.md", planned_names)

    def test_dry_run_outputs_json_plan_and_does_not_move_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_dir = root / "WAren6_20260510010308"
            case_dir.mkdir()

            result = workspace_hygiene.run_cli([
                "--root",
                str(root),
                "--json",
            ])
            payload = json.loads(result)

            self.assertTrue(case_dir.exists())
            self.assertEqual(payload["apply"], False)
            self.assertEqual(payload["planned_count"], 1)
            self.assertEqual(payload["items"][0]["kind"], "case-directory")

    def test_apply_uses_unique_destination_when_previous_cleanup_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "__pycache__"
            cache_dir.mkdir()
            existing = root / "artifacts" / "local" / "caches" / "__pycache__"
            existing.mkdir(parents=True)

            plan = workspace_hygiene.build_move_plan(root)
            moved = workspace_hygiene.apply_move_plan(plan, apply=True)

            self.assertFalse(cache_dir.exists())
            self.assertTrue((root / "artifacts" / "local" / "caches" / "__pycache__-1").exists())
            self.assertEqual(moved[0].destination.name, "__pycache__-1")

    def test_apply_json_reports_actual_unique_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "__pycache__").mkdir()
            (root / "artifacts" / "local" / "caches" / "__pycache__").mkdir(parents=True)

            result = workspace_hygiene.run_cli([
                "--root",
                str(root),
                "--apply",
                "--json",
            ])
            payload = json.loads(result)

            self.assertEqual(payload["items"][0]["destination"], "artifacts/local/caches/__pycache__-1")

    def test_classifies_local_mockups_and_backups_as_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contacts_stitch.html").write_text("mockup", encoding="utf-8")
            (root / "calls_stitch.html").write_text("mockup", encoding="utf-8")
            (root / "styles.css.bak-minimalist").write_text("backup", encoding="utf-8")
            (root / "README.md").write_text("source", encoding="utf-8")

            plan = workspace_hygiene.build_move_plan(root)
            planned = {item.source.name: item for item in plan}

        self.assertEqual(planned["contacts_stitch.html"].kind, "local-mockup")
        self.assertEqual(planned["calls_stitch.html"].kind, "local-mockup")
        self.assertEqual(planned["styles.css.bak-minimalist"].kind, "backup-file")
        self.assertNotIn("README.md", planned)

    def test_classifies_local_evidence_extracts_as_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("LocalState", "sessions", "EBWebView_Default"):
                (root / name).mkdir()
            for name in (
                "genericStorage.dec.db",
                "genericStorage.dec.db-wal",
                "runtime_capture.jsonl",
            ):
                (root / name).write_text("evidence", encoding="utf-8")
            (root / "README.md").write_text("source", encoding="utf-8")

            plan = workspace_hygiene.build_move_plan(root)
            planned = {item.source.name: item for item in plan}

        self.assertEqual(planned["LocalState"].kind, "evidence-directory")
        self.assertEqual(planned["sessions"].kind, "evidence-directory")
        self.assertEqual(planned["EBWebView_Default"].kind, "evidence-directory")
        self.assertEqual(planned["genericStorage.dec.db"].kind, "evidence-file")
        self.assertEqual(planned["genericStorage.dec.db-wal"].kind, "evidence-file")
        self.assertEqual(planned["runtime_capture.jsonl"].kind, "runtime-jsonl")
        self.assertNotIn("README.md", planned)


if __name__ == "__main__":
    unittest.main()
