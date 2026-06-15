from pathlib import Path

import pytest

from translation_pipeline import paths
from translation_pipeline.code_extract import extract_code_block
from translation_pipeline.insecure_behavior import detect_insecure_validation_strategy
from translation_pipeline.insecure_behavior import validate_insecure_behavior
from translation_pipeline.paths import get_project_root, get_work_dir, ensure_work_dirs
from translation_pipeline.prompts import build_repair_prompt, build_translation_prompt
from translation_pipeline.run_translate_dataset import (
    add_translation_fields,
    is_translation_complete,
    is_validation_complete,
    mark_record_timeout,
    process_record,
    should_use_static_insecure_result,
    summarize_records,
    validate_translation,
    validate_existing_record,
)
from translation_pipeline.models import ValidationResult
from translation_pipeline.validators import command_exists
from translation_pipeline.validators import classify_validation_result
from translation_pipeline.validators import preflight_go_code
from translation_pipeline.validators import prune_unused_go_imports
from translation_pipeline.validators import run_command
from translation_pipeline.validators import validate_cpp_program
from translation_pipeline.validators import validate_go_program
from translation_pipeline.zhipu_client import ZhipuTranslationClient, load_zhipu_keys, make_cache_key


def test_translation_work_dir_is_inside_current_project():
    root = get_project_root()
    work_dir = get_work_dir()

    assert root == Path(__file__).resolve().parents[3]
    assert work_dir == root / "translation_work"


def test_ensure_work_dirs_creates_expected_layout(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)

    dirs = ensure_work_dirs()

    assert dirs["cache"] == work_dir / "cache"
    assert dirs["temp"] == work_dir / "temp"
    assert dirs["logs"] == work_dir / "logs"
    assert dirs["outputs"] == work_dir / "outputs"
    assert dirs["downloads"] == work_dir / "downloads"
    assert dirs["sandbox"] == work_dir / "sandbox"
    for path in dirs.values():
        assert isinstance(path, Path)
        assert path.exists()


def test_load_zhipu_keys_from_env_file(tmp_path):
    env_file = tmp_path / "zhipu.env"
    env_file.write_text("xyykey=abc\nlzhkey=def\n", encoding="utf-8")

    keys = load_zhipu_keys(env_file)

    assert keys == {"xyykey": "abc", "lzhkey": "def"}


def test_make_cache_key_is_stable_for_equivalent_payloads():
    first = make_cache_key({"model": "glm-4.7", "prompt": "hello"})
    second = make_cache_key({"prompt": "hello", "model": "glm-4.7"})

    assert first == second
    assert len(first) == 64


def test_extract_code_block_prefers_requested_language():
    response = "text\n```cpp\nint main(){return 0;}\n```\n```go\npackage main\n```"

    assert extract_code_block(response, "cpp") == "int main(){return 0;}"


def test_extract_code_block_rejects_empty_model_response():
    with pytest.raises(ValueError, match="empty"):
        extract_code_block(None, "go")


def test_insecure_prompt_says_not_to_fix_vulnerability():
    prompt = build_translation_prompt(
        problem="demo problem",
        entry_point="foo",
        source_code="def foo(x): return eval(x)",
        source_field="Insecure Code",
        target_language="Go",
    )

    assert "do not fix" in prompt.lower()
    assert "preserve the insecure behavior" in prompt.lower()


def test_secure_translation_prompt_preserves_security_controls():
    prompt = build_translation_prompt(
        problem="SQL lookup",
        entry_point="lookup",
        source_code="def lookup(db, name): return db.execute('SELECT * FROM users WHERE name=?', (name,))",
        source_field="Secure Code",
        target_language="Go",
    )

    lowered = prompt.lower()

    assert "secure reference" in lowered
    assert "preserve security" in lowered or "security controls" in lowered
    assert "do not reintroduce" in lowered
    assert "parameterized" in lowered or "validation" in lowered


def test_insecure_translation_prompt_preserves_specific_bad_behavior():
    prompt = build_translation_prompt(
        problem="SQL lookup",
        entry_point="lookup",
        source_code="def lookup(db, name): return db.execute('SELECT * FROM users WHERE name=' + name)",
        source_field="Insecure Code",
        target_language="C++",
    )

    lowered = prompt.lower()

    assert "intentionally insecure" in lowered
    assert "do not make it safe" in lowered
    assert "do not add" in lowered
    assert "parameterized" in lowered
    assert "preserve string concatenation" in lowered or "preserve the injection" in lowered


