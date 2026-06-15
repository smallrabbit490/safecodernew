import json
from pathlib import Path

from translation_pipeline.architecture_experiment import (
    ArchitectureVariant,
    build_cross_language_method_matrix,
    build_cross_language_splits,
    build_evolved_skill,
    build_experiment_splits,
    build_experience_context,
    build_python_delta_memory,
    build_security_delta_cards,
    build_seed_lessons,
    classify_failure_type,
    evolution_gate,
    gate_lessons_with_dev_results,
    make_adaptive_repair_strategy,
    make_experience_provider,
    retrieve_lessons,
    summarize_architecture_results,
)
from translation_pipeline.prompts import build_repair_prompt


def _record(record_id, cwe="CWE-020", secure_cpp_ok=False, secure_go_ok=False, insecure_cpp_ok=False, insecure_go_ok=False):
    return {
        "ID": record_id,
        "Problem": f"{cwe} demo",
        "Entry_Point": "demo",
        "Secure Code": "def demo(x): return x",
        "Insecure Code": "def demo(x): return x",
        "Test": "def check(candidate): pass",
        "Secure Code C++ Test Result": {"ok": secure_cpp_ok},
        "Secure Code Go Test Result": {"ok": secure_go_ok},
        "Insecure Code C++ Behavior Result": {"ok": insecure_cpp_ok},
        "Insecure Code Go Behavior Result": {"ok": insecure_go_ok},
    }


def test_build_experiment_splits_are_disjoint_and_stable(tmp_path):
    records = [_record(f"CWE-{idx:03d}_case.py") for idx in range(10)]
    data_path = tmp_path / "records.json"
    data_path.write_text(json.dumps(records), encoding="utf-8")

    split = build_experiment_splits(data_path, train_size=3, test_size=4, seed=7)
    split_again = build_experiment_splits(data_path, train_size=3, test_size=4, seed=7)

    assert split.train_ids == split_again.train_ids
    assert split.test_ids == split_again.test_ids
    assert len(split.train_records) == 3
    assert len(split.test_records) == 4
    assert set(split.train_ids).isdisjoint(split.test_ids)


def test_retrieve_lessons_filters_by_language_mode_and_failure_type():
    lessons = [
        {
            "lesson_id": "go-secure-compile",
            "target_language": "go",
            "security_mode": "secure",
            "failure_type": "compile_error",
            "quality_score": 0.9,
            "text": "Remove unused imports.",
        },
        {
            "lesson_id": "cpp-secure-compile",
            "target_language": "cpp",
            "security_mode": "secure",
            "failure_type": "compile_error",
            "quality_score": 0.95,
            "text": "Include required headers.",
        },
        {
            "lesson_id": "go-insecure-security",
            "target_language": "go",
            "security_mode": "insecure",
            "failure_type": "security_mismatch",
            "quality_score": 0.99,
            "text": "Do not add validation.",
        },
    ]

    picked = retrieve_lessons(
        lessons,
        target_language="go",
        security_mode="secure",
        failure_type="compile_error",
        top_k=2,
    )

    assert [lesson["lesson_id"] for lesson in picked] == ["go-secure-compile"]


def test_summarize_architecture_results_counts_all_four_tracks():
    records = [
        _record("one", secure_cpp_ok=True, secure_go_ok=True, insecure_cpp_ok=True, insecure_go_ok=True),
        _record("two", secure_cpp_ok=True, secure_go_ok=False, insecure_cpp_ok=True, insecure_go_ok=False),
    ]

    summary = summarize_architecture_results("memory_with_negative", records)

    assert summary["architecture"] == "memory_with_negative"
    assert summary["records"] == 2
    assert summary["secure_cpp_ok"] == 2
    assert summary["secure_go_ok"] == 1
    assert summary["insecure_cpp_ok"] == 2
    assert summary["insecure_go_ok"] == 1
    assert summary["all_four_ok"] == 1
    assert summary["secure_rate"] == 0.75
    assert summary["insecure_rate"] == 0.75


def test_architecture_variants_define_comparable_conditions():
    variants = ArchitectureVariant.defaults()

    assert [variant.name for variant in variants] == [
        "baseline_repair",
        "memory_positive",
        "memory_positive_negative",
        "memory_skill_evolution",
    ]
    assert variants[0].use_memory is False
    assert variants[1].use_memory is True
    assert variants[2].use_negative_lessons is True
    assert variants[3].use_skill_evolution is True


