# AGENTS.md

适用范围：本文件适用于整个 `safecodernew` 工作区。

## 项目概览

这个工作区是一个面向“安全感知代码生成与修复”的研究材料包。目前它不是 Git 仓库，请把它当作已经解压好的补充材料处理。修改时保持范围小、动作轻，避免顺手大规模格式化或清理数据。

主要内容分为三块：

- `DatasetAndMethod/CodeSecEval/`：CodeSecEval 基准数据，JSON 数组格式。
- `DatasetAndMethod/SecAwareCoder/`：安全感知代码生成、修复、本地 Python 测试执行，以及多语言执行/评测工具。
- `DatasetAndMethod/阅读文献/`：论文、研究要求等阅读材料。

除非任务和打包、归档或清理直接有关，否则忽略 `__MACOSX/`、`.DS_Store` 和根目录 zip 文件。

## 重要目录和文件

- `DatasetAndMethod/CodeSecEval/SecEvaBase.json`：基准数据文件，约 115 条记录。
- `DatasetAndMethod/CodeSecEval/SecEvalPlus.json`：扩展基准数据文件，约 140 条记录。
- `DatasetAndMethod/SecAwareCoder/main_streamsave.py`：批量运行入口，使用 Fire CLI。负责构建工作流、并发执行任务、按已有 `task_id` 续跑、写入 JSONL 结果、保存轨迹和 token 汇总。
- `DatasetAndMethod/SecAwareCoder/security_aware_code_generation_graph.py`：主 LangGraph 工作流定义。支持的 `security_mode` 包括 `single`、`all`、`repair` 和 `problem`。
- `DatasetAndMethod/SecAwareCoder/greedy_or_cot_graph.py`：较早的 greedy/COT 代码生成和翻译图辅助函数，目前没有接入 `main_streamsave.py`。
- `DatasetAndMethod/SecAwareCoder/prompts.py`：提示词模板。修改时必须保留 `.format(...)` 需要的变量名。
- `DatasetAndMethod/SecAwareCoder/tools_and_schemas.py`：Pydantic 结构化输出 schema，用于分析、安全风险、测试生成和修复测试。
- `DatasetAndMethod/SecAwareCoder/state.py`：LangGraph 节点使用的 TypedDict 状态契约。
- `DatasetAndMethod/SecAwareCoder/configuration.py`：可运行配置模型。环境变量可以按大写字段名覆盖配置字段。
- `DatasetAndMethod/SecAwareCoder/utils.py`：JSONL 读取、模型 API 选择、token 统计，以及 `ChatOpenAI` 构造。
- `DatasetAndMethod/SecAwareCoder/execution_engine/`：面向 Linux 的 Flask/Gunicorn 多语言沙箱执行服务。
- `DatasetAndMethod/SecAwareCoder/eval_scripts/`：通过 HTTP 调用执行引擎的 pass@k 和评测辅助脚本。

## 数据格式

`CodeSecEval` 里的 JSON 文件都是数组。字段名请保持原样：

- `ID`
- `Problem`
- `Entry_Point`
- `Insecure Code`
- `Secure Code`
- `Test`
- `Test-FP`
- `Test-SP`
- `update`，只出现在 `SecEvalPlus.json` 中

`main_streamsave.py` 会把每条记录映射成一个任务，常用字段包括 `problem_description`、`entry_point`、`original_tests`、`insecure_code` 和 `secure_code`。

不要随意重写、美化或标准化数据集内容。有些基准文本和测试片段本来就比较杂，改动它们可能影响实验可复现性。

## 环境和依赖

尽量使用 Python 3.10+。根目录没有统一的 requirements 文件，只安装当前任务真正需要的依赖。

核心工作流常用依赖：

```bash
pip install fire tqdm pydantic python-dotenv langgraph langchain-openai langchain-core tiktoken
```

评测脚本依赖：

```bash
pip install -r DatasetAndMethod/SecAwareCoder/eval_scripts/requirements.txt
pip install PyYAML
```

执行引擎额外依赖 Flask/Gunicorn，以及 Linux/系统层面的 seccomp、用户/组、编译器和运行时支持：

```bash
pip install flask flask-cors gunicorn gmpy2 PyYAML
```

`execution_engine` 会导入 `seccomp`。在 Linux 上它通常由系统包提供，不一定能直接通过 PyPI 安装。

模型凭据在 `utils.setup_openai_api()` 中按模型名前缀选择：

- `gpt*`：`OPENAI_API_KEY`，可选 `OPENAI_API_BASE`
- `glm*` 或 `codegeex*`：`ZHIPU_API_KEY`，可选 `ZHIPU_API_BASE`
- `claude*`：`ANTHROPIC_API_KEY`，可选 `ANTHROPIC_API_BASE`
- `deepseek*`：`DEEPSEEK_API_KEY`，可选 `DEEPSEEK_API_BASE`
- `moonshot*`：`MOONSHOT_API_KEY`，可选 `MOONSHOT_API_BASE`
- `qwen*`：`QWEN_API_KEY`，可选 `QWEN_API_BASE`
- `gemini*`：`GOOGLE_API_KEY`，可选 `GOOGLE_API_BASE`

图模块会调用 `load_dotenv()`，本地 `.env` 文件可用。不要提交、打印或粘贴真实密钥。

## 运行工作流

请从 `DatasetAndMethod/SecAwareCoder` 目录运行脚本，这样相对路径和 `Temp/` 行为才和代码一致：

```bash
cd DatasetAndMethod/SecAwareCoder
```

提供的 `run_*.sh` 默认数据路径可能不匹配这个已解压工作区。运行时请显式传入数据路径：