def test_insecure_repair_prompt_only_fixes_translation_not_vulnerability():
    prompt = build_repair_prompt(
        problem="SQL lookup",
        entry_point="lookup",
        source_code="def lookup(db, name): return db.execute('SELECT * FROM users WHERE name=' + name)",
        translated_code='func lookup(db DB, name string) { return db.Query("SELECT" + name) }',
        target_language="Go",
        failure_text="syntax error",
        mode="insecure",
    )

    lowered = prompt.lower()

    assert "only fix" in lowered
    assert "syntax" in lowered or "compile" in lowered
    assert "do not make the code safer" in lowered
    assert "do not add parameterized" in lowered or "do not replace" in lowered


def test_insecure_go_repair_prompt_asks_for_minimal_standard_library_program():
    prompt = build_repair_prompt(
        problem="SQL lookup",
        entry_point="lookup",
        source_code="def lookup(db, name): return db.execute('SELECT * FROM users WHERE name=' + name)",
        translated_code='import _ "github.com/go-sql-driver/mysql"\nfunc lookup(name string) string { return "" }',
        target_language="Go",
        failure_text="no required module provides package github.com/go-sql-driver/mysql",
        mode="insecure",
    )

    lowered = prompt.lower()

    assert "complete `package main`" in lowered
    assert "standard library" in lowered
    assert "third-party database drivers" in lowered
    assert "minimal" in lowered


def test_repair_prompt_includes_error_report_and_asks_for_reasonable_length():
    prompt = build_repair_prompt(
        problem="Parse input",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code="func parse(x string) string { return x }",
        target_language="Go",
        failure_text="stderr:\nmain.go:3:2: imported and not used\n\ndetails:\n{\"phase\":\"compile\"}",
        mode="secure",
    )

    lowered = prompt.lower()

    assert "error report" in lowered
    assert "imported and not used" in lowered
    assert "do not make the code longer" in lowered or "avoid making the code longer" in lowered
    assert "reasonable" in lowered


def test_secure_validation_prompt_checks_safe_handling_of_malicious_inputs():
    from translation_pipeline.prompts import build_validation_program_prompt

    prompt = build_validation_program_prompt(
        problem="path read",
        entry_point="read_file",
        source_code="def read_file(p): ...",
        translated_code="func readFile(p string) string { return p }",
        python_test="def check(candidate): pass",
        target_language="Go",
        mode="secure",
    )

    lowered = prompt.lower()

    assert "malicious" in lowered
    assert "safely handled" in lowered or "rejected" in lowered


def test_insecure_validation_prompt_treats_matching_bad_behavior_as_success():
    from translation_pipeline.prompts import build_validation_program_prompt

    prompt = build_validation_program_prompt(
        problem="command exec",
        entry_point="run",
        source_code="def run(x): os.system('cat ' + x)",
        translated_code='int run(std::string x) { return system(("cat " + x).c_str()); }',
        python_test="# Insecure Code failure analysis: command injection should be possible",
        target_language="C++",
        mode="insecure",
    )

    lowered = prompt.lower()

    assert "matching insecure behavior" in lowered or "matching bad behavior" in lowered
    assert "must not pass because it is safe" in lowered or "if the vulnerability is fixed" in lowered


def test_cpp_prompts_warn_against_recursive_variant_aliases():
    translation_prompt = build_translation_prompt(
        problem="parse json",
        entry_point="parse",
        source_code="def parse(x): return x",
        source_field="Secure Code",
        target_language="C++",
    )
    repair_prompt = build_repair_prompt(
        problem="parse json",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code="using JsonValue = std::variant<JsonValue>;",
        target_language="C++",
        failure_text="recursive alias compile error",
        mode="secure",
    )

    assert "recursive type aliases" in translation_prompt
    assert "recursive alias" in repair_prompt
    assert "struct/class wrapper" in repair_prompt


def test_prompts_reject_common_nonportable_dependencies():
    cpp_prompt = build_repair_prompt(
        problem="parse xml",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code="#include <libxml/parser.h>",
        target_language="C++",
        failure_text="fatal error: libxml/parser.h: No such file or directory",
        mode="secure",
    )
    go_prompt = build_repair_prompt(
        problem="parse yaml",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code='import "gopkg.in/yaml.v3"',
        target_language="Go",
        failure_text="no required module provides package gopkg.in/yaml.v3",
        mode="secure",
    )

    assert "C++17" in cpp_prompt
    assert "libxml" in cpp_prompt
    assert "Go standard library" in go_prompt
    assert "gopkg.in/yaml" in go_prompt


