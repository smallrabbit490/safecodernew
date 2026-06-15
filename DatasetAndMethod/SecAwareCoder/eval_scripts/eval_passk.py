import itertools
import json
import gzip
from typing import Iterable, Dict
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fire
import jsonlines
import numpy as np
import tqdm
import re

sys.path.extend(
    [Path(__file__).parent.parent, Path(__file__).parent.parent / "execution_engine"]
)
sys.path.append(str(Path(__file__).resolve().parent.parent))
# exit(0)
# sys.path.extend([
from utils import stream_jsonl
from api_comm import APICommunication
from exec_outcome import ExecOutcome
from yaml import safe_load

def sanitize(code: str, lang: str = None) -> str:
    code = code.strip()

    pattern = rf"```(?:{lang})?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, code)

    # 如果匹配到 markdown 代码块 → 抽取内容
    if match:
        return match.group(1).strip()

    # 否则 → 输入就是纯代码
    return code


def estimate_pass_at_k(
    num_samples: int | list[int] | np.ndarray,
    num_correct: list[int] | np.ndarray,
    k: int,
) -> np.ndarray:
    """
    Estimates pass@k of each problem and returns them in an array.
    """

    def estimator(n: int, c: int, k: int):
        """
        Calculates 1 - comb(n - c, k) / comb(n, k).
        """
        if n - c < k:
            return 1.0
        return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))

    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    return np.array(
        [estimator(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)]
    )

def pass_at_K_by_task(results, k):
    result_dict = defaultdict(list)
    for line in results:
        result_dict[line['task_id']].append(line['passed'])
    result = dict()
    for task_id in result_dict.keys():
        total = len(result_dict[task_id])
        correct = sum(result_dict[task_id])
        score = estimate_pass_at_k(total, [correct], k)[0]
        result[task_id] = score
    return result

def pass_at_K_by_difficulty(results, problems, k):
    """
    Calculate pass@k grouped by difficulty level
    """
    # Group results by difficulty
    difficulty_dict = defaultdict(list)
    for line in results:
        task_id = line['task_id']
        difficulty = problems[task_id]['difficulty']
        difficulty_dict[difficulty].append(line['passed'])
    
    # Calculate pass@k for each difficulty
    result = dict()
    for difficulty in difficulty_dict.keys():
        total = len(difficulty_dict[difficulty])
        correct = sum(difficulty_dict[difficulty])
        score = estimate_pass_at_k(total, [correct], k)[0]
        result[difficulty] = score
    return result

def pass_at_K_by_tag(results, problems_with_tags, k):
    """
    Calculate pass@k grouped by single tag
    A task with tags ["string", "dp"] contributes to both "string" and "dp".
    """
    tag_dict = defaultdict(list)

    for line in results:
        task_id = line['task_id']
        tags = problems_with_tags[task_id]['tags']
        for tag in tags:
            tag_dict[tag].append(line['passed'])

    result = dict()
    for tag, passed_list in tag_dict.items():
        total = len(passed_list)
        correct = sum(passed_list)
        score = estimate_pass_at_k(total, [correct], k)[0]
        result[tag] = score
    return result

# 新增：错误类型统计
def _normalize_counter(counter: dict[str, int]) -> dict[str, float]:
    total = sum(counter.values())
    if total == 0:
        return {k: 0.0 for k in counter.keys()}
    return {k: v / total for k, v in counter.items()}

def compute_error_stats_overall(sample_level_outcomes):
    """
    sample_level_outcomes: list[{"task_id": ..., "exec_outcome": ...}]
    返回: {outcome -> ratio}
    """
    c = Counter()
    for rec in sample_level_outcomes:
        c[rec["exec_outcome"]] += 1
    return _normalize_counter(c)

def compute_error_stats_by_difficulty(sample_level_outcomes, difficulties_db):
    """
    返回: {difficulty -> {outcome -> ratio}}
    """
    # difficulty -> Counter(outcome)
    diff_counters = defaultdict(Counter)
    for rec in sample_level_outcomes:
        task_id = rec["task_id"]
        diff = difficulties_db.get(task_id, {}).get("difficulty", "unknown")
        diff_counters[diff][rec["exec_outcome"]] += 1

    result = {}
    for diff, cnt in diff_counters.items():
        result[diff] = _normalize_counter(cnt)
    return result