def test_cross_language_splits_include_train_dev_test_and_are_disjoint(tmp_path):
    records = [_record(f"CWE-{idx:03d}_case.py") for idx in range(80)]
    data_path = tmp_path / "records.json"
    data_path.write_text(json.dumps(records), encoding="utf-8")

    split = build_cross_language_splits(
        data_path,
        train_size=30,
        dev_size=10,
        test_size=30,
        seed=20260606,
    )

    assert len(split.train_records) == 30
    assert len(split.dev_records) == 10
    assert len(split.test_records) == 30
    assert set(split.train_ids).isdisjoint(split.dev_ids)
    assert set(split.train_ids).isdisjoint(split.test_ids)
    assert set(split.dev_ids).isdisjoint(split.test_ids)


def test_full_architecture_variants_include_delta_memory_and_gate():
    variants = ArchitectureVariant.full_method_variants()

    assert [variant.name for variant in variants] == [
        "S0_direct_translation",
        "S1_feedback_repair",
        "S2_python_delta_transfer",
        "S3_adaptive_memory",
        "S4_contrastive_dual_track",
        "S5_evolution_gate",
    ]
    assert variants[0].max_repair_attempts == 0
    assert variants[2].use_python_delta is True
    assert variants[3].use_adaptive_memory is True
    assert variants[4].use_contrastive_dual_track is True
    assert variants[5].use_evolution_gate is True


def test_cross_language_method_matrix_defines_paper_grade_m0_to_m7():
    variants = build_cross_language_method_matrix()

    assert [variant.name for variant in variants] == [
        "M0_direct_translation",
        "M1_feedback_repair",
        "M2_python_delta_memory",
        "M3_failure_typed_repair",
        "M4_adaptive_retrieval",
        "M5_verifier_guided_evolution",
        "M6_skill_evolution",
        "M7_full_method",
    ]
    assert variants[0].max_repair_attempts == 0
    assert variants[1].use_memory is False
    assert variants[2].use_python_delta is True
    assert variants[3].use_failure_typed_repair is True
    assert variants[4].use_adaptive_memory is True
    assert variants[5].use_verifier_guided_evolution is True
    assert variants[6].use_skill_evolution is True
    assert variants[7].use_contrastive_dual_track is True


def test_python_delta_memory_is_built_only_from_python_train_records():
    train = [
        {
            **_record("CWE-078_train.py"),
            "Secure Code": "def run(x): return subprocess.check_output(['ls', x])",
            "Insecure Code": "def run(x): return os.popen('ls ' + x).read()",
            "Test": "def check(candidate): assert_raises(candidate, '; rm -rf /')",
        }
    ]

    memory = build_python_delta_memory(train)

    assert len(memory) >= 1
    first = memory[0]
    assert first["source"] == "python_train"
    assert first["memory_type"] == "delta"
    assert first["cwe"] == "CWE-078"
    assert "CWE-078_train.py" in first["evidence_ids"]
    assert "subprocess" in first["secure_pattern"] or "check_output" in first["secure_pattern"]
    assert "popen" in first["insecure_pattern"] or "concat" in first["insecure_pattern"].lower()


def test_security_delta_cards_are_structured_python_training_experience():
    train = [
        {
            **_record("CWE-078_train.py"),
            "Secure Code": "def run(x): return subprocess.check_output(['ls', x])",
            "Insecure Code": "def run(x): return os.popen('ls ' + x).read()",
            "Test": "def check(candidate): assert_raises(candidate, '; rm -rf /')",
        }
    ]

    cards = build_security_delta_cards(train)

    assert len(cards) == 1
    card = cards[0]
    assert card["source"] == "python_train"
    assert card["card_type"] == "security_delta_card"
    assert card["case_id"] == "CWE-078_train.py"
    assert card["cwe"] == "CWE-078"
    assert card["secure_intent"]
    assert card["insecure_intent"]
    assert "go" in card["target_language_risks"]
    assert "cpp" in card["target_language_risks"]
    assert card["allowed_modes"] == ["secure", "insecure"]