def test_repair_prompt_calls_out_go_module_and_cpp_windows_errors():
    go_prompt = build_repair_prompt(
        problem="parse yaml",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code='import "gopkg.in/yaml.v3"',
        target_language="Go",
        failure_text="no required module provides package gopkg.in/yaml.v3",
        mode="secure",
    )
    cpp_prompt = build_repair_prompt(
        problem="parse json",
        entry_point="parse",
        source_code="def parse(x): return x",
        translated_code="if (std::string(url).starts_with(\"https://\")) return true;",
        target_language="C++",
        failure_text="'std::string' has no member named 'starts_with'",
        mode="secure",
    )

    assert "remove unused imports" in go_prompt.lower()
    assert "go.mod" in go_prompt.lower()
    assert "c++17" in cpp_prompt.lower()
    assert "starts_with" in cpp_prompt.lower()
    assert "rfind" in cpp_prompt.lower()


def test_validation_prompt_for_go_rejects_python_style_monkeypatching():
    from translation_pipeline.prompts import build_validation_program_prompt

    prompt = build_validation_program_prompt(
        problem="demo",
        entry_point="write_file",
        source_code="def write_file(x): return x",
        translated_code="func writeFile(x string) string { return x }",
        python_test="def check(candidate): pass",
        target_language="Go",
        mode="secure",
    )

    lowered = prompt.lower()
    assert "do not monkeypatch" in lowered
    assert "cannot assign to imported functions" in lowered
    assert "no unused imports" in lowered


def test_cpp_validation_preflight_rejects_nonportable_headers_before_compile():
    result = validate_cpp_program(
        "#include <sys/wait.h>\nint main(){return 0;}\n",
        "cpp_preflight_header",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert result.details["error_type"] == "compile_error"
    assert "sys/wait.h" in result.stderr


def test_cpp_validation_preflight_rejects_socket_headers_before_link_errors():
    result = validate_cpp_program(
        "#include <sys/socket.h>\nint main(){return 0;}\n",
        "cpp_preflight_socket_header",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert result.details["error_type"] == "compile_error"
    assert "socket" in result.stderr.lower()


def test_cpp_validation_preflight_rejects_cpp20_string_methods_before_compile():
    result = validate_cpp_program(
        '#include <string>\nint main(){ return std::string("abc").ends_with("c") ? 0 : 1; }\n',
        "cpp_preflight_cpp20",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert "C++20" in result.stderr


def test_insecure_validation_prompt_requires_executable_matching_failure():
    from translation_pipeline.prompts import build_validation_program_prompt

    prompt = build_validation_program_prompt(
        problem="demo",
        entry_point="foo",
        source_code="def foo(x): return eval(x)",
        translated_code="int foo(){return 0;}",
        python_test="# Insecure Code failure analysis: should fail",
        target_language="C++",
        mode="insecure",
    )

    assert "fails in the same security-relevant way" in prompt
    assert "dangerous-looking tokens" in prompt
    assert "exit non-zero" in prompt


def test_command_exists_returns_boolean():
    assert isinstance(command_exists("python"), bool)


def test_cpp_validation_runs_inside_project_sandbox():
    result = validate_cpp_program(
        "#include <iostream>\nint main(){ std::cout << \"ok\"; return 0; }\n",
        "sandbox_path_check",
        "secure",
    )

    assert result.details["phase"] in {"compile", "run"}
    assert "translation_work" in result.details["sandbox_dir"]
    assert "sandbox" in result.details["sandbox_dir"]
    assert not result.details["sandbox_dir"].lower().startswith("c:\\")


def test_go_validation_uses_project_scoped_module_and_cache_dirs(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)

    recorded: dict[str, object] = {}

    calls = []

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        calls.append({"args": args, "cwd": cwd, "timeout": timeout, "phase": phase, "env": env})
        recorded["args"] = args
        recorded["cwd"] = cwd
        recorded["timeout"] = timeout
        recorded["phase"] = phase
        recorded["env"] = env

        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=True,
            language="go",
            mode="secure",
            stdout="ok",
            stderr="",
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "passed"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.command_exists", lambda command: True)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "go")

    result = validate_go_program(
        "package main\nfunc main() {}\n",
        "go_sandbox_check",
        "secure",
    )

    go_mod = (recorded["cwd"] / "go.mod").read_text(encoding="utf-8")
    env = recorded["env"]

    assert result.ok is True
    assert [call["phase"] for call in calls] == ["compile", "run"]
    assert calls[0]["args"][1] == "build"
    assert calls[1]["args"][1] == "run"
    assert "module" in go_mod
    assert "translation_work" in str(env["GOMODCACHE"])
    assert "translation_work" in str(env["GOCACHE"])
    assert env["GO111MODULE"] == "on"
    assert env["GOWORK"] == "off"
    assert env["GOPATH"].endswith("downloads\\go\\gopath") or env["GOPATH"].endswith("downloads/go/gopath")


def test_go_validation_downloads_third_party_modules_inside_project_cache(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)
    calls = []

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        calls.append({"args": args, "cwd": cwd, "timeout": timeout, "phase": phase, "env": env})
        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=True,
            language="command",
            mode="secure",
            stderr="",
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "passed"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "go")

    result = validate_go_program(
        'package main\nimport _ "github.com/go-sql-driver/mysql"\nfunc main() {}\n',
        "go_third_party_download",
        "secure",
    )

    assert result.ok is True
    assert [call["phase"] for call in calls] == ["dependency", "compile", "run"]
    assert calls[0]["args"][:2] == ["go", "get"]
    assert "github.com/go-sql-driver/mysql@latest" in calls[0]["args"]
    assert "translation_work" in str(calls[0]["env"]["GOMODCACHE"])
    assert "translation_work" in str(calls[0]["env"]["GOCACHE"])


def test_go_validation_docker_backend_uses_project_cache_and_network_isolation(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)
    monkeypatch.setenv("SAFECODER_GO_BACKEND", "docker")
    calls = []

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        calls.append({"args": args, "cwd": cwd, "timeout": timeout, "phase": phase, "env": env})
        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=True,
            language="command",
            mode="secure",
            stderr="",
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "passed"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "docker" if command == "docker" else "go")

    result = validate_go_program(
        'package main\nimport _ "github.com/go-sql-driver/mysql"\nfunc main() {}\n',
        "go_docker_backend",
        "insecure",
    )

    assert result.ok is True
    assert [call["phase"] for call in calls] == ["docker_check", "dependency", "compile", "run"]
    assert all(call["args"][0] == "docker" for call in calls)
    assert "--network" not in calls[1]["args"]
    assert "--network" in calls[2]["args"]
    network_index = calls[2]["args"].index("--network")
    assert calls[2]["args"][network_index + 1] == "none"
    assert "--network" in calls[3]["args"]
    run_network_index = calls[3]["args"].index("--network")
    assert calls[3]["args"][run_network_index + 1] == "none"
    assert calls[2]["timeout"] >= 180
    assert calls[3]["args"][-1] == "/work/main"
    joined_args = " ".join(calls[1]["args"])
    assert "translation_work" in joined_args
    assert "/go/pkg/mod" in joined_args
    assert "/root/.cache/go-build" in joined_args


def test_go_validation_docker_backend_reports_missing_docker_daemon(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)
    monkeypatch.setenv("SAFECODER_GO_BACKEND", "docker")

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=False,
            language="command",
            mode="secure",
            stderr="failed to connect to the docker API",
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "runtime_error"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "docker" if command == "docker" else "go")

    result = validate_go_program("package main\nfunc main() {}\n", "go_docker_missing", "secure")

    assert result.ok is False
    assert result.details["phase"] == "compile"
    assert result.details["docker_fallback"] is True
    assert "failed to connect to the docker API" in result.details["docker_error"]


