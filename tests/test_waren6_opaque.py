import unittest
import tempfile
from pathlib import Path

import waren6


class OpaqueMessageTests(unittest.TestCase):
    def test_plain_indexeddb_body_is_preferred(self):
        body, status = waren6.select_indexeddb_message_body({
            "body": "hello",
            "msgRowOpaqueData": {"_data": b"cipher", "iv": (0,) * 16, "_keyId": 1},
        })

        self.assertEqual(body, "hello")
        self.assertEqual(status, "plain")

    def test_encrypted_opaque_chat_body_is_classified(self):
        body, status = waren6.select_indexeddb_message_body({
            "type": "chat",
            "msgRowOpaqueData": {"_data": b"cipher", "iv": (0,) * 16, "_keyId": 1},
        })

        self.assertIsNone(body)
        self.assertEqual(status, "opaque_unresolved")

    def test_hkdf_sha256_matches_rfc5869_vector(self):
        okm = waren6.hkdf_sha256(
            ikm=bytes.fromhex("0b" * 22),
            salt=bytes.fromhex("000102030405060708090a0b0c"),
            info=bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
            length=42,
        )

        self.assertEqual(
            okm.hex(),
            "3cb25f25faacd57a90434f64d0362f2a"
            "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865",
        )

    def test_aes_cbc_pkcs7_decrypts_known_store8_vector(self):
        plaintext = waren6.aes_128_cbc_pkcs7_decrypt(
            ciphertext=bytes.fromhex(
                "bfb2be6c8923d8236ba61b5c68fb3e541855c1ffbcaedd430a6124399f7a43ca"
                "08529012d48304b5ca1a6cbf48424a75e964161b2d5db94b05a58c1298b1aeca"
            ),
            key=bytes.fromhex("e37e7a66d7c42a4bd966a614a5ca69ea"),
            iv=bytes.fromhex("202122232425262728292a2b2c2d2e2f"),
        )

        self.assertEqual(
            plaintext,
            b'{"body":"Store 8 recovered","caption":"ignored"}',
        )

    def test_synthetic_opaque_record_is_recovered_with_supplied_salt(self):
        context = waren6.Store8CryptoContext(
            ikm_candidates=[
                {
                    "name": "test_ikm",
                    "source": "unit",
                    "value": bytes.fromhex(
                        "000102030405060708090a0b0c0d0e0f"
                        "101112131415161718191a1b1c1d1e1f"
                    ),
                }
            ],
            salt_candidates=[
                {
                    "name": "network_salt",
                    "source": "unit",
                    "value": bytes.fromhex("606162636465666768696a6b6c6d6e6f7071727374757677"),
                }
            ],
            info_candidates=[
                {
                    "name": "test_info",
                    "source": "unit",
                    "value": b"WAren6 Store8 Test Info",
                }
            ],
        )
        record = {
            "type": "chat",
            "msgRowOpaqueData": {
                "_scheme": 1,
                "_keyId": 1,
                "iv": list(bytes.fromhex("202122232425262728292a2b2c2d2e2f")),
                "_data": bytes.fromhex(
                    "bfb2be6c8923d8236ba61b5c68fb3e541855c1ffbcaedd430a6124399f7a43ca"
                    "08529012d48304b5ca1a6cbf48424a75e964161b2d5db94b05a58c1298b1aeca"
                ),
            },
        }

        result = waren6.decrypt_store8_opaque_record(record, context)

        self.assertEqual(result["status"], "decrypted")
        self.assertEqual(result["body"], "Store 8 recovered")
        self.assertEqual(result["scheme"], 1)
        self.assertEqual(result["key_id"], 1)

    def test_opaque_decryptor_fails_closed_when_network_salt_missing(self):
        context = waren6.Store8CryptoContext(
            ikm_candidates=[{"name": "test_ikm", "source": "unit", "value": b"x" * 32}],
            salt_candidates=[],
            info_candidates=[{"name": "test_info", "source": "unit", "value": b"info"}],
        )

        result = waren6.decrypt_store8_opaque_record(
            {"msgRowOpaqueData": {"_scheme": 1, "_keyId": 1, "iv": [0] * 16, "_data": b"\x00" * 16}},
            context,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker"], "network_salt_missing")

    def test_profile_store8_crypto_data_counts_opaque_shape(self):
        profile = waren6.profile_store8_crypto_data([
            {"msgRowOpaqueData": {"_scheme": 1, "_keyId": 1, "iv": [0] * 16, "_data": b"a" * 64}},
            {"msgRowOpaqueData": {"_scheme": 2, "_keyId": 3, "iv": [0] * 12, "_data": b"b" * 48}},
            {"body": "plain"},
        ])

        self.assertEqual(profile["store8_total_rows"], 3)
        self.assertEqual(profile["store8_opaque_rows"], 2)
        self.assertEqual(profile["schemes"], {"1": 1, "2": 1})
        self.assertEqual(profile["key_ids"], {"1": 1, "3": 1})
        self.assertEqual(profile["iv_lengths"], {"16": 1, "12": 1})
        self.assertEqual(profile["ciphertext_lengths"], {"64": 1, "48": 1})

    def test_salt_file_accepts_hex_or_json_without_logging_raw_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            salt_file = Path(tmp) / "salt.json"
            salt_file.write_text('{"network_salt":"61626364656667"}', encoding="utf-8")

            candidates, inventory = waren6.load_opaque_salt_file(salt_file)

        self.assertEqual(candidates[0]["value"], b"abcdefg")
        self.assertNotIn("abcdefg", str(inventory))
        self.assertEqual(inventory["artifacts"][0]["sha256"], "7d1a54127b222502f5b79b5fb0803061152a44f92b37e23c6527baf665d4da9a")

    def test_salt_hunter_extracts_named_hex_and_base64_without_raw_values(self):
        payload = b'{"webwa_network_salt":"61626364656667","other":"U0VDUkVU"} salt=YWJjZGVmZw=='

        candidates = waren6.extract_opaque_salt_candidates_from_bytes(payload, "artifact.har")

        values = {c["value"] for c in candidates}
        self.assertIn(b"abcdefg", values)
        self.assertNotIn("abcdefg", str([c["public"] for c in candidates]))
        self.assertTrue(all(c["public"]["sha256"] for c in candidates))

    def test_salt_hunter_validates_candidate_before_accepting_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "network.json"
            artifact.write_text(
                '{"webwa_network_salt":"606162636465666768696a6b6c6d6e6f7071727374757677"}',
                encoding="utf-8",
            )
            context = waren6.Store8CryptoContext(
                ikm_candidates=[{
                    "name": "test_ikm",
                    "source": "unit",
                    "value": bytes.fromhex(
                        "000102030405060708090a0b0c0d0e0f"
                        "101112131415161718191a1b1c1d1e1f"
                    ),
                }],
                info_candidates=[{
                    "name": "test_info",
                    "source": "unit",
                    "value": b"WAren6 Store8 Test Info",
                }],
            )
            messages = [{
                "id": "true_0@c.us_TEST",
                "type": "chat",
                "msgRowOpaqueData": {
                    "_scheme": 1,
                    "_keyId": 1,
                    "iv": list(bytes.fromhex("202122232425262728292a2b2c2d2e2f")),
                    "_data": bytes.fromhex(
                        "bfb2be6c8923d8236ba61b5c68fb3e541855c1ffbcaedd430a6124399f7a43ca"
                        "08529012d48304b5ca1a6cbf48424a75e964161b2d5db94b05a58c1298b1aeca"
                    ),
                },
            }]

            report = waren6.hunt_store8_network_salts([artifact], messages, context)

        self.assertEqual(report["summary"]["validated_candidates"], 1)
        self.assertEqual(len(context.salt_candidates), 1)
        self.assertEqual(context.salt_candidates[0]["value"], bytes.fromhex("606162636465666768696a6b6c6d6e6f7071727374757677"))
        self.assertEqual(report["validated"][0]["sample_body_sha256"], "a52b2b9df2449fb32576547bc2d9081a37dee99807df1b85dfd21cd263fae287")

    def test_salt_hunter_rejects_candidates_that_do_not_decrypt(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "network.json"
            artifact.write_text('{"webwa_network_salt":"000102030405060708090a0b0c0d0e0f"}', encoding="utf-8")
            context = waren6.Store8CryptoContext(
                ikm_candidates=[{"name": "test_ikm", "source": "unit", "value": b"x" * 32}],
                info_candidates=[{"name": "test_info", "source": "unit", "value": b"info"}],
            )

            report = waren6.hunt_store8_network_salts(
                [artifact],
                [{"id": "m", "msgRowOpaqueData": {"_scheme": 1, "_keyId": 1, "iv": [0] * 16, "_data": b"\x00" * 16}}],
                context,
            )

        self.assertEqual(report["summary"]["validated_candidates"], 0)
        self.assertEqual(context.salt_candidates, [])

class GenericStorageTextTests(unittest.TestCase):
    def test_embedded_base64_preview_is_stripped_without_losing_caption(self):
        raw = "*New: Keep conversations going*\nPaste a link and send. /9j/4AAQSkZJRgABAgAAAQABAAD"

        self.assertEqual(
            waren6.clean_media_text(raw, msg_type="interactive"),
            "*New: Keep conversations going*\nPaste a link and send."
        )

    def test_validation_counter_uses_visible_text_for_embedded_previews(self):
        raw = "Visible examiner text /9j/4AAQSkZJRgABAgAAAQABAAD"

        counter = waren6.source_text_counter([
            {"chatId": "0@c.us", "timestamp": "1777367456", "text": raw}
        ])

        self.assertEqual(counter[("0@c.us", 1777367456, "Visible examiner text")], 1)

    def test_validation_counter_ignores_duplicate_document_filename_artifacts(self):
        counter = waren6.source_text_counter([
            {"chatId": "0@c.us", "timestamp": "1777367456", "text": "file.pdf file.pdf"}
        ])

        self.assertEqual(counter, {})

    def test_validation_counter_normalizes_social_preview_text(self):
        raw = "https://youtube.com/shorts/example\n\nSender caption kept elsewhere"

        counter = waren6.source_text_counter([
            {"chatId": "0@c.us", "timestamp": "1777367456", "text": raw}
        ])

        self.assertEqual(counter[("0@c.us", 1777367456, "https://youtube.com/shorts/example")], 1)


if __name__ == "__main__":
    unittest.main()