def test_evolution_gate_promotes_only_dev_supported_candidate_lessons():
    candidates = [
        {"lesson_id": "good", "status": "candidate", "supporting_case_ids": ["a"], "failure_count": 0},
        {"lesson_id": "bad", "status": "candidate", "supporting_case_ids": [], "failure_count": 2},
    ]
    dev_results = [
        {"ID": "a", "Secure Code C++ Test Result": {"ok": True}},
        {"ID": "b", "Secure Code C++ Test Result": {"ok": False}},
    ]

    promoted = evolution_gate(candidates, dev_results, min_support=1, max_failures=0)

    assert [lesson["lesson_id"] for lesson in promoted] == ["good"]
    assert promoted[0]["status"] == "verified"


def test_verifier_guided_gate_uses_go_cpp_dev_results_not_test_records():
    lessons = [
        {
            "lesson_id": "compile-go",
            "target_language": "go",
            "security_mode": "secure",
            "supporting_case_ids": ["train-a"],
            "status": "candidate",
        },
        {
            "lesson_id": "bad-insecure",
            "target_language": "go",
            "security_mode": "insecure",
            "supporting_case_ids": ["train-b"],
            "status": "candidate",
        },
    ]
    dev_results = [
        {
            **_record("dev-a"),
            "Secure Code Go Test Result": {"ok": True},
            "Insecure Code Go Behavior Result": {"ok": False, "details": {"error_type": "security_mismatch"}},
        }
    ]

    gated = gate_lessons_with_dev_results(lessons, dev_results, min_track_successes=1, max_track_failures=0)

    assert [lesson["lesson_id"] for lesson in gated] == ["compile-go"]
    assert gated[0]["status"] == "verified_by_dev"
    assert gated[0]["dev_support"] == 1


def test_failure_type_classifier_and_strategy_are_mode_specific():
    compile_result = {
        "stderr": "package main\nimported and not used: fmt\nsyntax error",
        "details": {"error_type": "runtime_error"},
    }
    security_result = {
        "stderr": "translation became safe and did not expose the vulnerability",
        "details": {"error_type": "security_mismatch"},
    }

    assert classify_failure_type(compile_result) == "compile_error"
    assert classify_failure_type(security_result) == "security_mismatch"

    insecure_strategy = make_adaptive_repair_strategy("go", "insecure", "security_mismatch")
    secure_strategy = make_adaptive_repair_strategy("cpp", "secure", "compile_error")

    assert "do not add validation" in insecure_strategy.lower()
    assert "unused imports" in make_adaptive_repair_strategy("go", "secure", "compile_error").lower()
    assert "c++17" in secure_strategy.lower()


def test_experience_context_is_injected_into_repair_prompt():
    context = build_experience_context(
        positive_lessons=[{"text": "Use double-quoted Go strings.", "lesson_id": "p1"}],
        negative_lessons=[{"text": "Do not add validation to insecure examples.", "lesson_id": "n1"}],
        evolved_skill="Keep insecure behavior while fixing compile errors.",
    )

    prompt = build_repair_prompt(
        problem="demo",
        entry_point="run",
        source_code="def run(x): return x",
        translated_code="package main",
        target_language="Go",
        failure_text="syntax error",
        mode="insecure",
        experience_context=context,
    )

    assert "Architecture experience context" in prompt
    assert "Use double-quoted Go strings." in prompt
    assert "Do not add validation to insecure examples." in prompt
    assert "Keep insecure behavior while fixing compile errors." in prompt


def test_seed_lessons_and_provider_use_training_records_only():
    train = [
        _record("CWE-078_train.py", secure_go_ok=True, insecure_go_ok=True),
        _record("CWE-020_train.py", secure_cpp_ok=True, insecure_cpp_ok=True),
    ]
    lessons = build_seed_lessons(train)
    evolved_skill = build_evolved_skill(train)
    provider = make_experience_provider(
        ArchitectureVariant(
            "memory_positive_negative",
            max_repair_attempts=1,
            use_memory=True,
            use_negative_lessons=True,
        ),
        lessons,
        evolved_skill,
    )

    context = provider(_record("CWE-999_test.py"), "go", "insecure", "repair")

    assert "CWE-999_test.py" not in context
    assert "CWE-078_train.py" in context
    assert "Do not add validation" in context or "preserve" in context.lower()


def test_baseline_variant_has_no_experience_provider():
    provider = make_experience_provider(
        ArchitectureVariant("baseline_repair", max_repair_attempts=1, use_memory=False),
        [],
        "skill",
    )

    assert provider is None