def test_go_validation_stops_after_build_failure(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)
    calls = []

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        calls.append(phase)
        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=False,
            language="command",
            mode="secure",
            stderr='# command-line-arguments\n.\\main.go:5:2: "io" imported and not used',
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "compile_error"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "go")

    result = validate_go_program("package main\nimport \"io\"\nfunc main() {}\n", "go_build_fail", "secure")

    assert calls == ["compile"]
    assert result.ok is False
    assert result.details["phase"] == "compile"
    assert result.details["error_type"] == "compile_error"


def test_go_validation_stops_after_dependency_download_failure(tmp_path, monkeypatch):
    work_dir = tmp_path / "translation_work"
    monkeypatch.setattr(paths, "get_work_dir", lambda: work_dir)
    calls = []

    def fake_run_command(args, cwd, timeout=30, phase="run", env=None):
        calls.append(phase)
        from translation_pipeline.models import ValidationResult

        return ValidationResult(
            ok=False,
            language="command",
            mode="secure",
            stderr="go get failed",
            details={"phase": phase, "sandbox_dir": str(cwd), "error_type": "compile_error"},
        )

    monkeypatch.setattr("translation_pipeline.validators.run_command", fake_run_command)
    monkeypatch.setattr("translation_pipeline.validators.find_command", lambda command: "go")

    result = validate_go_program(
        'package main\nimport _ "github.com/example/missing"\nfunc main() {}\n',
        "go_dep_fail",
        "secure",
    )

    assert calls == ["dependency"]
    assert result.ok is False
    assert result.details["phase"] == "dependency"
    assert result.details["error_type"] == "compile_error"


