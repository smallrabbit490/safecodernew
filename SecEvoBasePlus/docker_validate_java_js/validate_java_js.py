#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path, timeout: int) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-3000:],
            "stderr": proc.stderr[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr": "timeout",
        }


def strip_java_public(code: str) -> str:
    return re.sub(r"\bpublic\s+class\s+Solution\b", "class Solution", code)


def java_imports(*parts: str) -> str:
    imports = []
    seen = set()
    for part in parts:
        for line in part.splitlines():
            if line.strip().startswith("import ") and line.strip() not in seen:
                imports.append(line.strip())
                seen.add(line.strip())
    return "\n".join(imports)


def strip_java_imports(code: str) -> str:
    return "\n".join(line for line in code.splitlines() if not line.strip().startswith("import "))


def java_class_body(code: str) -> str:
    code = strip_java_public(strip_java_imports(code))
    marker = re.search(r"\bclass\s+Solution\b[^{]*\{", code)
    if not marker:
        return code
    start = marker.end()
    depth = 1
    idx = start
    while idx < len(code):
        if code[idx] == "{":
            depth += 1
        elif code[idx] == "}":
            depth -= 1
            if depth == 0:
                return code[start:idx]
        idx += 1
    return code[start:]


def find_matching_brace(text: str, open_idx: int) -> int:
    depth = 1
    idx = open_idx + 1
    in_string: str | None = None
    escaped = False
    while idx < len(text):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
        else:
            if ch in ("'", '"'):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return idx
        idx += 1
    return len(text)


def java_candidate_member_names(body: str) -> dict[str, set[str]]:
    methods = {
        m.group(1)
        for m in re.finditer(
            r"(?:^|[;\}\s])(?:public|private|protected)?\s*(?:static\s+)?(?:[\w<>\[\],?]+\s+)+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
            body,
        )
        if m.group(1)
        not in {
            "if",
            "for",
            "while",
            "switch",
            "catch",
            "new",
            "return",
            "throw",
        }
    }
    fields = {
        m.group(1)
        for m in re.finditer(
            r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?[\w<>\[\],?\s]+\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:=|;)",
            body,
            re.MULTILINE,
        )
    }
    classes = {
        m.group(1)
        for m in re.finditer(
            r"\b(?:public|private|protected)?\s*(?:static\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)\b",
            body,
        )
    }
    return {"methods": methods, "fields": fields, "classes": classes}


