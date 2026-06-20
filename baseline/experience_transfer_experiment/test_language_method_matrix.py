import json
import sys
import tempfile
from pathlib import Path
import unittest

import run_language_method_matrix as matrix
from translation_pipeline.models import truncate_text
from translation_pipeline.validators import run_command_limited


class LanguageMethodMatrixSafetyTests(unittest.TestCase):
    def test_compact_row_for_storage_truncates_large_raw_and_validator_output(self):
        huge = "x" * 20000
        row = {
            "task_id": "CWE-test",
            "secure": {
                "raw": huge,
                "code": "int main(){return 0;}",
                "eval": {
                    "result": {
                        "stdout": huge,
                        "stderr": huge,
                        "details": {"nested": huge, "args": ["docker", "run"]},
                    }
                },
            },
            "insecure": None,
        }

        compact = matrix.compact_row_for_storage(row)
        encoded = json.dumps(compact, ensure_ascii=False)

        self.assertLess(len(encoded), 12000)
        self.assertLessEqual(len(compact["secure"]["raw"]), matrix.MAX_STORED_TEXT_CHARS + 80)
        self.assertLessEqual(len(compact["secure"]["eval"]["result"]["stdout"]), matrix.MAX_STORED_TEXT_CHARS + 80)
        self.assertLessEqual(len(compact["secure"]["eval"]["result"]["stderr"]), matrix.MAX_STORED_TEXT_CHARS + 80)
        self.assertIn("truncated", compact["secure"]["raw"])
        self.assertEqual(compact["secure"]["eval"]["result"]["details"]["args"], ["docker", "run"])

    def test_shared_truncate_text_keeps_head_and_tail(self):
        text = "a" * 3000 + "TAIL"

        compact = truncate_text(text, 100)

        self.assertLessEqual(len(compact), 160)
        self.assertTrue(compact.startswith("a" * 50))
        self.assertTrue(compact.endswith("TAIL"))
        self.assertIn("truncated", compact)

    def test_run_command_limited_drops_excess_output_while_process_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            code = "import sys; sys.stdout.write('x' * 5000); sys.stderr.write('e' * 5000)"
            returncode, stdout, stderr, timed_out = run_command_limited(
                [sys.executable, "-c", code],
                Path(temp),
                timeout=10,
                output_limit=2000,
            )

        self.assertEqual(returncode, 0)
        self.assertFalse(timed_out)
        self.assertLess(len(stdout), 2100)
        self.assertLess(len(stderr), 2100)
        self.assertIn("truncated validator stdout", stdout)
        self.assertIn("truncated validator stderr", stderr)


if __name__ == "__main__":
    unittest.main()
