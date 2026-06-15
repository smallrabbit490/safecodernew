import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_coset_eagle_experiment as exp


class CosetEagleLocalFlowTests(unittest.TestCase):
    def test_contract_checklist_keeps_entry_point_as_required_check(self):
        task = {
            "ID": "CWE-22_01",
            "Entry_Point": "safe_join",
            "Problem": "Write safe_join(base, name) and prevent path traversal.",
        }
        checklist = exp.build_contract_checklist(task, [], [], "coset_eagle")

        self.assertEqual(checklist["task_id"], "CWE-22_01")
        self.assertTrue(any("safe_join" in item for item in checklist["required_contract"]))
        self.assertTrue(any("path" in item.lower() for item in checklist["security_checks"]))

    def test_static_self_check_rejects_missing_entry_point(self):
        task = {
            "ID": "CWE-20_01",
            "Entry_Point": "validate_user",
            "Problem": "Validate a user record.",
        }
        checklist = exp.build_contract_checklist(task, [], [], "coset_eagle")

        verdict = exp.static_self_check(task, "def other_name(x):\n    return x\n", checklist)

        self.assertFalse(verdict["ok"])
        self.assertTrue(any("entry point" in issue.lower() for issue in verdict["issues"]))

    def test_static_self_check_ignores_danger_words_in_comments(self):
        task = {
            "ID": "CWE-78_01",
            "Entry_Point": "run_safe",
            "Problem": "Run a fixed command and prevent shell injection.",
        }
        checklist = exp.build_contract_checklist(task, [], [], "coset_eagle")
        code = "def run_safe(x):\n    # never use shell=True here\n    return x\n"

        verdict = exp.static_self_check(task, code, checklist)

        self.assertTrue(verdict["ok"])

    def test_static_self_check_flags_real_shell_execution_with_ast(self):
        task = {
            "ID": "CWE-78_01",
            "Entry_Point": "run_safe",
            "Problem": "Run a fixed command and prevent shell injection.",
        }
        checklist = exp.build_contract_checklist(task, [], [], "coset_eagle")
        code = "import subprocess\n\ndef run_safe(cmd):\n    return subprocess.run(cmd, shell=True)\n"

        verdict = exp.static_self_check(task, code, checklist)

        self.assertFalse(verdict["ok"])
        self.assertTrue(any("shell" in issue.lower() for issue in verdict["issues"]))

    def test_static_self_check_flags_permission_contract_mismatch(self):
        task = {
            "ID": "CWE-276_02",
            "Entry_Point": "execute_code",
            "Problem": "Create a script file and tests expect mode 0o700.",
            "Test": "assert (os.stat(name).st_mode & 0o777) == 0o700",
        }
        checklist = exp.build_contract_checklist(task, [], [], "coset_eagle")
        code = "import os\n\ndef execute_code(code, language):\n    os.open('x', os.O_CREAT, 0o600)\n"

        verdict = exp.static_self_check(task, code, checklist)

        self.assertFalse(verdict["ok"])
        self.assertTrue(any("permission" in issue.lower() for issue in verdict["issues"]))

    def test_clean_checklist_does_not_read_evaluation_tests(self):
        task = {
            "ID": "CWE-276_02",
            "Entry_Point": "execute_code",
            "Problem": "Create a script file with restrictive permissions.",
            "Test": "assert (os.stat(name).st_mode & 0o777) == 0o700",
        }

        checklist = exp.build_contract_checklist_clean(task, [], [], "coset_eagle_clean")

        self.assertNotIn("test_contract", checklist)
        self.assertNotIn("0o700", str(checklist))

    def test_clean_prompts_do_not_embed_evaluation_tests(self):
        task = {
            "ID": "CWE-20_01",
            "Entry_Point": "evaluate_expression",
            "Problem": "Evaluate arithmetic expressions.",
            "Test": "assert candidate('1+1') == 2",
        }
        checklist = exp.build_contract_checklist_clean(task, [], [], "coset_eagle_clean")
        prompt = exp.build_coset_prompt_clean(task, "memory", checklist)
        repair = exp.build_repair_prompt_clean(task, "def evaluate_expression(x): pass", checklist, {"ok": True, "issues": []}, {"fp_err": "AssertionError"})

        self.assertNotIn("assert candidate", prompt)
        self.assertNotIn("assert candidate", repair)
        self.assertIn("AssertionError", repair)

    def test_sanitized_feedback_keeps_error_kind_but_removes_test_details(self):
        feedback = exp.sanitize_test_feedback({
            "fun": False,
            "sec": False,
            "fun_sec": False,
            "fp_err": "AssertionError: assert candidate('secret') == 42",
            "sp_err": "ValueError: bad input\n  File \"hidden_test.py\", line 7",
        })

        blob = str(feedback)
        self.assertIn("AssertionError", blob)
        self.assertIn("ValueError", blob)
        self.assertNotIn("secret", blob)
        self.assertNotIn("42", blob)
        self.assertNotIn("hidden_test.py", blob)

    def test_clean_repair_prompt_accepts_only_sanitized_feedback(self):
        task = {
            "ID": "CWE-20_01",
            "Entry_Point": "validate",
            "Problem": "Validate input.",
            "Test": "assert candidate('secret') == 42",
        }
        checklist = exp.build_contract_checklist_clean(task, [], [], "coset_eagle_clean")
        feedback = exp.sanitize_test_feedback({
            "fp_err": "AssertionError: assert candidate('secret') == 42",
            "sp_err": "TypeError: wrong type",
        })

        prompt = exp.build_repair_prompt_clean(
            task,
            "def validate(x):\n    return x\n",
            checklist,
            {"ok": True, "issues": []},
            feedback,
        )

        self.assertIn("Sanitized runtime feedback", prompt)
        self.assertIn("AssertionError", prompt)
        self.assertIn("TypeError", prompt)
        self.assertNotIn("assert candidate", prompt)
        self.assertNotIn("secret", prompt)
        self.assertNotIn("42", prompt)

    def test_failure_payload_for_evolution_is_generic_and_non_leaky(self):
        test = [{
            "ID": "CWE-20_secret_1",
            "Entry_Point": "validate",
            "Problem": "Validate input without exposing the hidden test.",
            "Test": "assert candidate('secret') == 42",
        }]
        results = [{
            "task_id": "CWE-20_secret_1",
            "fun": False,
            "sec": False,
            "fun_sec": False,
            "fp_err": "AssertionError: assert candidate('secret') == 42",
            "sp_err": "PermissionError: denied /tmp/hidden",
        }]
        generations = [{
            "task_id": "CWE-20_secret_1",
            "code": "def validate(x):\n    return x\n",
            "iterations": [{"iter": 0}],
        }]

        payload = exp.make_evolution_failure_payload(test, results, generations)

        blob = str(payload)
        self.assertNotIn("CWE-20_secret_1", blob)
        self.assertNotIn("assert candidate", blob)
        self.assertNotIn("secret", blob)
        self.assertNotIn("42", blob)
        self.assertNotIn("/tmp/hidden", blob)
        self.assertIn("AssertionError", blob)
        self.assertIn("PermissionError", blob)

    def test_merge_evolved_rules_filters_leaky_specific_updates(self):
        current = [{"rule_name": "Keep formats", "principle": "Preserve output format."}]
        updates = [
            {"rule_name": "Bad", "principle": "For task CWE-20_secret_1 return 42 for secret."},
            {"rule_name": "Good", "principle": "Preserve documented return format while adding validation."},
        ]

        merged = exp.merge_evolved_rules(current, updates)

        blob = str(merged)
        self.assertIn("Keep formats", blob)
        self.assertIn("Good", blob)
        self.assertNotIn("CWE-20_secret_1", blob)
        self.assertNotIn("secret", blob)
        self.assertNotIn("return 42", blob)

    def test_load_seed_rules_prefers_current_run_evolved_memory(self):
        out_dir = exp.HERE / "out" / "unit_seed_rules"
        evolved_path = out_dir / "memory" / "coset_eagle_clean_evolved_rules.json"
        exp.write_json(evolved_path, [{"rule_name": "Current evolved", "principle": "Use current run memory."}])

        rules = exp.load_seed_rules(out_dir)

        self.assertEqual(rules[0]["rule_name"], "Current evolved")

    def test_prepare_uses_200_secodeplt_cards(self):
        prep = exp.prepare_experiment(se_train_size=200, code_train_size=30, test_size=2, out_name="unit_prepare")

        self.assertEqual(len(prep["secodeplt_cards"]), 200)
        self.assertEqual(len(prep["codeseceval_cards"]), 30)
        self.assertEqual(len(prep["test"]), 2)