def remove_java_method(body: str, name: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:public|private|protected)?\s*(?:static\s+)?(?:[\w<>\[\],?]+\s+)+{re.escape(name)}\s*\([^)]*\)\s*(?:throws\s+[^\{{]+)?\{{",
        re.MULTILINE,
    )
    while True:
        match = pattern.search(body)
        if not match:
            return body
        open_idx = body.find("{", match.start(), match.end())
        end = find_matching_brace(body, open_idx)
        body = body[: match.start()] + "\n" + body[end + 1 :]


def remove_java_class(body: str, name: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+{re.escape(name)}\b[^\{{]*\{{",
        re.MULTILINE,
    )
    while True:
        match = pattern.search(body)
        if not match:
            return body
        open_idx = body.find("{", match.start(), match.end())
        end = find_matching_brace(body, open_idx)
        body = body[: match.start()] + "\n" + body[end + 1 :]


def remove_java_field(body: str, name: str) -> str:
    return re.sub(
        rf"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?[\w<>\[\],?\s]+\s+{re.escape(name)}\s*(?:=[^;]*)?;\s*\n?",
        "",
        body,
        flags=re.MULTILINE,
    )


def top_level_brace_depth(text: str, pos: int) -> int:
    depth = 0
    in_string: str | None = None
    escaped = False
    idx = 0
    while idx < pos:
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
        else:
            if ch in ("'", '"'):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        idx += 1
    return depth


def allow_top_level_java_checked_exceptions(body: str, only_check: bool = False) -> str:
    pattern = re.compile(
        r"(^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:[\w<>\[\],?]+\s+)+([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\))(?:\s*throws\s+([^{]+))?\s*\{",
        re.MULTILINE,
    )
    pieces = []
    last = 0
    for match in pattern.finditer(body):
        name = match.group(2)
        if top_level_brace_depth(body, match.start()) != 0:
            continue
        if only_check and name != "check":
            continue
        pieces.append(body[last : match.start()])
        header = match.group(1)
        existing_throws = match.group(3)
        if existing_throws and name != "check":
            pieces.append(match.group(0))
        else:
            pieces.append(header + " throws Exception {")
        last = match.end()
    pieces.append(body[last:])
    return "".join(pieces)


def java_test_body_without_candidate_duplicates(test_body: str, candidate_body: str) -> str:
    names = java_candidate_member_names(candidate_body)
    cleaned = test_body
    for class_name in sorted(names["classes"]):
        cleaned = remove_java_class(cleaned, class_name)
    for method_name in sorted(names["methods"]):
        cleaned = remove_java_method(cleaned, method_name)
    for field_name in sorted(names["fields"]):
        cleaned = remove_java_field(cleaned, field_name)
    return cleaned


def make_java_runner(code: str, test_code: str) -> str:
    imports = java_imports(code, test_code)
    solution_body = java_class_body(code)
    test_body = java_class_body(test_code)
    test_body = java_test_body_without_candidate_duplicates(test_body, solution_body)
    solution_body = allow_top_level_java_checked_exceptions(solution_body)
    test_body = allow_top_level_java_checked_exceptions(test_body, only_check=True)
    return (
        imports
        + "\n\nclass Solution {\n"
        + solution_body
        + "\n"
        + test_body
        + "\n}\n\n"
        + "public class Runner {\n"
        + "  public static void main(String[] args) throws Exception {\n"
        + "    Solution.check();\n"
        + "\n  }\n"
        + "}\n"
    )


def validate_java(code: str, test_code: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="secevo_java_") as tmp:
        cwd = Path(tmp)
        source = make_java_runner(code, test_code)
        (cwd / "Runner.java").write_text(source, encoding="utf-8")
        classpath = "/work/lib/*:."
        compile_result = run_cmd(["javac", "-cp", classpath, "Runner.java"], cwd, timeout)
        if not compile_result["ok"]:
            compile_result["phase"] = "compile"
            return compile_result
        result = run_cmd(["java", "-ea", "-cp", classpath, "Runner"], cwd, timeout)
        result["phase"] = "run"
        return result


def js_export_function_name(code: str) -> str | None:
    m = re.search(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", code)
    return m.group(1) if m else None


def make_js_runner(code: str, test_code: str, entry_point: str | None) -> str:
    fn = entry_point or js_export_function_name(code) or "candidate"
    test_code = re.sub(r"\bfunction\s+check\s*\(", "globalThis.__secevo_check = function(", test_code, count=1)
    return (
        "const vm = require('vm');\n"
        + "const Module = require('module');\n"
        + "const requireFn = Module.createRequire('/work/package.json');\n"
        + "const context = {console, Buffer, process, setTimeout, clearTimeout, URL, URLSearchParams};\n"
        + "context.globalThis = context;\n"
        + "context.global = context;\n"
        + "context.globalThis = context;\n"
        + "vm.createContext(context);\n"
        + "function runCommonJS(src) {\n"
        + "  const module = {exports: {}};\n"
        + "  const exports = module.exports;\n"
        + "  const wrapped = '(function(require, module, exports, global, globalThis) {\\n' + src + '\\n"
        + f"; if (typeof {fn} === \"function\") globalThis.__secevo_candidate = {fn};"
        + "\\n; return module.exports;\\n})';\n"
        + "  return vm.runInContext(wrapped, context)(requireFn, module, exports, context, context);\n"
        + "}\n"
        + "const codeExports = runCommonJS("
        + json.dumps(code)
        + ");\n"
        + "const testExports = runCommonJS("
        + json.dumps(test_code)
        + ");\n"
        + f"const candidate = context.__secevo_candidate || (codeExports && codeExports.{fn}) || (testExports && testExports.{fn});\n"
        + f"if (typeof candidate !== 'function') throw new Error('missing entry function: {fn}');\n"
        + "if (typeof context.__secevo_check !== 'function') throw new Error('missing check function');\n"
        + "(async () => { await context.__secevo_check(candidate); })().catch(err => { console.error(err && err.stack || err); process.exit(1); });\n"
    )


def validate_js(code: str, test_code: str, entry_point: str | None, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="secevo_js_") as tmp:
        cwd = Path(tmp)
        source = make_js_runner(code, test_code, entry_point)
        (cwd / "runner.js").write_text(source, encoding="utf-8")
        result = run_cmd(["node", "runner.js"], cwd, timeout)
        result["phase"] = "run"
        return result


def evaluate_row(row: dict, language: str, timeout: int) -> dict:
    secure_code = row.get("Secure Code") or ""
    insecure_code = row.get("Insecure Code") or ""
    function_test = row.get("Function Test") or row.get("Test-FP") or ""
    secure_test = row.get("Secure Test") or row.get("Test-SP") or ""
    entry_point = row.get("Entry_Point")

    if language == "java":
        runner = lambda code, test: validate_java(code, test, timeout)
    elif language == "js":
        runner = lambda code, test: validate_js(code, test, entry_point, timeout)
    else:
        raise ValueError(f"unsupported language: {language}")

    secure_function = runner(secure_code, function_test)
    secure_security = runner(secure_code, secure_test)
    insecure_function = runner(insecure_code, function_test)
    insecure_security = runner(insecure_code, secure_test)

    return {
        "id": row.get("ID"),
        "secure_ok": bool(secure_function["ok"] and secure_security["ok"]),
        "insecure_ok": bool(insecure_function["ok"] and not insecure_security["ok"]),
        "secure_function": secure_function,
        "secure_security": secure_security,
        "insecure_function": insecure_function,
        "insecure_security": insecure_security,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--language", choices=["java", "js"], required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    path = Path(args.dataset)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data[: args.limit]
    results = [evaluate_row(row, args.language, args.timeout) for row in rows]
    summary = {
        "dataset": str(path),
        "language": args.language,
        "total": len(results),
        "secure_ok": sum(1 for row in results if row["secure_ok"]),
        "insecure_ok": sum(1 for row in results if row["insecure_ok"]),
        "results": results,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
