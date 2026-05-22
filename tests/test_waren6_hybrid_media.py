import contextlib
import io
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import waren6


class UnifiedSchemaPerformanceTests(unittest.TestCase):
    def test_schema_indexes_quote_lookup_by_chat_and_message_id(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(waren6.UNIFIED_SCHEMA)
            indexes = {
                row[1]
                for row in conn.execute("PRAGMA index_list(messages)").fetchall()
            }
            self.assertIn("idx_messages_chat_msgid_ts", indexes)

            conn.execute(
                """
                INSERT INTO messages(
                    msg_key, msg_id, chat_jid, timestamp, text,
                    source, source_id, body_status
                )
                VALUES ('false_0@c.us_ORIGINAL', 'ORIGINAL', '0@c.us', 1770000000,
                        'quoted text', 'indexeddb', 'ORIGINAL', 'text_present')
                """
            )
            plan = "\n".join(
                str(row)
                for row in conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT o.text
                    FROM messages AS o
                    WHERE o.chat_jid = ?
                      AND o.msg_id = ?
                      AND o.text IS NOT NULL
                      AND TRIM(o.text) != ''
                    ORDER BY o.timestamp ASC, o.rowid ASC
                    LIMIT 1
                    """,
                    ("0@c.us", "ORIGINAL"),
                ).fetchall()
            )

            self.assertIn("idx_messages_chat_msgid_ts", plan)
        finally:
            conn.close()

    def test_schema_indexes_runtime_validation_by_message_key(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(waren6.UNIFIED_SCHEMA)
            indexes = {
                row[1]
                for row in conn.execute("PRAGMA index_list(messages)").fetchall()
            }
            self.assertIn("idx_messages_msg_key", indexes)

            plan = "\n".join(
                str(row)
                for row in conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT text, store8_decrypted_text
                    FROM messages
                    WHERE msg_key = ?
                    LIMIT 1
                    """,
                    ("false_0@c.us_STANZA",),
                ).fetchall()
            )

            self.assertIn("idx_messages_msg_key", plan)
        finally:
            conn.close()

    def test_schema_indexes_chat_timestamp_pagination(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(waren6.UNIFIED_SCHEMA)
            indexes = {
                row[1]
                for row in conn.execute("PRAGMA index_list(messages)").fetchall()
            }
            self.assertIn("idx_messages_chat_ts", indexes)

            plan = "\n".join(
                str(row)
                for row in conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT rowid
                    FROM messages
                    WHERE chat_jid = ?
                      AND (timestamp < ? OR (timestamp = ? AND rowid < ?))
                    ORDER BY timestamp DESC, rowid DESC
                    LIMIT 50
                    """,
                    ("12345@c.us", 1770000000, 1770000000, 99),
                ).fetchall()
            )

            self.assertIn("idx_messages_chat_ts", plan)
        finally:
            conn.close()

    def test_unified_builder_defers_indexes_until_after_message_bulk_load(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        build_start = source.index("def build_unified_db")
        build_end = source.index("def iter_local_media_files", build_start)
        build_source = source[build_start:build_end]

        self.assertIn("UNIFIED_TABLE_SCHEMA", source)
        self.assertIn("UNIFIED_INDEX_SCHEMA", source)
        self.assertIn("def create_unified_indexes", source)
        self.assertIn("cursor.executescript(UNIFIED_TABLE_SCHEMA)", build_source)
        self.assertIn("create_unified_indexes(conn)", build_source)
        self.assertNotIn("cursor.executescript(UNIFIED_SCHEMA)", build_source)
        self.assertLess(
            build_source.index("cursor.executescript(UNIFIED_TABLE_SCHEMA)"),
            build_source.index("execute_many_counting(cursor, message_insert_sql, idb_batch"),
        )
        self.assertLess(
            build_source.index("execute_many_counting(cursor, message_insert_sql, idb_batch"),
            build_source.index("create_unified_indexes(conn)"),
        )

    def test_unified_builder_uses_bulk_load_pragmas_for_generated_db(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")

        self.assertIn("def configure_unified_output_connection", source)
        self.assertIn("PRAGMA journal_mode=MEMORY", source)
        self.assertIn("PRAGMA synchronous=OFF", source)
        self.assertIn("PRAGMA temp_store=MEMORY", source)
        self.assertIn("PRAGMA mmap_size=268435456", source)
        self.assertIn("configure_unified_output_connection(conn)", source)

    def test_unifier_caches_repeated_jid_and_chat_id_parsing(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        build_start = source.index("def build_unified_db")
        build_end = source.index("def iter_local_media_files", build_start)
        build_source = source[build_start:build_end]

        self.assertIn("import functools", source)
        self.assertIn("@functools.lru_cache(maxsize=16384)", source)
        self.assertIn("def _normalize_chat_id_cached", source)
        self.assertIn("def cached_resolve_jid", build_source)
        raw_resolve_calls = re.findall(r"(?<!cached_)resolve_jid\(", build_source)
        self.assertEqual(len(raw_resolve_calls), 1)
        self.assertIn("cached_resolve_jid(", build_source)

    def test_unifier_batches_receipts_and_reactions(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        receipt_start = source.index("# ── Message receipts")
        reaction_start = source.index("# ── Reactions", receipt_start)
        final_start = source.index("# ── Final stats", reaction_start)
        receipt_source = source[receipt_start:reaction_start]
        reaction_source = source[reaction_start:final_start]

        self.assertIn("receipt_batch", receipt_source)
        self.assertIn("execute_many_counting(cursor", receipt_source)
        self.assertNotIn("cursor.execute(\"\"\"", receipt_source)
        self.assertIn("reaction_batch", reaction_source)
        self.assertIn("execute_many_counting(cursor", reaction_source)
        self.assertNotIn("cursor.execute(\"\"\"", reaction_source)

    def test_unifier_uses_set_based_quote_and_dedup_sql(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        quote_start = source.index("# ── Enrich quoted-message bodies")
        dedup_start = source.index("# ── Deduplicate only stable IndexedDB key duplicates", quote_start)
        summary_start = source.index("# Summary", dedup_start)
        quote_source = source[quote_start:dedup_start]
        dedup_source = source[dedup_start:summary_start]

        self.assertIn("ROW_NUMBER() OVER", quote_source)
        self.assertIn("FROM original_quotes", quote_source)
        self.assertNotIn("SELECT o.text", quote_source)
        self.assertIn("HAVING COUNT(*) > 1", dedup_source)
        self.assertNotIn("rowid NOT IN", dedup_source)

    def test_media_iterator_targets_transfer_and_blob_dirs_directly(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        iterator_start = source.index("def iter_local_media_files")
        iterator_end = source.index("def _case_relative", iterator_start)
        iterator_source = source[iterator_start:iterator_end]

        self.assertIn('sessions_root.glob("*/transfers")', iterator_source)
        self.assertIn('indexeddb_root.glob("*.indexeddb.blob")', iterator_source)
        self.assertNotIn('case_root / "sessions",', iterator_source)

    def test_wal_open_uses_caller_specific_sanity_tables(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")

        self.assertIn("def _apply_wal_and_open(db_path: pathlib.Path, sanity_table: str | None = None)", source)
        self.assertIn('_apply_wal_and_open(db_path, sanity_table="message")', source)
        self.assertIn('_apply_wal_and_open(db_path, sanity_table="UserStatuses")', source)
        self.assertNotIn('Native WAL read failed', source)


class BodyStatusTests(unittest.TestCase):
    def test_python_console_output_is_ascii_safe_for_powershell_capture(self):
        source = Path(waren6.__file__).read_text(encoding="utf-8")
        print_lines = [
            line for line in source.splitlines()
            if "print(" in line or "def print_progress" in line
        ]
        joined = "\n".join(print_lines)

        for bad in ("✓", "┌", "└", "│", "├", "»", "→", "█"):
            self.assertNotIn(bad, joined)
        self.assertIn("PROGRESS_ENABLED = not args.no_progress", source)
        self.assertIn("not sys.stdout.isatty()", source)
        self.assertIn('print("  Self phone: [redacted]")', source)
        self.assertNotIn('print(f"  Self phone: {self_phone}")', source)

    def test_lid_resolver_prints_one_compact_summary(self):
        contacts = [
            {"id": f"{idx}@lid", "phoneNumber": f"91000000000{idx}@c.us", "name": f"Example {idx}"}
            for idx in range(5)
        ]
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            lid_to_phone, _, _ = waren6.build_lid_resolver(contacts, [])

        self.assertEqual(len(lid_to_phone), 5)
        lines = [line for line in out.getvalue().splitlines() if line.strip()]
        self.assertEqual(lines, ["  LID mappings: 5 from IndexedDB contacts, 0 SQLite supplemental"])

    def test_default_unified_build_console_is_compact(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(out):
            db_path = Path(tmp) / "unified_whatsapp.db"
            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

        text = out.getvalue()
        self.assertIn("Source messages: 0 Store 8 rows, 0 genericStorage rows", text)
        self.assertNotIn("Inserting 0 messages", text)
        self.assertNotIn("Fallback enrichment", text)
        self.assertNotIn("Personal-chat fromMe fix", text)
        self.assertNotIn("fromMe coverage", text)

    def test_message_identity_uses_first_url_for_link_preview_duplicates(self):
        url = "https://youtube.com/shorts/4OarBibtuOk?si=xN2TX3HjX7hzzyY2"

        self.assertEqual(waren6.message_identity_text(url), url)
        self.assertEqual(
            waren6.message_identity_text(f"youtube.com {url} {url}"),
            url,
        )

    def test_classifies_expected_blank_rows_without_false_loss(self):
        self.assertEqual(
            waren6.classify_body_status(msg_type="image", media_filename="photo.jpg"),
            "media_only",
        )
        self.assertEqual(
            waren6.classify_body_status(msg_type="call_log"),
            "call_event",
        )
        self.assertEqual(
            waren6.classify_body_status(source_recovery="store8_opaque_unresolved", store8_status="opaque_unresolved"),
            "opaque_unresolved",
        )
        self.assertEqual(
            waren6.classify_body_status(msg_type="chat"),
            "missing_unexpected",
        )
        self.assertEqual(
            waren6.classify_body_status(msg_type="e2e_notification"),
            "system_event",
        )
        self.assertEqual(
            waren6.classify_body_status(msg_type="gp2"),
            "system_event",
        )

    def test_runtime_text_validation_checks_imported_live_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(waren6.UNIFIED_SCHEMA)
            conn.execute(
                """
                INSERT INTO messages(msg_key, chat_jid, timestamp, text, source, source_id, body_status)
                VALUES ('true_0@c.us_A', '0@c.us', 1, 'hello live', 'indexeddb', 'A', 'runtime_store8_decoded')
                """
            )
            conn.commit()
            conn.close()

            report = waren6.validate_unified_database(
                db_path,
                runtime_store8_supplement={
                    "records_by_msg_key": {
                        "true_0@c.us_A": {"msg_key": "true_0@c.us_A", "body": "hello live"}
                    }
                },
            )

        self.assertEqual(report["metrics"]["runtime_text_keys_missing_from_unified"], 0)
        self.assertEqual(report["status"], "ok")

    def test_exact_source_text_gaps_are_warnings_and_samples_are_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(waren6.UNIFIED_SCHEMA)
            conn.execute(
                """
                INSERT INTO messages(msg_key, chat_jid, timestamp, text, source, source_id, body_status)
                VALUES ('true_0@c.us_A', '0@c.us', 1, 'trimmed preview', 'indexeddb', 'A', 'text_present')
                """
            )
            conn.commit()
            conn.close()

            report = waren6.validate_unified_database(
                db_path,
                sqlite_messages=[
                    {"chatId": "0@c.us", "timestamp": 1, "text": "full preview text with private content"}
                ],
            )

        self.assertEqual(report["metrics"]["missing_exact_text_keys"], 1)
        self.assertIn("missing_exact_text_keys", report["warnings"])
        self.assertNotIn("missing_exact_text_keys", report["errors"])
        self.assertEqual(report["status"], "ok")
        self.assertIn("text_sha256", report["missing_exact_text_samples"][0])
        self.assertNotIn("text", report["missing_exact_text_samples"][0])

    def test_build_unified_db_inserts_runtime_only_text_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            runtime_key = "true_12345@c.us_ABCDEF"
            runtime = {
                "summary": {"enabled": True, "path": "runtime.jsonl", "usable_records": 1},
                "records_by_msg_key": {
                    runtime_key: {
                        "msg_key": runtime_key,
                        "timestamp": 1770000000,
                        "type": "chat",
                        "from_me": True,
                        "chat_jid": "12345@c.us",
                        "body": "runtime-only text",
                    }
                },
            }

            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
                runtime_store8_supplement=runtime,
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT text, source, source_recovery, body_status, store8_decryption_status
                FROM messages WHERE msg_key = ?
                """,
                (runtime_key,),
            ).fetchone()
            conn.close()

            report = waren6.validate_unified_database(db_path, runtime_store8_supplement=runtime)

        self.assertEqual(row, (
            "runtime-only text",
            "runtime_store8",
            "runtime_store8_only",
            "runtime_store8_decoded",
            "runtime_store8_decoded",
        ))
        self.assertEqual(report["metrics"]["runtime_text_keys_missing_from_unified"], 0)
        self.assertEqual(report["metrics"]["missing_unexpected"], 0)

    def test_runtime_only_rows_consume_matching_generic_storage_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            runtime_key = "true_12345@c.us_ABCDEF"
            runtime = {
                "summary": {"enabled": True, "path": "runtime.jsonl", "usable_records": 1},
                "records_by_msg_key": {
                    runtime_key: {
                        "msg_key": runtime_key,
                        "timestamp": 1770000000,
                        "type": "chat",
                        "from_me": True,
                        "chat_jid": "12345@c.us",
                        "body": "same text from runtime and sqlite",
                    }
                },
            }

            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [
                    {
                        "id": 7,
                        "chatId": "12345@c.us",
                        "timestamp": 1770000000,
                        "text": "same text from runtime and sqlite",
                    }
                ],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
                runtime_store8_supplement=runtime,
            )

            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                """
                SELECT msg_key, source, source_recovery, text
                FROM messages
                WHERE chat_jid = '12345@c.us'
                ORDER BY rowid
                """
            ).fetchall()
            conn.close()

        self.assertEqual(rows, [
            (
                runtime_key,
                "runtime_store8",
                "runtime_store8_only",
                "same text from runtime and sqlite",
            )
        ])

    def test_runtime_only_revoked_rows_are_preserved_without_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            runtime_key = "false_fixturegroup@g.us_DELETE_999@lid"
            runtime = {
                "summary": {"enabled": True, "path": "runtime.jsonl", "usable_records": 1},
                "records_by_msg_key": {
                    runtime_key: {
                        "msg_key": runtime_key,
                        "timestamp": 1770000000,
                        "type": "revoked",
                        "subtype": "sender",
                        "from_me": False,
                        "chat_jid": "fixturegroup@g.us",
                        "sender_jid": "999@lid",
                    }
                },
            }

            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
                runtime_store8_supplement=runtime,
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT text, msg_type, from_me, sender_jid, source, source_recovery, body_status
                FROM messages WHERE msg_key = ?
                """,
                (runtime_key,),
            ).fetchone()
            conn.close()

        self.assertEqual(row, (
            None,
            "revoked",
            0,
            "999@lid",
            "runtime_store8",
            "runtime_store8_only",
            "revoked_or_deleted",
        ))

    def test_runtime_only_quote_context_is_preserved_and_enriched(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            original_key = "false_fixturegroup@g.us_ORIG_111@lid"
            reply_key = "false_fixturegroup@g.us_REPLY_222@lid"
            runtime = {
                "summary": {"enabled": True, "path": "runtime.jsonl", "usable_records": 2},
                "records_by_msg_key": {
                    original_key: {
                        "msg_key": original_key,
                        "timestamp": 1770000000,
                        "type": "chat",
                        "from_me": False,
                        "chat_jid": "fixturegroup@g.us",
                        "sender_jid": "111@lid",
                        "body": "original body",
                    },
                    reply_key: {
                        "msg_key": reply_key,
                        "timestamp": 1770000010,
                        "type": "chat",
                        "from_me": False,
                        "chat_jid": "fixturegroup@g.us",
                        "sender_jid": "222@lid",
                        "body": "reply body",
                        "quoted_stanza_id": "ORIG",
                        "quoted_participant": "111@lid",
                        "quoted_msg_type": "chat",
                    },
                },
            }

            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
                runtime_store8_supplement=runtime,
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT quoted_stanza_id, quoted_participant, quoted_msg_body, quoted_msg_type
                FROM messages WHERE msg_key = ?
                """,
                (reply_key,),
            ).fetchone()
            conn.close()

        self.assertEqual(row, ("ORIG", "111@lid", "original body", "chat"))

    def test_store8_edit_marker_sets_message_edit_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            msg_key = "true_12345@c.us_MSG"

            waren6.build_unified_db(
                str(db_path),
                {
                    "message": [
                        {
                            "id": msg_key,
                            "t": 1770000000,
                            "type": "chat",
                            "body": "edited text",
                            "latestEditMsgKey": "true_12345@c.us_EDIT",
                            "latestEditSenderTimestampMs": 1770000065000,
                        }
                    ],
                },
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT is_edited, edited_at, edit_count, edit_history_status
                FROM messages WHERE msg_key = ?
                """,
                (msg_key,),
            ).fetchone()
            metrics = waren6.validate_unified_database(db_path)["metrics"]
            conn.close()

        self.assertEqual(row, (1, 1770000065, 0, "marker_only"))
        self.assertEqual(metrics["edited_message_markers"], 1)

    def test_message_edit_protocol_is_recorded_and_target_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            target_key = "true_12345@c.us_TARGET"
            edit_key = "true_12345@c.us_EDIT"

            waren6.build_unified_db(
                str(db_path),
                {
                    "message": [
                        {
                            "id": target_key,
                            "t": 1770000000,
                            "type": "chat",
                            "body": "new text",
                            "latestEditMsgKey": edit_key,
                            "latestEditSenderTimestampMs": 1770000100000,
                        },
                        {
                            "id": edit_key,
                            "t": 1770000100,
                            "type": "protocol",
                            "subtype": "message_edit",
                            "body": "new text",
                            "protocolMessageKey": target_key,
                        },
                    ],
                },
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            msg_row = conn.execute(
                """
                SELECT is_edited, edited_at, edit_count, edit_history_status
                FROM messages WHERE msg_key = ?
                """,
                (target_key,),
            ).fetchone()
            edit_row = conn.execute(
                """
                SELECT target_msg_key, edit_event_msg_key, edit_index, edited_at,
                       new_text, source, confidence
                FROM message_edits WHERE target_msg_key = ?
                """,
                (target_key,),
            ).fetchone()
            metrics = waren6.validate_unified_database(db_path)["metrics"]
            conn.close()

        self.assertEqual(msg_row, (1, 1770000100, 1, "event_history"))
        self.assertEqual(edit_row, (
            target_key,
            edit_key,
            1,
            1770000100,
            "new text",
            "store8",
            "high",
        ))
        self.assertEqual(metrics["message_edit_protocol_events"], 1)
        self.assertEqual(metrics["message_edit_protocol_folded"], 1)

    def test_orphan_message_edit_protocol_recovers_single_target_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            target_key = "false_fixturegroup@g.us_TARGET_111@lid"
            edit_key = "false_fixturegroup@g.us_EDIT_111@lid"

            waren6.build_unified_db(
                str(db_path),
                {
                    "message": [
                        {
                            "id": edit_key,
                            "t": 1770000100,
                            "type": "protocol",
                            "subtype": "message_edit",
                            "body": "recovered edited text",
                            "protocolMessageKey": target_key,
                        },
                    ],
                },
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            recovered = conn.execute(
                """
                SELECT msg_key, msg_id, chat_jid, text, source_recovery,
                       is_edited, edit_count, edit_history_status
                FROM messages
                WHERE msg_key = ?
                """,
                (target_key,),
            ).fetchone()
            visible_protocol_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE msg_key = ? AND msg_type = 'protocol'",
                (edit_key,),
            ).fetchone()[0]
            metrics = waren6.validate_unified_database(db_path)["metrics"]
            conn.close()

        self.assertEqual(recovered, (
            target_key,
            "TARGET",
            "fixturegroup@g.us",
            "recovered edited text",
            "store8_message_edit_orphan",
            1,
            1,
            "event_only_orphan",
        ))
        self.assertEqual(visible_protocol_count, 1)
        self.assertEqual(metrics["message_edit_protocol_orphans"], 1)

    def test_reply_to_edited_message_keeps_captured_quote_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            original_key = "true_12345@c.us_ORIG"
            reply_key = "false_12345@c.us_REPLY"

            waren6.build_unified_db(
                str(db_path),
                {
                    "message": [
                        {
                            "id": original_key,
                            "t": 1770000000,
                            "type": "chat",
                            "body": "edited current text",
                            "latestEditMsgKey": "true_12345@c.us_EDIT",
                            "latestEditSenderTimestampMs": 1770000100000,
                        },
                        {
                            "id": reply_key,
                            "t": 1770000200,
                            "type": "chat",
                            "body": "reply",
                            "quotedStanzaID": "ORIG",
                            "quotedMsg": {"body": "captured original quote"},
                        },
                    ],
                },
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT quoted_msg_body FROM messages WHERE msg_key = ?",
                (reply_key,),
            ).fetchone()
            conn.close()

        self.assertEqual(row[0], "captured original quote")

    def test_message_mentions_schema_extracts_store8_mentions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            msg_key = "false_fixturegroup@g.us_MSG_222@lid"

            waren6.build_unified_db(
                str(db_path),
                {
                    "message": [
                        {
                            "id": msg_key,
                            "t": 1770000000,
                            "type": "chat",
                            "body": "@~Example Member Amit @all",
                            "mentionedJidList": ["111@lid", "@all"],
                        }
                    ],
                },
                [],
                {"111@lid": "910000000001@c.us"},
                {"111@lid": "Example Member"},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                """
                SELECT msg_key, mention_index, kind, target_jid, target_phone,
                       target_name, display_text, source, confidence
                FROM message_mentions
                ORDER BY mention_index
                """
            ).fetchall()
            conn.close()

        self.assertEqual(rows, [
            (msg_key, 0, "participant", "111@lid", "910000000001", "Example Member", None, "store8", "high"),
            (msg_key, 1, "all", None, None, None, "@all", "store8", "high"),
        ])

    def test_message_mentions_ignore_null_fields_inside_mention_objects(self):
        record = {
            "body": "hello",
            "mentionedJidList": [
                {
                    "kind": None,
                    "type": None,
                    "displayText": None,
                    "jid": {"user": "910000000003", "server": "s.whatsapp.net"},
                }
            ],
        }

        self.assertEqual(
            waren6.extract_message_mentions(record),
            [
                {
                    "kind": "participant",
                    "target_jid": "910000000003@s.whatsapp.net",
                    "display_text": None,
                }
            ],
        )

    def test_runtime_only_mentions_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            runtime_key = "false_fixturegroup@g.us_REPLY_222@lid"
            runtime = {
                "summary": {"enabled": True, "path": "runtime.jsonl", "usable_records": 1},
                "records_by_msg_key": {
                    runtime_key: {
                        "msg_key": runtime_key,
                        "timestamp": 1770000010,
                        "type": "chat",
                        "from_me": False,
                        "chat_jid": "fixturegroup@g.us",
                        "sender_jid": "222@lid",
                        "body": "@910000000002 hello",
                        "mentioned_jids": ["910000000002@s.whatsapp.net"],
                    },
                },
            }

            waren6.build_unified_db(
                str(db_path),
                {"message": []},
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
                runtime_store8_supplement=runtime,
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                """
                SELECT kind, target_jid, target_phone, source, confidence
                FROM message_mentions
                WHERE msg_key = ?
                """,
                (runtime_key,),
            ).fetchone()
            conn.close()

        self.assertEqual(row, ("participant", "910000000002@s.whatsapp.net", "910000000002", "runtime", "high"))

    def test_group_metadata_subject_updates_chat_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "unified_whatsapp.db"
            group_jid = "fixturegroup@g.us"

            waren6.build_unified_db(
                str(db_path),
                {
                    "chat": [
                        {"id": group_jid, "name": "Old Group Name", "t": 1778494158},
                    ],
                    "group-metadata": [
                        {
                            "id": group_jid,
                            "subject": "Example Study Group",
                            "desc": "Class group",
                            "creation": 1778485570,
                        }
                    ],
                    "message": [],
                },
                [],
                {},
                {},
                {},
                "indexeddb",
                "decrypted",
            )

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT chat_name, is_group, is_newsletter FROM chats WHERE chat_jid = ?",
                (group_jid,),
            ).fetchone()
            group_row = conn.execute(
                "SELECT subject FROM groups WHERE group_jid = ?",
                (group_jid,),
            ).fetchone()
            conn.close()

        self.assertEqual(row, ("Example Study Group", 1, 0))
        self.assertEqual(group_row, ("Example Study Group",))


class MediaIndexTests(unittest.TestCase):
    def test_media_index_links_local_transfer_file_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_root = Path(tmp)
            media_dir = case_root / "sessions" / "S1" / "transfers" / "2026-19"
            media_dir.mkdir(parents=True)
            media_file = media_dir / "photo.jpg"
            media_file.write_bytes(b"fake jpg")

            db_path = case_root / "unified_whatsapp.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(waren6.UNIFIED_SCHEMA)
            conn.execute(
                """
                INSERT INTO messages(
                    msg_key, chat_jid, timestamp, msg_type, media_filename,
                    media_mime_type, source, source_id, body_status, media_status
                )
                VALUES ('false_0@c.us_A', '0@c.us', 1, 'image', 'photo.jpg',
                        'image/jpeg', 'indexeddb', 'A', 'media_only', 'metadata_only')
                """
            )
            conn.commit()
            conn.close()

            report = waren6.index_local_media_assets(db_path, case_root, enabled=True)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT media_status, media_case_path, media_sha256 FROM messages WHERE msg_key='false_0@c.us_A'"
            ).fetchone()
            asset_count = conn.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0]
            conn.close()

        self.assertEqual(report["messages_with_local_media"], 1)
        self.assertEqual(asset_count, 1)
        self.assertEqual(row[0], "local_present")
        self.assertTrue(row[1].endswith("photo.jpg"))
        self.assertEqual(row[2], waren6.sha256_bytes(b"fake jpg"))


class UnifyPathTests(unittest.TestCase):
    def test_prepare_unify_case_accepts_zip_and_creates_output_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / "WAren6_20260509120000"
            (case / "EBWebView_Default" / "IndexedDB").mkdir(parents=True)
            zip_base = root / "case_archive"
            archive = shutil.make_archive(str(zip_base), "zip", root, case.name)

            prepared = waren6.prepare_unify_case(archive)

            self.assertTrue(str(prepared["output"]).endswith("case_archive_unified\\unified_whatsapp.db") or
                            str(prepared["output"]).endswith("case_archive_unified/unified_whatsapp.db"))
            self.assertTrue(prepared["idb_path"].exists())
            self.assertTrue(prepared["extracted_from_zip"])

    def test_cleanup_prepared_unify_case_removes_unzipped_source_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / "WAren6_20260509120000"
            (case / "EBWebView_Default" / "IndexedDB").mkdir(parents=True)
            archive = shutil.make_archive(str(root / "case_archive"), "zip", root, case.name)

            prepared = waren6.prepare_unify_case(archive)
            extract_root = Path(prepared["extract_root"])
            self.assertTrue(extract_root.exists())

            waren6.cleanup_prepared_unify_case(prepared, success=True)

            self.assertFalse(extract_root.exists())

    def test_cleanup_prepared_unify_case_preserves_unzipped_source_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / "WAren6_20260509120000"
            (case / "EBWebView_Default" / "IndexedDB").mkdir(parents=True)
            archive = shutil.make_archive(str(root / "case_archive"), "zip", root, case.name)

            prepared = waren6.prepare_unify_case(archive)
            extract_root = Path(prepared["extract_root"])
            waren6.cleanup_prepared_unify_case(prepared, success=False)

            self.assertTrue(extract_root.exists())

    def test_prepare_unify_case_accepts_tar_zst_archive_when_system_tar_supports_it(self):
        if not shutil.which("tar"):
            self.skipTest("system tar unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / "WAren6_20260509120000"
            (case / "EBWebView_Default" / "IndexedDB").mkdir(parents=True)
            archive = root / "case_archive.tar.zst"
            try:
                import subprocess

                subprocess.run(
                    ["tar", "--zstd", "-cf", str(archive), "-C", str(root), case.name],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as exc:
                self.skipTest(f"system tar lacks zstd support: {exc}")

            prepared = waren6.prepare_unify_case(archive)

            self.assertTrue(prepared["idb_path"].exists())
            self.assertTrue(Path(prepared["extract_root"]).exists())
            waren6.cleanup_prepared_unify_case(prepared, success=True)
            self.assertFalse(Path(prepared["extract_root"]).exists())


if __name__ == "__main__":
    unittest.main()
