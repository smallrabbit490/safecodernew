import json
import sys
import tempfile
from pathlib import Path
import unittest

import run_language_method_matrix as matrix
import run_actual_5_python_methods as actual
from translation_pipeline.models import truncate_text
from translation_pipeline.validators import run_command_limited


class LanguageMethodMatrixSafetyTests(unittest.TestCase):
    def test_compiled_test_numbers_are_split_between_function_and_security(self):
        task = {
            "Test-FP": """
def check(candidate):
    # 1) normal input
    assert candidate("ok")
    # 2) another normal input
    assert candidate("still ok")
""",
            "Test-SP": """
def check(candidate):
    # 3) malicious input should be rejected
    assert candidate("../secret")
    # 4) malformed input should be rejected
    assert candidate("{bad")
""",
        }

        split = matrix.compiled_test_number_split(task)

        self.assertEqual(split["functional"], {1, 2})
        self.assertEqual(split["security"], {3, 4})

    def test_compiled_harness_result_keeps_function_and_security_separate(self):
        task = {
            "Test-FP": "# 1) normal input\n# 2) another normal input\n",
            "Test-SP": "# 3) malicious input\n# 4) malformed input\n",
        }
        result = matrix.compiled_harness_eval_from_result(
            task,
            {
                "ok": False,
                "stdout": "",
                "stderr": "Test 3 failed: malicious input was accepted\n",
                "details": {"phase": "run", "error_type": "runtime_error"},
            },
        )

        self.assertTrue(result["fun"])
        self.assertFalse(result["sec"])
        self.assertFalse(result["fun_sec"])
        self.assertFalse(result["compile_run_ok"])
        self.assertEqual(result["failed_security_tests"], [3])

    def test_compiled_harness_ok_passes_unnumbered_fp_and_sp_sections(self):
        task = {
            "Test-FP": "def check(candidate):\n    assert candidate('ok') == 'ok'\n",
            "Test-SP": "def check(candidate):\n    assert_raises(candidate, '../secret')\n",
        }

        result = matrix.compiled_harness_eval_from_result(
            task,
            {"ok": True, "stdout": "Tests passed: 8/8", "stderr": "", "details": {"phase": "run"}},
        )

        self.assertTrue(result["fun"])
        self.assertTrue(result["sec"])
        self.assertTrue(result["fun_sec"])

    def test_unclassified_run_failure_does_not_get_security_credit(self):
        task = {
            "Test-FP": "def check(candidate):\n    assert candidate('ok') == 'ok'\n",
            "Test-SP": "def check(candidate):\n    # 6) dangerous input\n    assert_raises(candidate, '../secret')\n",
        }

        result = matrix.compiled_harness_eval_from_result(
            task,
            {
                "ok": False,
                "stdout": "Test 3 failed: normal case broke",
                "stderr": "exit status 1",
                "details": {"phase": "run", "error_type": "runtime_error"},
            },
        )

        self.assertFalse(result["fun"])
        self.assertFalse(result["sec"])
        self.assertFalse(result["fun_sec"])
        self.assertEqual(result["unclassified_failed_tests"], [3])

    def test_go_entry_removal_handles_interface_return_braces(self):
        source = """
package main

import "encoding/json"

func GetPickleData(pickled []byte) (interface{}, error) {
    var data interface{}
    if err := json.Unmarshal(pickled, &data); err != nil {
        return nil, err
    }
    return data, nil
}

func main() {}
"""

        stripped = matrix._remove_entry_function("go", source, "getPickleData")

        self.assertNotIn("func GetPickleData", stripped)
        self.assertNotIn(", error) {", stripped)
        self.assertIn("func main()", stripped)

    def test_go_entry_removal_matches_snake_case_to_camel_case(self):
        source = """
package main

func evaluateExpression(expression string) (float64, error) {
    return 1, nil
}

func main() {}
"""

        stripped = matrix._remove_entry_function("go", source, "evaluate_expression")

        self.assertNotIn("func evaluateExpression", stripped)
        self.assertIn("func main()", stripped)

    def test_go_candidate_harness_removes_demo_main_and_saved_entry(self):
        task = {"Entry_Point": "evaluate_expression"}
        candidate = """
package main

import "fmt"

func evaluateExpression(expression string) (float64, error) {
    return 1, nil
}

func main() { fmt.Println("demo") }
"""
        saved = """
package main

import "fmt"

func evaluateExpression(expression string) (float64, error) {
    return 0, nil
}

func main() {
    value, _ := evaluateExpression("1+1")
    fmt.Println(value)
}
"""

        harness = matrix._build_go_candidate_harness(task, candidate, saved)

        self.assertEqual(harness.count("func evaluateExpression"), 1)
        self.assertNotIn('fmt.Println("demo")', harness)
        self.assertIn('evaluateExpression("1+1")', harness)

    def test_cpp_go_prompts_do_not_request_python_code_blocks(self):
        task = {
            "ID": "demo",
            "Problem": "Return a safe value.",
            "Entry_Point": "demo_func",
        }
        for language in ("cpp", "go"):
            prompt = matrix.build_prompt(actual.METHODS[2], language, task, "secure")

            self.assertNotIn("Python code block", prompt)
            self.assertIn(matrix.LANGUAGE_LABELS[language], prompt)
            self.assertIn("one code block", prompt)

    def test_compiled_secure_prompt_forbids_demo_main(self):
        task = {
            "ID": "demo",
            "Problem": "Return a safe value.",
            "Entry_Point": "demo_func",
        }

        prompt = matrix.build_prompt(actual.OURS_METHOD, "cpp", task, "secure")

        self.assertIn("Do not include a main function", prompt)
        self.assertIn("external test harness", prompt)

    def test_compiled_prompt_includes_harness_contract_when_available(self):
        task = {
            "ID": "demo",
            "Problem": "Return a safe value.",
            "Entry_Point": "demo_func",
            "Secure Code Test Result": {"details": {"sandbox_dir": ""}},
        }
        original = matrix.extract_harness_entry_signature
        original_context = matrix.extract_harness_entry_context

        try:
            matrix.extract_harness_entry_signature = lambda language, task: "int demo_func(const std::string& value)"
            matrix.extract_harness_entry_context = lambda language, task: "struct Request { std::string value; };"
            prompt = matrix.build_prompt(actual.METHODS[0], "cpp", task, "secure")
        finally:
            matrix.extract_harness_entry_signature = original
            matrix.extract_harness_entry_context = original_context

        self.assertIn("Harness contract", prompt)
        self.assertIn("int demo_func(const std::string& value)", prompt)
        self.assertIn("Available harness context", prompt)
        self.assertIn("struct Request", prompt)
        self.assertIn("Do not define `main`", prompt)

    def test_cpp_candidate_harness_preserves_candidate_includes(self):
        task = {"Entry_Point": "answer"}
        candidate = """
#include <any>
#include <vector>

std::any answer() {
    return 42;
}
"""
        saved = """
#include <iostream>

int answer() {
    return 0;
}

int main() {
    return answer() == 42 ? 0 : 1;
}
"""

        harness = matrix.build_cpp_candidate_harness(task, candidate, saved)

        self.assertIn("#include <any>", harness)
        self.assertEqual(harness.count("#include <vector>"), 1)
        self.assertNotIn("int answer() {\n    return 0;", harness)

    def test_ours_prompt_uses_retrieved_full_secodeplt_experience_pool(self):
        task = {
            "ID": "CWE-022_author_1.py",
            "Problem": "CWE-22: Read a file path safely inside a base directory.",
            "Entry_Point": "read_file",
        }

        prompt = matrix.build_prompt(actual.OURS_METHOD, "python", task, "secure")

        self.assertIn("Full SeCodePLT retrieved experience", prompt)
        self.assertIn("Most relevant learned examples", prompt)
        self.assertNotIn("CWE-22", prompt)
        self.assertNotIn("CWE-022", prompt)
        self.assertIn("Read a file path safely inside a base directory.", prompt)

    def test_only_ours_method_selection_excludes_baselines(self):
        methods = matrix.selected_methods(include_ours=True, only_ours=True)

        self.assertEqual([method["name"] for method in methods], ["Ours / SCT-Agent"])

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


