import argparse
import unittest

import waren6


class OutputProfileTests(unittest.TestCase):
    def test_store8_debug_reports_are_quiet_by_default(self):
        args = argparse.Namespace(
            store8_debug=False,
            profile_store8_crypto=False,
            decrypt_store8_opaque=False,
            hunt_opaque_salt=False,
            opaque_salt_file=None,
            crypto_artifacts_report=None,
            store8_crypto_profile=None,
            store8_decryption_report=None,
            store8_salt_hunt_report=None,
        )

        self.assertFalse(waren6.should_write_store8_debug_reports(args))

    def test_store8_debug_reports_are_written_when_research_is_requested(self):
        args = argparse.Namespace(
            store8_debug=True,
            profile_store8_crypto=False,
            decrypt_store8_opaque=False,
            hunt_opaque_salt=False,
            opaque_salt_file=None,
            crypto_artifacts_report=None,
            store8_crypto_profile=None,
            store8_decryption_report=None,
            store8_salt_hunt_report=None,
        )

        self.assertTrue(waren6.should_write_store8_debug_reports(args))

    def test_media_index_report_is_quiet_unless_media_indexing_is_requested(self):
        self.assertFalse(waren6.should_write_media_index_report(False, None))
        self.assertTrue(waren6.should_write_media_index_report(True, None))
        self.assertTrue(waren6.should_write_media_index_report(False, "media_index_report.json"))


if __name__ == "__main__":
    unittest.main()
