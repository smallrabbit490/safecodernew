from translation_pipeline.research_diagnostics import (
    analyze_failure_atlas,
    analyze_diff_preservation,
    analyze_paired_outcomes,
    analyze_track_outcomes,
    compute_oracle_router,
    compute_router_regret,
    extract_security_delta_ir,
    plan_paired_repair_actions,
    synthesize_repair_policy,
    simulate_track_router,
)


def _record(record_id, secure_cpp=False, secure_go=False, insecure_cpp=False, insecure_go=False):
    return {
        "ID": record_id,
        "Problem": "demo command injection",
        "Secure Code": "def run(x): return safe_exec(x)",
        "Insecure Code": "def run(x): return os.system('echo ' + x)",
        "Secure Code C++": "bool run(string x) { return x.find(';') == string::npos; }",
        "Insecure Code C++": "int run(string x) { return system(('echo ' + x).c_str()); }",
        "Secure Code Go": 'func run(x string) bool { return !strings.Contains(x, ";") }',
        "Insecure Code Go": 'func run(x string) { exec.Command("sh", "-c", "echo "+x).Run() }',
        "Secure Code C++ Test Result": {"ok": secure_cpp},
        "Secure Code Go Test Result": {"ok": secure_go},
        "Insecure Code C++ Behavior Result": {"ok": insecure_cpp},
        "Insecure Code Go Behavior Result": {"ok": insecure_go},
    }


def _failed_result(error_type=None, stderr=""):
    return {
        "ok": False,
        "error_type": error_type,
        "stderr": stderr,
    }


def test_oracle_router_selects_best_architecture_per_record():
    architecture_records = {
        "M4": [
            _record("a", True, True, False, False),
            _record("b", True, True, True, True),
        ],
        "M6": [
            _record("a", True, True, True, True),
            _record("b", True, False, True, True),
        ],
    }

    report = compute_oracle_router(architecture_records)

    assert report["records"] == 2
    assert report["all_four_ok"] == 2
    assert report["all_four_rate"] == 1.0
    assert report["choices"] == [
        {"ID": "a", "architecture": "M6", "score": 4},
        {"ID": "b", "architecture": "M4", "score": 4},
    ]


def test_diff_preservation_detects_secure_insecure_separation():
    records = [
        _record("preserved", True, True, True, True),
        {
            **_record("collapsed", True, True, True, True),
            "Insecure Code Go": 'func run(x string) bool { return !strings.Contains(x, ";") }',
        },
    ]

    report = analyze_diff_preservation(records)

    assert report["records"] == 2
    assert report["diff_preserved"] == 1
    assert report["diff_preservation_rate"] == 0.5
    collapsed = [item for item in report["items"] if item["ID"] == "collapsed"][0]
    assert collapsed["diff_preserved"] is False
    assert "go" in collapsed["collapsed_languages"]


def test_track_outcomes_show_per_track_success_rates():
    records = [
        _record("a", True, True, False, True),
        _record("b", True, False, False, False),
    ]

    report = analyze_track_outcomes(records)

    assert report["records"] == 2
    assert report["tracks"]["secure_cpp"]["ok"] == 2
    assert report["tracks"]["secure_cpp"]["rate"] == 1.0
    assert report["tracks"]["secure_go"]["ok"] == 1
    assert report["tracks"]["secure_go"]["rate"] == 0.5
    assert report["tracks"]["insecure_cpp"]["ok"] == 0
    assert report["tracks"]["insecure_cpp"]["rate"] == 0.0
    assert report["weakest_tracks"] == ["insecure_cpp"]


def test_router_regret_compares_architectures_to_oracle():
    architecture_records = {
        "M4": [
            _record("a", True, True, False, False),
            _record("b", True, True, True, True),
        ],
        "M6": [
            _record("a", True, True, True, True),
            _record("b", True, False, True, True),
        ],
    }
    oracle = compute_oracle_router(architecture_records)

    regrets = compute_router_regret(architecture_records, oracle)

    assert regrets["oracle_all_four_rate"] == 1.0
    assert regrets["architectures"]["M4"]["all_four_rate"] == 0.5
    assert regrets["architectures"]["M4"]["router_regret"] == 0.5
    assert regrets["architectures"]["M6"]["all_four_rate"] == 0.5
    assert regrets["architectures"]["M6"]["router_regret"] == 0.5


def test_failure_atlas_classifies_common_language_failures():
    records = [
        {
            **_record("go-import", True, False, True, True),
            "Secure Code Go Test Result": _failed_result(stderr='main.go:3:2: "os" imported and not used'),
        },
        {
            **_record("go-undefined", True, True, True, False),
            "Insecure Code Go Behavior Result": _failed_result(stderr="undefined: yaml.Unmarshal"),
        },
        {
            **_record("cpp-compile", False, True, True, True),
            "Secure Code C++ Test Result": _failed_result(
                error_type="compile_error",
                stderr="error: 'vector' was not declared in this scope",
            ),
        },
    ]

    report = analyze_failure_atlas(records)

    assert report["records"] == 3
    assert report["failures"] == 3
    assert report["by_category"]["go_unused_import"]["count"] == 1
    assert report["by_category"]["go_undefined_symbol"]["count"] == 1
    assert report["by_category"]["cpp_compile_error"]["count"] == 1
    assert report["by_track"]["secure_go"]["count"] == 1
    assert report["by_track"]["insecure_go"]["count"] == 1
    assert report["by_track"]["secure_cpp"]["count"] == 1


