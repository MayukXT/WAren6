import sqlite3
import tempfile
import unittest
from pathlib import Path

import waren6


class ForensicReportTests(unittest.TestCase):
    def build_db(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(waren6.UNIFIED_SCHEMA)
        conn.execute(
            "INSERT INTO extraction_metadata(key, value) VALUES ('self_phone', '15550101234')"
        )
        conn.execute(
            "INSERT INTO chats(chat_jid, chat_name, is_group) VALUES ('15550107654@c.us', 'Test Chat', 0)"
        )
        conn.execute(
            """
            INSERT INTO messages(
                msg_key, msg_id, chat_jid, chat_name, sender_name, from_me,
                timestamp, text, msg_type, source, source_id, source_recovery
            )
            VALUES ('true_15550107654@c.us_ABC', 'ABC', '15550107654@c.us',
                    'Test Chat', 'Examiner', 1, 1714569600, 'hello',
                    'chat', 'indexeddb', 'ABC', 'store8')
            """
        )
        conn.commit()
        conn.close()

    def test_exports_all_requested_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "unified_whatsapp.db"
            out_dir = tmp_path / "reports"
            self.build_db(db_path)

            outputs = waren6.export_forensic_reports(
                db_path=db_path,
                output_dir=out_dir,
                formats=["html", "jsonl", "csv", "tsv", "pdf"],
                timezone_name="UTC",
                tool_version="test",
                scope="full",
            )

            self.assertEqual(set(outputs), {"html", "jsonl", "csv", "tsv", "pdf"})
            self.assertTrue((out_dir / "full_case.html").read_text(encoding="utf-8").startswith("<!doctype html>"))
            self.assertIn('"text": "hello"', (out_dir / "full_case.jsonl").read_text(encoding="utf-8"))
            self.assertIn("chat_jid,msg_id", (out_dir / "full_case.csv").read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("chat_jid\tmsg_id", (out_dir / "full_case.tsv").read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue((out_dir / "full_case.pdf").read_bytes().startswith(b"%PDF-"))
            self.assertTrue((out_dir / "report_manifest.json").exists())
            manifest = waren6.write_report_manifest(
                out_dir / "report_manifest.aggregate.json",
                db_path,
                "UTC",
                outputs,
            )
            self.assertEqual(len(manifest["files"]), 5)
            self.assertTrue(all(entry["sha256"] for entry in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
