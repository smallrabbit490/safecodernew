# baseline 三个压缩包分析与轻量测试报告

更新时间：2026-06-11  
工作目录：`D:\thecourceofdasi\safecodernew\baseline`

## 1. 结论先说

本次检查的三个压缩包分别对应三个评测/实验体系：

| 压缩包 | 对应内容 | 当前状态 |
| --- | --- | --- |
| `cweval.zip` | CWEval benchmark，评测多语言代码是否同时功能正确和安全 | 核心完整；生成入口和评测入口可启动；完整评测还需要 Go、Docker daemon 和语言依赖 |
| `SeCodePLT-main.zip` | SecCodePLT / SeCodePLT benchmark，含 Python instruct、Python autocomplete、Java patch 任务 | 核心源码和数据已补解；任务注册可导入；mini-swe-agent baseline 缺外部 `mini-swe-agent` 仓库；完整评测依赖 Docker |
| `codesecevalDatasetAndMethod.zip` | CodeSecEval 数据集和多个 baseline / agent 方法实现 | 核心数据、方法脚本、评分器可用；本地评分器已通过轻量测试；部分脚本有硬编码 API key，需要改成环境变量更适合复现 |

GLM 5.1 的 key 已做最轻量 API 测试：请求 `glm-5.1`、关闭 thinking、只要求回复 `OK`，返回正常，`usage_total=10`。这说明模型 API 通路是可用的。

## 2. 解压情况

解压后的真实项目根目录是双层结构：

| 包 | 实际项目根目录 |
| --- | --- |
| CodeSecEval | `baseline\codesecevalDatasetAndMethod\codesecevalDatasetAndMethod` |
| CWEval | `baseline\cweval\cweval` |
| SeCodePLT | `baseline\SeCodePLT-main\SeCodePLT-main` |

严格对照 zip 内容后：

- `cweval.zip`：5167 个文件全部存在。
- `codesecevalDatasetAndMethod.zip`：核心源码和数据存在，但随包的 `swe_venv` 虚拟环境仍有 5897 个文件未解出。这类文件是打包进去的 Python 环境，不建议直接依赖它复现实验。
- `SeCodePLT-main.zip`：一开始缺了 `virtue_code_eval` 和配置文件，已从 zip 中定向补解。剩余缺失集中在 `out/` 和 `logs/` 历史输出目录，不影响读取源码和数据。

简单理解：现在三个项目的“能分析、能配置、能继续跑实验”的核心内容都在；缺的主要是历史输出或不建议复用的虚拟环境。

## 3. AAAI 表格和三个包的关系

表格文件：`baseline\相关联aaai论文表格.xlsx`

表格有 52 行、14 列，主要是在比较三个 benchmark 上不同方法的结果：

| 表格区域 | 对应压缩包 | 含义 |
| --- | --- | --- |
| `CWEval（119）` | `cweval.zip` | 119 个 CWEval 任务，指标为 `func` 和 `func_sec` |
| `SecCodePLT（5900）` | `SeCodePLT-main.zip` | SecCodePLT 数据，包含 Python instruction generation、Python code completion、Java patch generation |
| `CodeSecEval（255）` | `codesecevalDatasetAndMethod.zip` | CodeSecEval 的 Base 115 条 + Plus 140 条，总计 255 条 |

表格里的方法行和代码位置大致对应如下：