def compute_error_stats_by_tag(sample_level_outcomes, tags_db):
    """
    返回: {tag -> {outcome -> ratio}}
    一个 task 可能属于多个 tag，因此一个 sample 会被计入多个 tag 的统计中。
    """
    tag_counters = defaultdict(Counter)
    for rec in sample_level_outcomes:
        task_id = rec["task_id"]
        tags = tags_db.get(task_id, {}).get("tags", [])
        for tag in tags:
            tag_counters[tag][rec["exec_outcome"]] += 1

    result = {}
    for tag, cnt in tag_counters.items():
        result[tag] = _normalize_counter(cnt)
    return result

# 新增：按 task 统计错误类型
def compute_error_stats_by_task(sample_level_outcomes):
    """
    返回: {task_id -> {outcome -> ratio}}
    一个 task 可能有多条 sample 结果（多次生成），这里统计该 task 内部各错误类型的占比。
    """
    task_counters = defaultdict(Counter)
    for rec in sample_level_outcomes:
        task_id = rec["task_id"]
        task_counters[task_id][rec["exec_outcome"]] += 1

    result = {}
    for task_id, cnt in task_counters.items():
        result[task_id] = _normalize_counter(cnt)
    return result

def evaluate_functional_correctness(
    sample_file: str,
    k: list[int] = [1, 10, 100],
    n_workers: int = 4,
    limits_by_lang: dict = {},
    compile_n_execute_args_by_lang: dict = {},
    eval_result_file: str | None = None,
    unittest_file: str = "unittest_db.json",
    execeval_url: str = "http://localhost:5000",
    block_network: bool = True,
    stop_on_first_fail: bool = True,
    use_sanitizer: bool = False,
    limit_mode: str = "fixed",
    fixed_cpu: int = 2,
    fixed_mem: int = 512,
):
    """
    Evaluates the functional correctness of generated samples, and writes
    results to f"{sample_file}_results.jsonl.gz"
    """
    
    unittest_db = {}
    task_limits = {}
    difficulties_db = {}
    tags_db = {}  # 新增：按 task 保存 tags

    for d in stream_jsonl(unittest_file):
        test = d["test_cases"]
        for t in test:
            out = t["output"]
            t["output"] = [out]
        task_id = d["task_id"]
        unittest_db[task_id] = test
        difficulties_db[task_id] = {"difficulty": d.get("difficulty", "unknown")}
        tags_db[task_id] = {"tags": d.get("tags", [])}  # 新增：tags 是 list

        task_limits[task_id] = {
            "cpu": int(d.get("time_limits", 2)),
            "_as": int(d.get("memory_limits", 512) * 1024**2)
        }

    lang_map = {
        "python": "Python 3",
        "cpp": "GNU C++17",
        "java": "Java 17",
        "javascript": "JavaScript",
        "csharp": "C# 10"
    }
    
    
    with APICommunication(execeval_url) as execeval:
        execute_code = execeval.execute_code
        supported_langs = {r["runtime_name"] for r in execeval.get_runtimes()}

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = []
            completion_id = Counter()
            n_samples = 0
            results = defaultdict(list)
            with jsonlines.open(sample_file) as sample_rp:
                for idx, sample in tqdm.tqdm(
                    enumerate(sample_rp), desc="Reading samples"
                ):
                    src_uid = sample["task_id"]
                    source_code = sample["code"]
                    
                    if "target_language" in sample.keys():
                        language = sample["target_language"]
                    else:
                        language = sample["language"]
                    source_code = sanitize(source_code, language.lower())
                    task_id = sample["task_id"]
                    lang =  lang_map[language.lower()]
                    if src_uid not in unittest_db:
                        continue
                    unittests = unittest_db[src_uid]
                    if len(unittests) == 0:
                        continue
                    if lang not in supported_langs:
                        print(f"Language {lang} not supported by execution engine, skipping...")
                        continue
                    
                    if limit_mode == "fixed":
                        # 所有task使用相同的限制
                        task_specific_limit = dict(limits_by_lang.get(lang, {}))
                        task_specific_limit.update({
                            "cpu": fixed_cpu,
                            "_as": fixed_mem * 1024 ** 2
                        })
                    else:  # limit_mode == "task"
                        task_specific_limit = dict(limits_by_lang.get(lang, {}))
                        if task_id in task_limits:
                            task_specific_limit.update(task_limits[task_id])
                    # print(f"Task {task_id} limits: {task_specific_limit}")
                    args = (
                        lang,
                        source_code,
                        unittests,
                        task_specific_limit,
                        block_network,
                        stop_on_first_fail,
                        use_sanitizer,
                        compile_n_execute_args_by_lang.get(lang, {}).get("compile_cmd"),
                        compile_n_execute_args_by_lang.get(lang, {}).get(
                            "compile_flags"
                        ),
                        compile_n_execute_args_by_lang.get(lang, {}).get("execute_cmd"),
                        compile_n_execute_args_by_lang.get(lang, {}).get(
                            "execute_flags"
                        ),
                        idx,
                        task_id,
                    )

                    future = executor.submit(execute_code, *args)
                    futures.append(future)
                    completion_id[task_id] += 1
                    n_samples += 1

            print("Running test suites...")
            # 新增：用于错误类型统计的列表
            sample_level_outcomes = []  # 每个元素: {"task_id": ..., "exec_outcome": ...}

            for idx, future in tqdm.tqdm(
                enumerate(as_completed(futures)),
                desc="Test running",
                total=len(futures),
            ):
                result = future.result()
                unittests, sample_idx, task_id = result
                if not isinstance(unittests, list) and "error" in unittests:
                    """
                    [TODO] log it
                    """
                    print("ERROR: ", unittests["error"])
                    continue
                results[task_id].append((sample_idx, unittests))

                # 统计该 sample 的最终 exec_outcome（和 combine_results 中逻辑一致）
                _exec_outcomes = [
                    r["exec_outcome"]
                    for r in unittests
                    if r["exec_outcome"] != ExecOutcome.PASSED.value
                ] + [ExecOutcome.PASSED.value]
                sample_level_outcomes.append(
                    {"task_id": task_id, "exec_outcome": _exec_outcomes[0]}
                )

    print("Calculate pass@k.")
    total, correct = [], []
    for result in results.values():
        result.sort()
        passed = [
            all(x["exec_outcome"] == ExecOutcome.PASSED.value for x in r[1])
            for r in result
        ]
        total.append(len(passed))
        correct.append(sum(passed))
    total = np.array(total)
    correct = np.array(correct)

    ks = k
    pass_at_k = {
        f"pass@{k}": estimate_pass_at_k(total, correct, k).mean()
        for k in ks
        if (total >= k).all()
    }

    # === 🔹 新增：每个task和difficulty的pass@k统计 ===
    print("Calculating per-task and per-difficulty pass@k...")

    # 将结果展开为flat list以便统计
    flat_results = []
    for task_id, records in results.items():
        for _, ut in records:
            passed = all(x["exec_outcome"] == ExecOutcome.PASSED.value for x in ut)
            flat_results.append({"task_id": task_id, "passed": passed})
    # 每个task的pass@k
    passk_by_task = {f"pass@{kk}": pass_at_K_by_task(flat_results, kk) for kk in ks}

    passk_by_diff = {f"pass@{kk}": pass_at_K_by_difficulty(flat_results, difficulties_db, kk) for kk in ks}

    passk_by_tag = {
        f"pass@{kk}": pass_at_K_by_tag(flat_results, tags_db, kk)
        for kk in ks
    }
    # 新增：错误类型统计（基于 sample_level_outcomes）
    error_stats_overall = compute_error_stats_overall(sample_level_outcomes)
    error_stats_by_difficulty = compute_error_stats_by_difficulty(sample_level_outcomes, difficulties_db)
    error_stats_by_tag = compute_error_stats_by_tag(sample_level_outcomes, tags_db)
    error_stats_by_task = compute_error_stats_by_task(sample_level_outcomes)  # 新增

    # Finally, save the results in one file:
    def combine_results():
        with jsonlines.open(sample_file) as sample_rp:
            cnt = 0
            for idx, sample in enumerate(sample_rp):
                cnt += 1
                # if sample["lang"] not in supported_langs:
                #     continue
                task_id = sample["task_id"]
                if len(results[task_id]) == 0:
                    continue
                if results[task_id][0][0] > idx:
                    continue
                result = results[task_id].pop(0)

                sample["unittests"] = result[1]
                _exec_outcomes = [
                    r["exec_outcome"]
                    for r in result[1]
                    if r["exec_outcome"] != ExecOutcome.PASSED.value
                ] + [ExecOutcome.PASSED.value]

                sample["exec_outcome"] = _exec_outcomes[0]
                yield sample
    
    # 汇总结果
    metrics = {
        "overall": pass_at_k,
        "by_difficulty": passk_by_diff,
        "by_tag": passk_by_tag,
        "error_stats": {  # 新增
            "overall": error_stats_overall,
            "by_difficulty": error_stats_by_difficulty,
            "by_tag": error_stats_by_tag,
            "by_task": error_stats_by_task,
        },
        "by_task": passk_by_task
    }

    # 保存指标

    if limit_mode == "fixed":
        subfolder_name = f"fixed_{fixed_cpu}s_{fixed_mem}MB"
    else:
        subfolder_name = "task_specific_limit"

    output_dir = Path(sample_file).parent
    base_name = Path(sample_file).stem
    output_dir = output_dir / subfolder_name
    output_dir.mkdir(parents=True, exist_ok=True) 

    if eval_result_file is None:
        eval_result_file = output_dir / f"{base_name}-evaluated.jsonl.gz"
        metrics_file = output_dir / f"{base_name}-metrics.json"
    with open(metrics_file, "w") as fp:
        json.dump(metrics, fp, indent=2)
    print(f"Saved metrics to {metrics_file}")

    # print(f"Writing compressed execution results to {eval_result_file}...")
    # with gzip.open(eval_result_file, "wt", encoding="utf-8") as gzfp:
    #     writer = jsonlines.Writer(gzfp)
    #     for result in tqdm.tqdm(combine_results(), total=n_samples):
    #         writer.write(result)
    #     writer.close()

    return pass_at_k