class ExistingBaselineRevalidationTests(unittest.TestCase):
    def test_sharded_input_root_matches_existing_layout(self):
        import rerun_existing_baselines_current_standard as reval

        out_root = Path("out")

        root = reval.sharded_input_root(out_root, "Base", "python")

        self.assertEqual(root, out_root / "full_secure_sharded_guarded_base_python" / "Base")

    def test_python_rows_are_re_evaluated_with_native_oracle(self):
        import rerun_existing_baselines_current_standard as reval

        task = {
            "ID": "demo",
            "subset": "base",
            "Entry_Point": "answer",
            "Test-FP": "def check(candidate):\n    assert candidate() == 42\n",
            "Test-SP": "def check(candidate):\n    assert candidate() != 0\n",
        }
        old_row = {
            "task_id": "demo",
            "secure": {"code": "def answer():\n    return 42\n", "eval": {"fun": False, "sec": False, "fun_sec": False}},
        }

        row = reval.reeval_row("python", task, old_row)

        self.assertTrue(row["metrics"]["secure_functional"])
        self.assertTrue(row["metrics"]["secure_security"])
        self.assertTrue(row["metrics"]["secure_func_sec"])

    def test_method_slug_filter_keeps_requested_baseline_only(self):
        import rerun_existing_baselines_current_standard as reval

        methods = reval.methods_from_slugs(["ra_gen"])

        self.assertEqual([method["name"] for method in methods], ["RA-Gen"])

    def test_compiled_rows_use_harness_without_standalone_compile_run(self):
        import rerun_existing_baselines_current_standard as reval

        task = {"ID": "demo", "Test-FP": "# 1) normal\n", "Test-SP": "# 2) security\n"}
        old_row = {"task_id": "demo", "secure": {"code": "int answer(){return 1;}", "eval": {}}}
        calls = {"evaluate": 0, "harness": 0}
        original_evaluate = reval.matrix.evaluate
        original_harness = reval.matrix.validate_compiled_candidate_with_harness

        class FakeHarnessResult:
            ok = True
            language = "cpp"
            mode = "secure"
            stdout = "Tests passed: 2/2"
            stderr = ""
            details = {"phase": "run"}

        def fake_evaluate(*args, **kwargs):
            calls["evaluate"] += 1
            raise AssertionError("standalone compiled evaluation should not run")

        def fake_harness(*args, **kwargs):
            calls["harness"] += 1
            return FakeHarnessResult()

        try:
            reval.matrix.evaluate = fake_evaluate
            reval.matrix.validate_compiled_candidate_with_harness = fake_harness
            row = reval.reeval_row("cpp", task, old_row)
        finally:
            reval.matrix.evaluate = original_evaluate
            reval.matrix.validate_compiled_candidate_with_harness = original_harness

        self.assertEqual(calls["evaluate"], 0)
        self.assertEqual(calls["harness"], 1)
        self.assertTrue(row["metrics"]["secure_func_sec"])


if __name__ == "__main__":
    unittest.main()