| 表格方法 | CodeSecEval 包内位置 | SeCodePLT 包内位置 | CWEval 包内位置 |
| --- | --- | --- | --- |
| Greedy | `greedy_cot_eval\run_method.py --method greedy` | 需要用对应 adapter/prompt 复现 | `cweval\generate.py --ppt direct` 一类直接生成 |
| Greedy + Secure Prompt | `greedy_cot_eval\run_method.py --method greedy --secure` | 需要安全提示版本 prompt | 需要安全提示版本 prompt |
| Chain-of-Thought | `greedy_cot_eval\run_method.py --method cot` | 需要 CoT prompt | 需要 CoT prompt |
| Chain-of-Thought + Secure Prompt | `greedy_cot_eval\run_method.py --method cot --secure` | 需要 CoT + 安全提示 | 需要 CoT + 安全提示 |
| AutoSafeCoder | `AutoSafeCoder_official\` 和 `greedy_cot_eval\run_autosafe_official.py` | 表格有方法行，但当前 SeCodePLT 包里没有直接 AutoSafeCoder adapter | `third_party\AutoSafeCoder\` / `run_repro_min_on_cweval.py` 类 adapter |
| RA-Gen | `ragen_eval\`、`ragen_function_level\` | `ragen_function_level` 里有 SeCodePLT 相关脚本和 dummy 结果 | 表格有结果，但包内主要是 CodeSecEval/SeCodePLT 适配 |
| SWE-Agent | `SWE_agent_official\`、`swe_eval\` | `agent_adapters\mini_swe_agent\` 可看作 lightweight SWE-agent adapter | 需要额外 adapter |
| AgentCoder | `AgentCoder_official\`、`agentcoder_eval\run_agentcoder.py` | `agent_adapters\agentcoder\run_agentcoder_on_secodeplt.py` | 表格有结果，需要 CWEval adapter |
| SecAwareCoder | `SecAwareCoder\`、`secaware_eval\` | 当前 SeCodePLT 包里未看到完整 SecAwareCoder adapter | 可作为待适配方法 |

这里要注意：表格不是“一个压缩包只对应一种方法”。它是“多个 benchmark + 多个方法”的汇总表。

## 4. CodeSecEval 包分析

核心数据：

- `CodeSecEval\SecEvaBase.json`：115 条。
- `CodeSecEval\SecEvalPlus.json`：140 条。
- 两个文件合计 255 条，对应表格中的 `CodeSecEval（255）`。

主要运行方式：

| 方法 | 入口 | 输入 | 输出 |
| --- | --- | --- | --- |
| Greedy / CoT / Secure Prompt | `greedy_cot_eval\run_method.py` | `SecEvaBase.json` 或 `SecEvalPlus.json` | `greedy_cot_eval\results\{model}\{method}\{subset}\` |
| AutoSafeCoder | `greedy_cot_eval\run_autosafe_official.py` | CodeSecEval 任务 | 与其他方法相同结构的 generation / summary |
| AgentCoder | `agentcoder_eval\run_agentcoder.py` | CodeSecEval 任务 | `greedy_cot_eval\results\glm-5.1\agentcoder\...` |
| SWE-Agent | `swe_eval\` | 构造 SWE-agent instance，再从 patch 中还原 `main.py` 评分 | `swe_eval\out_base` / `out_plus` |
| SecAwareCoder | `SecAwareCoder\main_streamsave.py` | CodeSecEval JSON | `SecAwareCoder\data\security_aware\...` |
| 统一评分 | `greedy_cot_eval\harness.py` 和 `suites.py` | 生成代码 + `Test-FP` / `Test-SP` | `fun`、`sec`、`fun_sec` |

轻量测试结果：

| 测试项 | 结果 | 说明 |
| --- | --- | --- |
| 入口脚本语法检查 | 通过 | 对主要入口做了 `py_compile` |
| `greedy_cot_eval\run_method.py --help` | 通过 | 可显示参数 |
| 本地评分器测试 Base 第一条 Secure Code | 通过 | `fp=True, sp=True` |
| 本地评分器测试 Plus 第一条 Secure Code | 通过 | `fp=True, sp=True` |
| `SecAwareCoder\main_streamsave.py --help` | 通过 | 安装 LangGraph/LangChain 后可启动 |
| `CG_Configuration` 导入 | 通过 | 配置类实际叫 `CG_Configuration`，不是 `Configuration` |

包里已有的 GLM-5.1 历史结果摘要：

| 方法 | Base fun | Base fun_sec | Plus fun | Plus fun_sec |
| --- | ---: | ---: | ---: | ---: |
| greedy | 27.83 | 5.22 | 76.43 | 19.29 |
| greedy_sec | 23.48 | 3.48 | 75.00 | 25.00 |
| cot | 23.48 | 3.48 | 69.29 | 15.71 |
| cot_sec | 20.00 | 3.48 | 62.14 | 17.14 |
| autosafecoder | 20.87 | 4.35 | 50.00 | 20.71 |
| ragen | 20.00 | 3.48 | 62.14 | 15.71 |
| swe_agent | 8.70 | 2.61 | 40.00 | 8.57 |
| agentcoder | 26.09 | 4.35 | 78.57 | 23.57 |
| secawarecoder | 20.87 | 8.70 | 67.14 | 25.00 |

这些是包里已经存在的结果文件，不是本次重新全量跑出来的。

发现的问题：

- `greedy_cot_eval\run_method.py`、`agentcoder_eval\run_agentcoder.py` 等脚本里有硬编码 API key。复现实验时建议改成读取 `ZHIPU_API_KEY`。
- `SecAwareCoder\configuration.py` 里的配置类名是 `CG_Configuration` / `CT_Configuration`，不是普通的 `Configuration`。
- `SecEvalPlus` 的拆分测试在 `suites.py` 里有专门修复逻辑，不能直接假设 `Test-FP` / `Test-SP` 都干净。

## 5. CWEval 包分析

核心内容：

- `benchmark\core` 和 `benchmark\lang` 是任务数据。
- `cweval\generate.py` 负责调用 LLM 生成代码。
- `cweval\evaluate.py` 负责解析生成结果、编译/运行测试、统计 pass@k。
- `requirements\core.txt`、`requirements\ai.txt`、`requirements\dev.txt` 是依赖文件。

README 推荐流程：

```powershell
cd D:\thecourceofdasi\safecodernew\baseline\cweval\cweval
$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\baseline\cweval\cweval"
python cweval/generate.py gen --n 1 --temperature 0 --num_proc 1 --eval_path evals\your_run --model <model>
python cweval/evaluate.py pipeline --eval_path evals\your_run --num_proc 1 --docker False
python cweval/evaluate.py report_pass_at_k --eval_path evals\your_run
```

轻量测试结果：

| 测试项 | 结果 | 说明 |
| --- | --- | --- |
| `cweval\generate.py --help` | 通过 | 设置 `PYTHONPATH` 并安装 `litellm` 后可启动 |
| `cweval\evaluate.py --help` | 通过 | 安装 `pytest`、`docker` Python 包后可启动 |
| `cweval\commons.py --help` | 通过 | 公共工具入口可启动 |
| `compile_all_in --path benchmark/core/py` | 未通过 | 即使只给 Python 路径，脚本也会先检查 `go version`；当前系统没有 Go |
| Docker 检查 | 未通过 | `docker --version` 有，但 Docker daemon 连接失败 |

当前系统语言环境：

- C/C++：有 `gcc/g++ 15.2.0`。
- Node：有 `v22.15.1`。
- Java：有 `25.0.1`。
- Go：未找到 `go`。
- Docker：客户端存在，但 daemon 未连接。

包里已有历史结果：

- `evals\smoke\res_all.json`：一个 Python smoke 任务，`functional=True, secure=True, func_secure=True`。
- `evals\asc_smoke\res_all.json`：5 个核心语言 smoke 结果，其中 C/C++/Go/Python 通过，JS 功能未通过。
- `evals\glm51_*`：存在若干 GLM-5.1 历史输出和 `res_all.json`。

发现的问题：

- 完整 CWEval 最好在 Docker 镜像 `co1lin/cweval` 里跑，因为它需要多语言运行时和系统库。
- 当前 Windows 本地环境缺 Go，Docker daemon 也没有连上，所以不能说完整 CWEval 评测已在本机通过。

## 6. SeCodePLT 包分析

核心内容：

- `generate_dataset\`：用于生成、检查、转换 SeCodePLT 数据。
- `virtue_code_eval\`：任务注册、数据读取、指标计算核心包。初次解压缺失，已从 zip 中定向补出。
- `agent_adapters\mini_swe_agent\`：把 mini-swe-agent 接到 SeCodePLT 三类任务上。
- `agent_adapters\agentcoder\`：把 AgentCoder 接到 SeCodePLT 三类任务上。
- `executor_docker\`：FastAPI + Docker 执行服务，用于 Python / Java 测试。

数据和任务：

- `virtue_code_eval\data\safety\secodeplt\data.json`：SecCodePLT Python 安全任务数据。
- `virtue_code_eval\data\safety\juliet\juliet_autocomplete.json`：Juliet / Java 相关任务数据。
- 成功导入的任务注册中包含：
  - `secodeplt_python_instruct`
  - `secodeplt_python_autocomplete`
  - `unified_java_patch`
  - `secodeplt_juliet_autocomplete`
  - `juliet_patch`

README 推荐流程：

```powershell
cd D:\thecourceofdasi\safecodernew\baseline\SeCodePLT-main\SeCodePLT-main
pip install -r requirements.txt
pip install -e .
pip install -e ..\mini-swe-agent