def entry_point(
    sample_file: str,
    k: str | list | tuple = "1,2,5,10",
    n_workers: int = 4,
    compile_n_execute_args_by_lang_cfg_file: str | None = None,
    limits_by_lang_cfg_file: str | None = None,
    unittest_file: str = "unittest_db.json",
    execeval_url: str = "http://localhost:5000",
    block_network: bool = True,
    stop_on_first_fail: bool = True,
    use_sanitizer: bool = False,
    limit_mode: str = "fixed",
    fixed_cpu: int = 2,
    fixed_mem: int = 512,
):
    """
    Evaluates the functional correctness of generated samples, and writes
    results to f"{sample_file}_results.jsonl.gz"
    """

    """
    [TODO]
    compile_n_execute_args_by_lang_cfg_file: str | None = None,
    limits_by_lang_cfg_file: str | None = None,

    assume yaml files and consider config.yaml for compile..args,
    and resource_limits.py for limits_by_lang
    """
    limits_by_lang, compile_n_execute_args_by_lang = None, {}
    if limits_by_lang_cfg_file is None:
        limits_by_lang_cfg_file = "limits_by_lang.yaml"
    if not os.path.exists(limits_by_lang_cfg_file):
        print(
            "Need resource limit defaults for all runtimes, provide the path to default 'limits_by_lang.yaml' or to the modified one."
        )
        exit(-1)
    with open(limits_by_lang_cfg_file) as limit_cfg_rp:
        limits_by_lang = safe_load(limit_cfg_rp)

    if compile_n_execute_args_by_lang_cfg_file is not None and os.path.exists(
        compile_n_execute_args_by_lang_cfg_file
    ):
        with open(
            compile_n_execute_args_by_lang_cfg_file
        ) as compile_n_execute_args_by_lang_rp:
            compile_n_execute_args_by_lang = safe_load(
                compile_n_execute_args_by_lang_rp
            )

    ks = list(map(int, k.split(","))) if isinstance(k, str) else list(k)
    results = evaluate_functional_correctness(
        sample_file,
        ks,
        n_workers,
        block_network=block_network,
        limits_by_lang=limits_by_lang,
        compile_n_execute_args_by_lang=compile_n_execute_args_by_lang,
        unittest_file=unittest_file,
        execeval_url=execeval_url,
        stop_on_first_fail=stop_on_first_fail,
        use_sanitizer=use_sanitizer,
        limit_mode = limit_mode,
        fixed_cpu = fixed_cpu,     
        fixed_mem = fixed_mem     
    )

    print(results)


def main():
    fire.Fire(entry_point)

sys.exit(main())