def test_track_router_picks_best_architecture_per_track():
    architecture_records = {
        "M4": [
            _record("a", True, True, False, False),
            _record("b", True, True, False, False),
        ],
        "M7": [
            _record("a", False, False, True, True),
            _record("b", True, False, True, True),
        ],
    }

    report = simulate_track_router(architecture_records)

    assert report["records"] == 2
    assert report["policy"] == {
        "secure_cpp": "M4",
        "secure_go": "M4",
        "insecure_cpp": "M7",
        "insecure_go": "M7",
    }
    assert report["all_four_ok"] == 2
    assert report["all_four_rate"] == 1.0
    assert report["track_rates"]["secure_cpp"] == 1.0
    assert report["track_rates"]["insecure_go"] == 1.0


def test_paired_outcomes_group_secure_and_insecure_by_language():
    records = [
        _record("both", True, True, True, True),
        _record("secure-only", True, True, False, False),
        _record("insecure-only", False, False, True, True),
        _record("both-fail", False, False, False, False),
    ]

    report = analyze_paired_outcomes(records)

    assert report["records"] == 4
    assert report["languages"]["cpp"]["both_ok"] == 1
    assert report["languages"]["cpp"]["secure_only"] == 1
    assert report["languages"]["cpp"]["insecure_only"] == 1
    assert report["languages"]["cpp"]["both_fail"] == 1
    assert report["languages"]["cpp"]["pair_success_rate"] == 0.25
    assert report["languages"]["go"]["both_ok"] == 1
    assert report["languages"]["go"]["secure_only"] == 1
    assert report["languages"]["go"]["insecure_only"] == 1
    assert report["languages"]["go"]["both_fail"] == 1


def test_repair_policy_maps_failure_categories_to_change_budgets():
    failure_atlas = {
        "by_category": {
            "cpp_compile_error": {"count": 2, "examples": []},
            "go_undefined_symbol": {"count": 1, "examples": []},
            "behavior_mismatch": {"count": 3, "examples": []},
        }
    }

    policy = synthesize_repair_policy(failure_atlas)

    assert policy["rules"]["cpp_compile_error"]["allowed_change_scope"] == "includes_types_signatures_only"
    assert "Do not rewrite security logic" in policy["rules"]["cpp_compile_error"]["constraints"]
    assert policy["rules"]["go_undefined_symbol"]["allowed_change_scope"] == "imports_dependencies_api_names_only"
    assert policy["rules"]["behavior_mismatch"]["secure_allowed_change_scope"] == "security_guard_logic"
    assert policy["rules"]["behavior_mismatch"]["insecure_allowed_change_scope"] == "preserve_expected_vulnerable_behavior"
    assert policy["rules"]["behavior_mismatch"]["count"] == 3


def test_security_delta_ir_extracts_contrastive_security_shape():
    record = {
        **_record("CWE-078_demo.py", True, True, True, True),
        "Secure Code": "def run(x): validate(x); return safe_exec(x)",
    }

    delta = extract_security_delta_ir(record)

    assert delta["ID"] == "CWE-078_demo.py"
    assert delta["cwe"] == "CWE-078"
    assert "command" in delta["python_delta"]["shared_security_groups"]
    assert "validation" in delta["python_delta"]["secure_only_groups"]
    assert "safe" in delta["python_delta"]["secure_only_tokens"]
    assert delta["target_language_delta"]["cpp"]["diff_preserved"] is True
    assert delta["target_language_delta"]["go"]["diff_preserved"] is True
    assert delta["risk_notes"]


def test_paired_repair_actions_use_pair_category_and_delta_status():
    records = [
        _record("both", True, True, True, True),
        _record("secure-only", True, True, False, False),
        _record("insecure-only", False, False, True, True),
        _record("both-fail", False, False, False, False),
    ]
    paired = analyze_paired_outcomes(records)
    delta_irs = {"items": [extract_security_delta_ir(record) for record in records]}

    plan = plan_paired_repair_actions(paired, delta_irs)

    assert plan["records"] == 4
    cpp_actions = {item["ID"]: item["action"] for item in plan["languages"]["cpp"]["items"]}
    assert cpp_actions["both"] == "accept_pair"
    assert cpp_actions["secure-only"] == "repair_insecure"
    assert cpp_actions["insecure-only"] == "repair_secure"
    assert cpp_actions["both-fail"] == "repair_both"
    assert plan["languages"]["cpp"]["by_action"]["accept_pair"] == 1
    assert plan["languages"]["cpp"]["by_action"]["repair_insecure"] == 1
    assert plan["languages"]["cpp"]["by_action"]["repair_secure"] == 1
    assert plan["languages"]["cpp"]["by_action"]["repair_both"] == 1