python agent_adapters\mini_swe_agent\run_mini_swe_on_secodeplt.py ^
  --task all ^
  --sample-count 1 ^
  --output-dir out\mini_swe_agent_smoke ^
  --mock-reference
```

如果要跑 Java patch 或真实单元测试，还要启动 Docker executor：

```powershell
cd executor_docker
python -m server --host 127.0.0.1 --port 8666 --image secodeplt/juliet-java-env:latest
```

轻量测试结果：

| 测试项 | 结果 | 说明 |
| --- | --- | --- |
| `mini_swe_agent` adapter `--help` | 通过 | 脚本入口能显示参数 |
| `agentcoder` adapter `--help` | 通过 | 脚本入口能显示参数 |
| `virtue_code_eval` 任务注册导入 | 通过 | 补齐 `datasets`、`codebleu`、`pillow`、`sacrebleu` 后可导入 |
| `mini_swe_agent --mock-reference` 一条样本 | 未通过 | 缺外部包 `minisweagent`，README 要求 `pip install -e ../mini-swe-agent` |
| Docker executor | 未通过 | Docker daemon 当前不可用 |

发现的问题：

- SeCodePLT 的顶层 `virtue_code_eval.__init__` 会先导入全部 metrics。即使只跑安全单元测试，也要满足 BLEU、CodeBLEU、LLM judge 等无关指标依赖。
- `mini_swe_agent` adapter 依赖外部 `mini-swe-agent` 项目，当前三个压缩包里没有这个仓库。
- Java patch 任务需要 Docker 镜像和 Docker daemon；当前本地 Docker 客户端存在，但 daemon 未连接。

## 7. GLM 5.1 测试

本次做了最轻量 API 测试：

- 环境变量：`ZHIPU_API_KEY` 已存在。
- API base：默认 `https://open.bigmodel.cn/api/paas/v4`。
- 模型：`glm-5.1`。
- thinking：关闭，`extra_body={"thinking": {"type": "disabled"}}`。
- 请求内容：`只回复 OK`。

