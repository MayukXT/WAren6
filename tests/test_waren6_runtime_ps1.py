import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "waren6.ps1"


class PowerShellRuntimeCaptureTests(unittest.TestCase):
    def _source(self):
        return SCRIPT.read_text(encoding="utf-8", errors="replace")

    def _runtime_expression(self):
        source = self._source()
        function_start = source.index("function Get-WAren6RuntimeExpression")
        heredoc_start = source.index("return @'", function_start)
        expression_start = source.index("\n", heredoc_start) + 1
        expression_end = source.index("\n'@", expression_start)
        return source[expression_start:expression_end]

    def test_hybrid_runtime_capture_is_preserved_after_acquisition_copy(self):
        source = self._source()

        self.assertIn("function Copy-WAren6RuntimeSupplement", source)
        self.assertRegex(
            source,
            r"Invoke-WAren6RuntimeStore8Capture\s+-OutputDirectory\s+\$runtimeCaptureRoot",
        )
        self.assertNotRegex(
            source,
            r"Invoke-WAren6RuntimeStore8Capture\s+-OutputDirectory\s+\$targetOutput",
        )

        acquisition = source.index("Copy-Directory -Source $WhatsAppPath")
        preserve = source.index("Copy-WAren6RuntimeSupplement `")
        self.assertLess(acquisition, preserve)

    def test_runtime_expression_does_not_shadow_message_key_helper(self):
        expression = self._runtime_expression()

        self.assertIn("function normalizeMsgKey(", expression)
        self.assertNotIn("function msgKey(", expression)
        self.assertIn("const latestEditMsgKey = normalizeMsgKey(", expression)
        self.assertIn("const protocolMessageKey = normalizeMsgKey(", expression)

    def test_runtime_capture_reports_javascript_evaluation_errors(self):
        source = self._source()

        self.assertIn("$result.exceptionDetails", source)
        self.assertIn("$lastRuntimeException", source)
        self.assertIn("Start-Sleep -Seconds 3", source)
        self.assertIn("Runtime JS evaluation failed", source)


if __name__ == "__main__":
    unittest.main()
