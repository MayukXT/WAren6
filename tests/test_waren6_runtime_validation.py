import sqlite3
import tempfile
import unittest
from pathlib import Path

import waren6


class RuntimeSupplementValidationTests(unittest.TestCase):
    def test_missing_enabled_runtime_jsonl_marks_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(waren6.UNIFIED_SCHEMA)
            conn.commit()
            conn.close()

            report = waren6.validate_unified_database(
                db_path,
                runtime_store8_supplement={
                    "summary": {
                        "enabled": True,
                        "path": str(Path(tmp) / "missing-runtime.jsonl"),
                        "usable_records": 0,
                        "warnings": [
                            {
                                "message": "Runtime Store 8 supplement file not found",
                                "path": str(Path(tmp) / "missing-runtime.jsonl"),
                            }
                        ],
                    },
                    "records_by_msg_key": {},
                },
            )

        self.assertEqual(report["metrics"]["runtime_store8_supplement_missing_file"], 1)
        self.assertIn("runtime_store8_supplement_missing_file", report["errors"])
        self.assertEqual(report["status"], "error")

    def test_runtime_summary_missing_file_false_does_not_mark_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(waren6.UNIFIED_SCHEMA)
            conn.commit()
            conn.close()

            report = waren6.validate_unified_database(
                db_path,
                runtime_store8_supplement={
                    "summary": {
                        "enabled": True,
                        "path": str(Path(tmp) / "cleaned-runtime.jsonl"),
                        "missing_file": False,
                        "usable_records": 1,
                        "warnings": [],
                    },
                    "records_by_msg_key": {},
                },
            )

        self.assertEqual(report["metrics"]["runtime_store8_supplement_missing_file"], 0)
        self.assertNotIn("runtime_store8_supplement_missing_file", report["errors"])


if __name__ == "__main__":
    unittest.main()