```bash
bash run_security_aware.sh --data_path ../CodeSecEval/SecEvaBase.json --security_mode all --num_workers 1
bash run_problem_aware.sh --data_path ../CodeSecEval/SecEvalPlus.json --num_workers 1
bash run_repair_mode.sh --data_path ../CodeSecEval/SecEvalPlus.json --num_workers 1
```

也可以直接用 Python CLI。直接运行前需要先创建 `Temp/`，或者用脚本自动创建。图执行器会在 `cwd=Temp` 下运行生成的 Python 测试代码。

```bash
mkdir -p Temp
python main_streamsave.py \
  --model_name qwen3-235b-a22b \
  --mode security_aware \
  --setting security_aware_agent \
  --security_mode all \
  --data_path ../CodeSecEval/SecEvaBase.json \
  --num_workers 1 \
  --sleep_interval 0 \
  --run_id smoke
```

生成结果通常位于：

```text
DatasetAndMethod/SecAwareCoder/data/security_aware/{model}/{setting}/{run_id}/{dataset}/
```

运行过程中可能出现这些附加产物：

- `logs/`
- `Temp/`
- `data/.../*.jsonl`
- adjacent `traj/` directories
- `*_token_summary.json`
- workflow diagrams such as `security_aware_workflow_all.png`

不要删除用户明确要求保留的实验输出。日常代码修改时，除非任务明确要求，否则不要把生成产物混进最终改动。

## 执行引擎

主安全感知图会直接在本地执行生成的 Python 片段，命令形如：

```python
subprocess.run(["python", temp_file], cwd=Temp, timeout=30)
```

这和 `execution_engine/` 是两套机制。

`execution_engine/` 是 Linux/Gunicorn 服务，提供：

- `POST /api/execute_code`
- `GET /api/all_runtimes`

`POST /api/execute_code` 接收 JSON 请求体，字段包括 `language`、`source_code`、`unittests`、可选的编译/执行覆盖参数、可选的 `limits`、`block_network`、`stop_on_first_fail` 和 `use_sanitizer`。

这个服务需要以下环境变量：

- `WORKER_CFG_DB`
- `RUN_GID`
- `RUN_UID`
- `NUM_WORKERS`
- `GUNICORN_PORT`
- `LOG_LEVEL`

`start_engine.sh` 会创建 Linux 用户/组并启动 Gunicorn。不要指望它能直接在普通 Windows shell 里跑起来。

## 评测脚本

`eval_scripts/eval_passk.py` 默认通过 `http://localhost:5000` 上的执行引擎计算 pass@k。它需要一个样本 JSONL 文件和一个 unittest 数据库。当前脚本会写出 metrics JSON，压缩后的评测输出写入块被注释掉了。

已知注意点：`eval_passk.py` 从父级 `utils.py` 导入 `stream_jsonl`，但当前 `utils.py` 只定义了 `load_jsonl`。依赖这个评测器之前，需要补上或修正这个辅助函数。

## 开发注意事项

- 搜索优先使用 `rg` / `rg --files`。
- 修改范围尽量小且局部。这个工作区包含研究代码和基准数据，避免大范围格式化、编码清理或数据集标准化。
- 许多注释存在历史编码问题。除非任务专门要求文档或编码清理，否则不要顺手改这些注释。
- 修改图节点时，保留 Pydantic schema 字段和 TypedDict 状态键。`main_streamsave.py` 里的 `normalize_result()` 依赖不同模式的输出键。
- 新增工作流模式时，要同步更新 `build_security_aware_workflow()`、`build_workflow_and_inputs()`、`normalize_result()`，以及所有需要暴露该模式的运行脚本或文档。
- 编辑 `prompts.py` 时，要确保每个 `.format(...)` 占位符都和调用它的节点保持一致。
- 把生成代码当作不可信输入处理。只在预期隔离环境里运行它，并始终考虑网络阻断和沙箱行为。
- 图代码会从数据集中读取 `original_tests`，但当前本地执行路径主要通过 `check(entry_point)` 运行生成的 `test_code`。不要先验地认为数据集里的 `Test` 一定被包含进去，最好先核实执行器行为。

## 临时文件和收尾

完成工作后要及时整理工作区。

- 如果为了排查、转换或批处理临时创建了脚本文件，任务结束后要删除这些临时脚本。
- 如果运行验证命令生成了 `__pycache__/`、临时测试文件、一次性日志或中间输出，确认不需要保留后再清理。
- 不要删除用户明确要求保留的实验数据、结果文件、轨迹目录或日志。
- 汇报最终结果前，先检查有没有自己留下的临时文件。对新手来说，干净的目录更容易继续使用。

## 沟通和汇报方式

向用户汇报时，请把用户当作刚接触这个项目的新手来解释。

- 先说结论：做了什么、是否完成、有没有风险。
- 再解释原因：用简单话说明为什么这么做。
- 提到命令或文件时，说明它们的作用，不要只扔路径和术语。
- 如果有报错或限制，说明“这意味着什么”和“下一步该怎么办”。
- 不要假设用户熟悉 LangGraph、pass@k、schema、JSONL、沙箱执行等概念；第一次提到时用一句话解释。

## 验证

Python 修改后如果只需要做语法检查，可以运行：

```bash
python -m compileall -q DatasetAndMethod/SecAwareCoder
```

`compileall` 会创建 `__pycache__/` 目录。验证结束后，如果这些目录只是临时产物，请清理掉。

如果要检查执行引擎配置解析，请在 `DatasetAndMethod/SecAwareCoder` 下运行：

```bash
python execution_engine/config.py
```

完整工作流运行需要模型 API 凭据，并且可能消耗 token。做烟雾测试时，尽量使用 `--num_workers 1`、小数据集切片，或者自定义 `--save_path`。