结果：

```text
ZHIPU_API_KEY set=True
content=OK
usage_total=10
```

这说明 GLM 5.1 的 key 和 OpenAI-compatible 调用方式是通的，可以用于后续最小样本生成。

## 8. 哪些 baseline 现在可以跑

| baseline / 功能 | 当前能否跑 | 原因 |
| --- | --- | --- |
| CodeSecEval Greedy / CoT / Secure Prompt | 可以轻量跑 | `run_method.py` 入口正常，评分器正常，GLM key 可用 |
| CodeSecEval 本地评分器 | 可以跑 | Base/Plus 第一条 Secure Code 已通过 |
| CodeSecEval SecAwareCoder | 可以启动 | `main_streamsave.py --help` 和配置导入通过；真实运行会消耗 API |
| CodeSecEval AgentCoder / AutoSafeCoder | 基本可跑，但建议先修配置 | 脚本存在；部分脚本硬编码 key，需要改环境变量 |
| CWEval 生成 | 可以启动 | `generate.py --help` 通过；真实生成需要模型参数 |
| CWEval 完整评测 | 暂不能完整跑 | 缺 Go，Docker daemon 未连接，多语言系统依赖不完整 |
| SeCodePLT 任务注册 | 可以导入 | 核心数据已补解，依赖已补到可导入 |
| SeCodePLT mini-swe-agent | 暂不能跑 | 缺外部 `minisweagent` 包/仓库 |
| SeCodePLT AgentCoder adapter | 可显示帮助，真实跑需进一步验证 | 入口正常；真实评测仍依赖 `virtue_code_eval`、Docker executor、API |
| SeCodePLT Java patch | 暂不能完整跑 | 需要 Docker executor 和 Java 镜像 |

## 9. 建议的下一步

1. 先把 CodeSecEval 的脚本中硬编码 API key 改为读取环境变量，避免复现时泄露或换 key 麻烦。
2. 如果要完整跑 CWEval，在 Docker Desktop 正常启动后，用官方镜像 `co1lin/cweval` 跑，或者在本地补 Go、Node 全局包、C 系统库。
3. 如果要完整跑 SeCodePLT，先准备外部 `mini-swe-agent` 仓库，并安装：

```powershell
pip install -e ..\mini-swe-agent
```

4. SeCodePLT 的 Java / Juliet 任务需要先解决 Docker daemon，再拉取或构建 `secodeplt/juliet-java-env`。
5. 后续写论文或对比实验时，建议把“历史结果”“轻量 smoke 结果”“正式全量结果”分三个目录保存，避免统计时混在一起。

## 10. 本次测试产物

本次轻量测试的虚拟环境、pip 缓存和日志都放在：

```text
baseline\baseline_test_work
```

里面包含多次 smoke 测试的 JSON 记录，例如：

- `smoke_results.json`
- `smoke_after_deps.json`
- `cweval_final_smoke.json`
- `final_smoke_round.json`
- `secodeplt_after_sacrebleu.json`

这些文件用于证明本次检查过程，不属于原始 baseline 数据。