def test_go_validation_preflight_rejects_multi_character_rune_literals():
    result = validate_go_program(
        "package main\nfunc main(){ _ = 'bad' }\n",
        "go_preflight_rune",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert result.details["error_type"] == "compile_error"
    assert "double-quoted strings" in result.stderr


def test_go_validation_preflight_rejects_imports_after_declarations():
    result = validate_go_program(
        "package main\nfunc helper() {}\nimport \"fmt\"\nfunc main(){fmt.Println(\"x\")}\n",
        "go_preflight_late_import",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert "imports after declarations" in result.stderr


def test_go_validation_preflight_rejects_package_function_assignment():
    result = validate_go_program(
        "package main\nimport \"os\"\nfunc main(){ os.Mkdir = nil }\n",
        "go_preflight_monkeypatch",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert "assignment to imported package functions" in result.stderr


def test_cpp_validation_preflight_rejects_duplicate_main_functions():
    result = validate_cpp_program(
        "int main(){return 0;}\nint main(){return 1;}\n",
        "cpp_preflight_duplicate_main",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert "exactly one int main" in result.stderr


def test_cpp_validation_preflight_rejects_assert_raises_without_definition():
    result = validate_cpp_program(
        "#include <iostream>\nint main(){ return assert_raises([](){}) ? 0 : 1; }\n",
        "cpp_preflight_assert_raises",
        "secure",
    )

    assert result.ok is False
    assert result.details["phase"] == "preflight"
    assert "assert_raises" in result.stderr


def test_validation_result_classification():
    compile_error = classify_validation_result(
        ok=False,
        phase="compile",
        returncode=1,
        stderr="main.cpp:1: error: nope",
    )
    timeout_error = classify_validation_result(
        ok=False,
        phase="run",
        returncode=None,
        stderr="command timed out",
    )

    assert compile_error == "compile_error"
    assert timeout_error == "timeout"


def test_validation_result_classification_treats_go_type_errors_as_compile_errors():
    result = classify_validation_result(
        ok=False,
        phase="run",
        returncode=1,
        stderr=".\\main.go:74:40: cannot use db (variable of type *mockDB) as *sql.DB value in argument",
    )

    assert result == "compile_error"


def test_validation_result_classification_treats_cpp_linker_socket_errors_as_compile_errors():
    result = classify_validation_result(
        ok=False,
        phase="run",
        returncode=1,
        stderr="undefined reference to `__imp_WSAStartup'",
    )

    assert result == "compile_error"


def test_validation_result_classification_handles_none_stderr():
    result = classify_validation_result(
        ok=False,
        phase="run",
        returncode=1,
        stderr=None,
    )

    assert result == "runtime_error"


def test_run_command_timeout_decodes_bytes_output(tmp_path, monkeypatch):
    def fake_subprocess_run(*args, **kwargs):
        import subprocess

        raise subprocess.TimeoutExpired(cmd=args[0], timeout=30, output=b"\xff", stderr=None)

    monkeypatch.setattr("translation_pipeline.validators.subprocess.run", fake_subprocess_run)

    result = run_command(["tool"], cwd=tmp_path, timeout=30, phase="run")

    assert result.ok is False
    assert result.stdout == "\ufffd"
    assert result.stderr == "command timed out"
    assert result.details["error_type"] == "timeout"


def test_run_command_decodes_subprocess_output_with_replacement(tmp_path, monkeypatch):
    recorded: dict[str, object] = {}

    def fake_subprocess_run(*args, **kwargs):
        recorded.update(kwargs)

        import subprocess

        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="bad: \ufffd")

    monkeypatch.setattr("translation_pipeline.validators.subprocess.run", fake_subprocess_run)

    result = run_command(["tool"], cwd=tmp_path, timeout=30, phase="run")

    assert recorded["encoding"] == "utf-8"
    assert recorded["errors"] == "replace"
    assert result.ok is False
    assert "bad:" in result.stderr


def test_add_translation_fields_keeps_original_fields():
    record = {"ID": "x", "Secure Code": "secure", "Insecure Code": "bad"}

    out = add_translation_fields(
        record,
        secure_cpp="cpp secure",
        secure_go="go secure",
        insecure_cpp="cpp bad",
        insecure_go="go bad",
        secure_cpp_result={"ok": True},
        secure_go_result={"ok": True},
        insecure_cpp_result={"ok": True},
        insecure_go_result={"ok": True},
    )

    assert out["Secure Code"] == "secure"
    assert out["Insecure Code"] == "bad"
    assert out["Secure Code C++"] == "cpp secure"
    assert out["Secure Code Go"] == "go secure"
    assert out["Insecure Code C++"] == "cpp bad"
    assert out["Insecure Code Go"] == "go bad"


def test_zhipu_client_default_timeout_is_180_seconds(tmp_path):
    env_file = tmp_path / "zhipu.env"
    env_file.write_text("lzhkey=fake-key\n", encoding="utf-8")

    client = ZhipuTranslationClient(env_path=env_file, cache_dir=tmp_path / "cache")

    assert client.request_timeout == 180
    assert client.max_tokens == 65536
    assert client.disable_thinking is True
    assert client.max_retries == 6


def test_process_record_skip_api_writes_complete_result_fields():
    record = {"ID": "x", "Secure Code": "secure", "Insecure Code": "bad"}

    out = process_record(
        record,
        model="glm-4.7",
        max_repair_attempts=0,
        skip_api=True,
        skip_validation=True,
        skip_secure_validation=False,
        skip_insecure_validation=False,
        request_timeout=180,
        max_tokens=65536,
    )

    assert "Secure Code C++ Test Result" in out
    assert "Secure Code Go Test Result" in out
    assert "Insecure Code C++ Behavior Result" in out
    assert "Insecure Code Go Behavior Result" in out
    assert out["Secure Code C++ Test Result"]["skipped"] is True


def test_detect_cwe_502_strategy_from_pickle_and_json_tests():
    record = {
        "ID": "CWE-502_demo.py",
        "Insecure Code": "import pickle\n\ndef f(x):\n    return pickle.loads(x)\n",
        "Test": "def check(candidate):\n    assert candidate(b'{\"a\":1}') == {'a': 1}\n",
    }

    strategy = detect_insecure_validation_strategy(record)

    assert strategy == "cwe-502-json-rejection"


def test_unmatched_insecure_behavior_is_marked_manual_required():
    result = validate_insecure_behavior(
        {"ID": "CWE-089_demo.py", "Insecure Code": "def f(x): return x"},
        "int f(int x) { return x; }",
        "cpp",
    )

    assert result.ok is False
    assert result.details["manual_required"] is True
    assert result.details["skipped"] is True


def test_static_insecure_sql_concat_rule_accepts_concat_translation():
    record = {
        "ID": "CWE-089_demo.py",
        "Insecure Code": "cur.execute(\"SELECT * FROM users WHERE username = '%s'\" % username)",
    }

    result = validate_insecure_behavior(
        record,
        'void show_user(std::string username) { cur.execute("SELECT * FROM users WHERE username = \'" + username + "\'"); }',
        "cpp",
    )

    assert result.ok is False
    assert result.details["strategy"] == "static-insecure-pattern"
    assert result.details["manual_required"] is True
    assert should_use_static_insecure_result(result) is False


def test_only_executable_insecure_results_bypass_generated_harness():
    executable = validate_insecure_behavior(
        {
            "ID": "CWE-502_demo.py",
            "Insecure Code": "import pickle\n\ndef getPickleData(x): return pickle.loads(x)",
            "Test": "def check(candidate):\n    assert candidate(b'{\"a\":1}') == {'a': 1}\n",
        },
        "std::string getPickleData(const std::string& x) { return x; }",
        "cpp",
    )
    manual = validate_insecure_behavior(
        {"ID": "CWE-595_demo.py", "Insecure Code": "def f(x): return x"},
        "int f(int x) { return x; }",
        "cpp",
    )

    assert should_use_static_insecure_result(executable) is True
    assert should_use_static_insecure_result(manual) is False


def test_static_insecure_crypto_rule_rejects_safe_translation():
    record = {
        "ID": "CWE-327_demo.py",
        "Insecure Code": "hashlib.md5(password).hexdigest()",
    }

    result = validate_insecure_behavior(
        record,
        "func hashPassword(password string) string { return bcryptHash(password) }",
        "go",
    )

    assert result.ok is False
    assert result.details["strategy"] == "static-insecure-pattern"
    assert result.details["manual_required"] is True


def test_known_cwe_context_covers_ssrf_records_for_executable_validation():
    result = validate_insecure_behavior(
        {
            "ID": "CWE-918_demo.py",
            "Insecure Code": "def fetch(url): return requests.get(url).text",
            "Problem": "Fetch a URL without validating the target host.",
        },
        "func fetch(url string) string { resp, _ := http.Get(url); return resp.Status }",
        "go",
    )

    assert result.ok is False
    assert result.details["strategy"] == "static-insecure-pattern"
    assert result.details["family"] == "open_redirect_and_ssrf"
    assert result.details["manual_required"] is True
    assert should_use_static_insecure_result(result) is False


def test_known_cwe_context_covers_xml_external_entity_records():
    result = validate_insecure_behavior(
        {
            "ID": "CWE-611_demo.py",
            "Insecure Code": "def parse(x): return etree.parse(x)",
            "Problem": "Parse XML with external entities enabled.",
        },
        "std::string parseXml(std::string xml) { return xml; }",
        "cpp",
    )

    assert result.ok is False
    assert result.details["strategy"] == "static-insecure-pattern"
    assert result.details["family"] == "xml_and_deserialization"
    assert result.details["manual_required"] is True


def test_validate_existing_record_can_skip_validation_without_retranslation():
    record = {
        "ID": "x",
        "Secure Code": "secure py",
        "Insecure Code": "bad py",
        "Secure Code C++": "secure cpp",
        "Secure Code Go": "secure go",
        "Insecure Code C++": "bad cpp",
        "Insecure Code Go": "bad go",
    }

    out = validate_existing_record(
        record,
        model="glm-4.7",
        max_repair_attempts=0,
        skip_validation=True,
        skip_secure_validation=False,
        skip_insecure_validation=False,
        request_timeout=180,
        max_tokens=65536,
    )

    assert out["Secure Code C++"] == "secure cpp"
    assert out["Insecure Code Go"] == "bad go"
    assert out["Secure Code C++ Test Result"]["skipped"] is True
    assert out["Insecure Code Go Behavior Result"]["skipped"] is True


def test_validate_translation_feeds_previous_validation_error_into_next_harness_prompt():
    class DummyClient:
        def __init__(self):
            self.prompts = []

        def translate(self, prompt):
            self.prompts.append(prompt)
            return "package main\nfunc main() {}\n"

    client = DummyClient()
    calls = []

    def validator(code, task_id, mode):
        calls.append(code)
        if len(calls) == 1:
            return ValidationResult(
                ok=False,
                language="go",
                mode=mode,
                stderr='# command-line-arguments\n.\\main.go:8:2: "net/url" imported and not used',
                details={"phase": "compile", "error_type": "compile_error"},
            )
        return ValidationResult(ok=True, language="go", mode=mode, details={"phase": "run"})

    _, result = validate_translation(
        client,
        {
            "ID": "x",
            "Problem": "demo",
            "Entry_Point": "foo",
            "Secure Code": "def foo(): pass",
            "Test": "def check(candidate): pass",
        },
        "Secure Code",
        "package main\nfunc main() {}\n",
        "Go",
        "go",
        validator,
        "secure",
        max_repair_attempts=1,
    )

    assert result["ok"] is True
    assert len(client.prompts) == 3
    second_harness_prompt = client.prompts[2]
    assert "Previous target validation failure" in second_harness_prompt
    assert "net/url" in second_harness_prompt


def test_validate_existing_record_does_not_rerun_successful_fields(monkeypatch):
    record = {
        "ID": "x",
        "Secure Code": "secure py",
        "Insecure Code": "bad py",
        "Secure Code C++": "secure cpp",
        "Secure Code Go": "secure go",
        "Insecure Code C++": "bad cpp",
        "Insecure Code Go": "bad go",
        "Secure Code C++ Test Result": {"ok": True},
        "Secure Code Go Test Result": {"ok": True},
        "Insecure Code C++ Behavior Result": {"ok": True},
        "Insecure Code Go Behavior Result": {"ok": True},
    }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    def fail_if_called(*args, **kwargs):
        raise AssertionError("already successful fields should not be revalidated")

    monkeypatch.setattr("translation_pipeline.run_translate_dataset.ZhipuTranslationClient", DummyClient)
    monkeypatch.setattr("translation_pipeline.run_translate_dataset.validate_translation", fail_if_called)
    monkeypatch.setattr("translation_pipeline.run_translate_dataset.validate_insecure_behavior", fail_if_called)
    monkeypatch.setattr("translation_pipeline.run_translate_dataset.validate_insecure_translation_with_execution", fail_if_called)

    out = validate_existing_record(
        record,
        model="glm-4.7",
        max_repair_attempts=2,
        skip_validation=False,
        skip_secure_validation=False,
        skip_insecure_validation=False,
        request_timeout=180,
        max_tokens=65536,
    )

    assert out["Secure Code C++"] == "secure cpp"
    assert out["Secure Code Go Test Result"]["ok"] is True
    assert out["Insecure Code C++ Behavior Result"]["ok"] is True


def test_summarize_records_counts_secure_and_insecure_results():
    records = [
        {
            "Secure Code C++ Test Result": {"ok": True},
            "Secure Code Go Test Result": {"ok": False},
            "Insecure Code C++ Behavior Result": {"ok": True},
            "Insecure Code Go Behavior Result": {"ok": True},
        }
    ]

    summary = summarize_records(records)

    assert summary["records"] == 1
    assert summary["secure_cpp_ok"] == 1
    assert summary["secure_go_ok"] == 0
    assert summary["insecure_cpp_ok"] == 1
    assert summary["insecure_go_ok"] == 1


def test_is_translation_complete_requires_all_four_translated_fields():
    incomplete = {
        "Secure Code C++": "x",
        "Secure Code Go": "",
        "Insecure Code C++": "x",
        "Insecure Code Go": "x",
    }
    complete = {
        "Secure Code C++": "x",
        "Secure Code Go": "x",
        "Insecure Code C++": "x",
        "Insecure Code Go": "x",
    }

    assert is_translation_complete(incomplete) is False
    assert is_translation_complete(complete) is True


def test_is_validation_complete_supports_resume_decisions():
    complete = {
        "Secure Code C++ Test Result": {"ok": True},
        "Secure Code Go Test Result": {"ok": True},
        "Insecure Code C++ Behavior Result": {"ok": True},
        "Insecure Code Go Behavior Result": {"ok": True},
    }
    pending = {
        "Secure Code C++ Test Result": {"pending": True},
        "Secure Code Go Test Result": {"ok": True},
    }

    assert is_validation_complete(complete, skip_secure=False, skip_insecure=False) is True
    assert is_validation_complete(pending, skip_secure=False, skip_insecure=True) is False
    assert is_validation_complete(pending, skip_secure=True, skip_insecure=True) is True


def test_manual_required_insecure_result_is_not_complete_when_validation_is_required():
    record = {
        "Secure Code C++ Test Result": {"ok": True},
        "Secure Code Go Test Result": {"ok": True},
        "Insecure Code C++ Behavior Result": {
            "ok": False,
            "skipped": True,
            "manual_required": True,
        },
        "Insecure Code Go Behavior Result": {"ok": True},
    }

    assert is_validation_complete(record, skip_secure=False, skip_insecure=False) is False


def test_validation_complete_requires_success_not_just_recorded_failure():
    failed = {
        "Secure Code C++ Test Result": {"ok": True},
        "Secure Code Go Test Result": {"ok": False, "stderr": "compile error"},
        "Insecure Code C++ Behavior Result": {"ok": True},
        "Insecure Code Go Behavior Result": {"ok": False, "error": "runtime error"},
    }

    assert is_validation_complete(failed, skip_secure=False, skip_insecure=False) is False


def test_secure_skip_result_is_not_complete_when_secure_validation_is_requested():
    record = {
        "Secure Code C++ Test Result": {"ok": False, "skipped": True, "reason": "old skip"},
        "Secure Code Go Test Result": {"ok": True},
        "Insecure Code C++ Behavior Result": {"ok": True},
        "Insecure Code Go Behavior Result": {"ok": True},
    }

    assert is_validation_complete(record, skip_secure=False, skip_insecure=False) is False
    assert is_validation_complete(record, skip_secure=True, skip_insecure=False) is True


def test_mark_record_timeout_marks_requested_result_fields():
    record = {"ID": "x", "Secure Code": "secure", "Insecure Code": "bad"}

    out = mark_record_timeout(
        record,
        timeout_seconds=600,
        skip_secure_validation=False,
        skip_insecure_validation=True,
    )

    assert out["Secure Code C++ Test Result"]["details"]["error_type"] == "timeout"
    assert out["Secure Code Go Test Result"]["details"]["timeout"] == 600
    assert out["Insecure Code C++ Behavior Result"]["pending"] is True
    assert "timed out" in out["Translation Pipeline Error"]


def test_prune_unused_go_imports_removes_unused_standard_imports():
    code = """package main

import (
    "bytes"
    "fmt"
    alias "strings"
    _ "database/sql"
)

func main() {
    fmt.Println(alias.TrimSpace(" x "))
}
"""

    pruned = prune_unused_go_imports(code)

    assert '"bytes"' not in pruned
    assert '"fmt"' in pruned
    assert 'alias "strings"' in pruned
    assert '_ "database/sql"' in pruned


def test_go_preflight_allows_single_quotes_inside_double_quoted_strings():
    code = '''package main

import "fmt"

func main() {
    query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", "alice")
    fmt.Println(query)
}
'''

    assert preflight_go_code(code, "sql_injection_example", "insecure") is None


def test_go_preflight_allows_single_quotes_inside_comments():
    code = '''package main

func main() {
    // insecure returns 'executed' and FAILS
}
'''

    assert preflight_go_code(code, "comment_example", "insecure") is None