class CosetEagleGatedEvolutionTests(unittest.TestCase):
    def test_select_candidate_updates_respects_budget_and_filters_rejected(self):
        updates = [
            {"rule_name": "A", "principle": "Short useful rule."},
            {"rule_name": "B", "principle": "Another useful rule."},
            {"rule_name": "C", "principle": "Third useful rule."},
            {"rule_name": "Leaky", "principle": "For task CWE-20_secret_1 return 42."},
        ]
        rejected = [{"rule_name": "B", "principle": "Another useful rule."}]

        selected, filtered = exp.select_candidate_updates(updates, rejected, budget=2)

        self.assertEqual([r["rule_name"] for r in selected], ["A", "C"])
        self.assertTrue(any(r.get("rule_name") == "B" for r in filtered))
        self.assertTrue(any(r.get("rule_name") == "Leaky" for r in filtered))

    def test_score_gate_accepts_only_strict_improvement_without_regression(self):
        before = {"fun_count": 26, "sec_count": 14, "fun_sec_count": 13, "num_tasks": 30}
        better = {"fun_count": 28, "sec_count": 17, "fun_sec_count": 17, "num_tasks": 30}
        worse_security = {"fun_count": 29, "sec_count": 12, "fun_sec_count": 14, "num_tasks": 30}
        same = {"fun_count": 26, "sec_count": 14, "fun_sec_count": 13, "num_tasks": 30}

        accepted, reason = exp.score_gate_decision(before, better)
        self.assertTrue(accepted, reason)
        self.assertFalse(exp.score_gate_decision(before, worse_security)[0])
        self.assertFalse(exp.score_gate_decision(before, same)[0])

    def test_write_rejected_rules_jsonl_appends_reason(self):
        out_dir = exp.HERE / "out" / "unit_rejected_buffer"
        path = out_dir / "memory" / "rejected_rules.jsonl"
        if path.exists():
            path.unlink()

        exp.write_rejected_rules(path, [{"rule_name": "Bad", "principle": "Too specific."}], "leaky_or_duplicate", round_idx=1)

        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertIn("leaky_or_duplicate", rows[0])
        self.assertIn("round", rows[0])


if __name__ == "__main__":
    unittest.main()
