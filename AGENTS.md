# AGENTS.md

适用范围：本文件适用于整个 `D:\thecourceofdasi\safecodernew` 工作区。

## 当前定稿方向

本项目当前主线已经调整为：

```text
自进化经验驱动的多语言安全代码生成
```

也就是说，最终论文和实验要突出安全代码生成、经验学习、自动修复和跨语言迁移。原因是软件工程方向，尤其是 ICSE，更希望任务能体现实际应用价值，这条主线更容易说明它能帮助开发者写出更安全的代码。

后续工作请围绕下面这条主线展开：

```text
从安全相关数据中学习经验
  -> 形成可复用的安全生成规则
  -> 用门控机制筛选有效经验
  -> 生成 Python / C++ / Go / Java / JS 安全代码
  -> 在目标语言环境中验证功能正确性和安全性
  -> 根据失败案例继续更新经验库
```

## 核心任务边界

最终实验只评估 Secure 安全代码生成。

保留不安全代码相关数据的唯一用途是：

- 在训练阶段辅助理解“漏洞代码”和“修复后代码”之间的安全差异。
- 帮助经验抽取模块总结安全规则。
- 作为负例来源，帮助模型知道哪些写法应该避免。

不要再把不安全代码作为最终评估轨道。

后续文档、表格和汇报中，不再设置任何以“不安全代码是否符合预期失败”为核心的最终评估表。正式汇报和新增实验以 Secure-only 安全代码生成为准。

## 完整数据集

当前完整数据集目录：

```text
SecEvoBasePlus/
  Base/
    Python_Base.json
    Cpp_Base.json
    Go_Base.json
    Java_Base.json
    JS_Base.json
  Plus/
    Python_Plus.json
    Cpp_Plus.json
    Go_Plus.json
    Java_Plus.json
    JS_Plus.json
```

数据规模：

| 子集 | Python | C++ | Go | Java | JS |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

常见字段包括：

- `ID`
- `Problem`
- `Entry_Point`
- `Secure Code`
- `Test`
- `Test-FP`
- `Test-SP`
- `Source Secure Code Python`
- `Secure Code Test Result`

部分数据文件里仍然可能保留不安全代码字段，例如 `Insecure Code` 或 `Source Insecure Code Python`。这些字段只作为训练阶段的负例/差异分析材料，不作为最终评估结果展示。

不要随意重写、美化或标准化 `SecEvoBasePlus/` 里的 JSON。它们是当前实验的定稿数据集。

## Docker 环境固定

当前固定使用下面三个 Docker 镜像验证 Python、C++、Go 的 Secure 安全代码：

| 用途 | 镜像 |
|---|---|
| Python 验证 | `safecoder-python-validator:local` |
| C++ 验证 | `safecoder-cpp-validator:local` |
| Go 验证 | `golang:1.22` |

对应 Dockerfile：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator/Dockerfile
DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator/Dockerfile
```

如果本机没有本地镜像，可以重新构建：

```powershell
docker build -t safecoder-python-validator:local DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator
docker build -t safecoder-cpp-validator:local DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator
docker pull golang:1.22
```

运行验证前固定这些环境变量：

```powershell
$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder"
$env:SAFECODER_PYTHON_DOCKER_IMAGE="safecoder-python-validator:local"
$env:SAFECODER_CPP_DOCKER_IMAGE="safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE="golang:1.22"
```

当前 Java 和 JS 数据集已经整理进 `SecEvoBasePlus/`，但本工作区目前没有已经确认可复现的 Java/JS Docker 镜像和验证脚本。等同学补齐镜像后，再把 Java/JS 的固定镜像名和验证命令补进本文件。

## Docker VHDX 空间控制

Docker Desktop 在 Windows 上会把 Linux 镜像、容器层、volume 和临时写入放进一个动态虚拟硬盘文件：

```text
D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx
```

这个文件的特点是：写入时会自动变大，但删除容器、删除临时文件以后，Windows 看到的 VHDX 文件通常不会自动变小。也就是说，Docker 里面的空间“空了”，不代表 D 盘马上能拿回来。

本项目曾出现过一次典型问题：

```text
Docker 实际可见资源：
Images: 11.47GB
Containers: 0B
Volumes: 840KB
Build Cache: 0B

但 Windows 侧：
docker_data.vhdx: 229.98GB
D 盘剩余空间: 约 6.8GB
```

根因是大量 Docker 验证任务反复启动短生命周期容器，容器运行和编译过程写入过 Docker 数据盘。容器虽然通过 `--rm` 删除了，但 VHDX 写过的块没有自动归还给 Windows。最终通过下面流程恢复：

```text
1. 在 docker-desktop WSL 内执行 fstrim。
2. 关闭 Docker Desktop 和 WSL。
3. 用管理员权限执行 diskpart compact vdisk。
4. 再检查 VHDX 和 D 盘空间。
```

当时关键证据：

```text
fstrim: /mnt/docker-desktop-disk trimmed 507.7 GiB
docker_data.vhdx: 229.98GB -> 14.87GB
D 盘剩余空间: 约 6.8GB -> 约 221.89GB
```

当前正常参考值：

```text
docker_data.vhdx: 约 14.87GB
D 盘剩余空间: 约 221.87GB
```

### 抑制 VHDX 膨胀的固定规则

所有 Docker 验证容器都要尽量避免把临时文件写进容器自己的可写层。当前代码已经固定：

- Docker run 增加 `--tmpfs /tmp:rw,nosuid,nodev,size=128m`。
- 容器内临时目录固定到挂载目录，例如 `/work/.tmp` 或 `/src/.tmp`。
- Python / C++ / Go 验证容器都设置 `TMPDIR`、`TEMP`、`TMP`。
- Go 验证额外设置 `GOTMPDIR=/work/.tmp`。
- Go 的 `GOMODCACHE` 和 `GOCACHE` 挂载到项目下的 `translation_work/cache/go/`，不要留在容器内部。
- `golang:1.22` 不要默认覆盖 entrypoint；否则容器内 `PATH` 可能丢失 `/usr/local/go/bin`，导致 `go: not found`。
- 验证输出必须限长写入，避免无限 stdout/stderr 把 JSONL 或日志撑爆。

对应代码位置：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/validators.py
DatasetAndMethod/SecAwareCoder/translation_pipeline/python_validator.py
DatasetAndMethod/SecAwareCoder/translation_pipeline/quality_metrics.py
```

### VHDX 检查命令

运行大规模实验前后都要记录：

```powershell
Get-Item "D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx" |
  Select-Object FullName,@{n='SizeGB';e={[math]::Round($_.Length/1GB,3)}},LastWriteTime

Get-PSDrive D |
  Select-Object Name,@{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}},@{n='UsedGB';e={[math]::Round($_.Used/1GB,2)}}

docker system df -v
```

如果 Docker 实际资源只有十几 GB，但 VHDX 明显大很多，说明是动态虚拟硬盘没有回收空闲块。

### VHDX 回收流程

先执行 trim：

```powershell
wsl -d docker-desktop -- sh -lc "fstrim -av 2>&1 || true"
```

再以管理员权限运行本项目固定脚本：

```powershell
Start-Process powershell -Verb RunAs -ArgumentList `
  "-NoProfile","-ExecutionPolicy","Bypass","-File",`
  "D:\thecourceofdasi\safecodernew\translation_work\admin_tools\compact_docker_vhdx_admin.ps1"
```

注意：

- 这个脚本会关闭 Docker Desktop 和 WSL。
- 必须点 UAC 管理员确认，否则不能压缩 VHDX。
- 不要直接删除 `docker_data.vhdx`。直接删除等于清空 Docker Desktop 的镜像、容器、volume 和内部状态，除非明确要重置 Docker。
- 需要保留实验镜像时，不要随便执行 `docker image prune -a`。

## Secure 全量 Docker 重验命令

只重验当前已经固定 Docker 环境的 Python、C++、Go Secure 代码：

```powershell
$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder"
$env:SAFECODER_PYTHON_DOCKER_IMAGE="safecoder-python-validator:local"
$env:SAFECODER_CPP_DOCKER_IMAGE="safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE="golang:1.22"

python -m translation_pipeline.run_full_docker_revalidation `
  --dataset-root SecEvoBasePlus `
  --output-root translation_work\docker_revalidation\latest_secure_check `
  --subsets Base Plus `
  --languages python cpp go `
  --tracks secure `
  --max-workers 3 `
  --timeout 90
```

如果只想重跑失败项，可以使用：

```powershell
python -m translation_pipeline.run_full_docker_revalidation `
  --dataset-root SecEvoBasePlus `
  --output-root translation_work\docker_revalidation\retry_secure_failures `
  --subsets Base Plus `
  --languages python cpp go `
  --tracks secure `
  --max-workers 3 `
  --timeout 90 `
  --only-failures-from translation_work\docker_revalidation\latest_secure_check\failures.json
```

## 当前 Secure 验证结果

Python、C++、Go 三种语言已经完成 Docker Secure 验证。

历史完整报告位置：

```text
translation_work/docker_revalidation/current_best_after_remaining_fixes/docker_revalidation_report.md
```

当前只作为 Secure 结果引用：

| 子集 | 语言 | Secure |
|---|---|---:|
| Base | Python | 115/115 |
| Base | C++ | 115/115 |
| Base | Go | 115/115 |
| Plus | Python | 140/140 |
| Plus | C++ | 140/140 |
| Plus | Go | 140/140 |

总计：

```text
765 / 765 Secure passed
failures: 0
```

这里的含义很简单：这些安全代码已经在对应 Docker 环境中通过功能测试和安全测试。

## 验证脚本位置

当前 Docker 重验入口：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/run_full_docker_revalidation.py
```

Python Docker 验证逻辑：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/python_validator.py
```

C++/Go Docker 参数和通用命令执行逻辑：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/validators.py
```

PRCS 生产就绪质量指标逻辑：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/quality_metrics.py
```

PRCS 指标生成入口：

```text
DatasetAndMethod/SecAwareCoder/translation_pipeline/run_quality_metrics.py
```

相关回归测试：

```text
baseline/experience_transfer_experiment/test_coset_eagle_experiment.py
```

## 自进化经验安全代码生成

当前我们自己的方法可以叫：

```text
Ours / SCT-Agent
```

也可以在论文方法部分描述为：

```text
Self-Evolving Security Experience Transfer for Secure Code Generation
```

给新手解释，可以这样说：

> 我们不是只让大模型一次性生成代码，而是让它先从已有安全样本中学习经验。每次生成后都运行测试，失败就分析失败原因，再把有普遍价值的经验写回记忆库。下一轮生成时，模型会带着这些通过验证的经验继续生成安全代码。

### 经验从哪里来

经验来源分三类：

| 来源 | 作用 |
|---|---|
| CodeSecEval / SecEvoBasePlus | 提供安全代码任务、测试和部分安全差异信息 |
| SeCodePLT | 提供漏洞代码和补丁代码，用来学习常见安全修复模式 |
| 运行失败记录 | 提供真实失败信号，用来让模型总结新规则 |

注意：漏洞代码或不安全代码只用于训练阶段分析，不作为最终评估对象。

### 经验如何进入模型

经验会被整理成规则，每条规则通常包含：

| 字段 | 含义 |
|---|---|
| `rule_name` | 规则名称 |
| `principle` | 这条经验的核心原则 |
| `when_to_apply` | 什么时候应该使用 |
| `implementation_hint` | 代码实现时怎么做 |
| `avoid` | 应该避免的危险写法 |
| `evidence` | 这条规则来自什么失败模式或经验来源 |

这些规则会被写入 prompt 的 memory 区，让模型生成代码时参考。

### 自进化流程

当前固定流程：

```text
1. Initial Memory
   从训练样本和历史经验中形成初始安全规则。

2. Secure Generation
   用当前 memory 生成安全代码。

3. Docker Validation
   在目标语言 Docker 环境中运行功能测试和安全测试。

4. Failure Analysis
   对失败样本提取清洗后的错误信号，不泄露隐藏测试。

5. Rule Evolution
   调用大模型总结新的泛化规则。

6. Micro Gate
   先用小规模代表性任务检查单条候选规则是否真的有帮助。

7. Promotion
   只有通过门控的规则才能进入长期 memory。

8. Best Skill
   固化当前最稳定的一版经验规则，用于正式实验。
```

### 当前固定方法产物

当前自进化/门控方法的固定样本在：

```text
baseline/experience_transfer_experiment/final_gated_sample/
```

当前固定规则入口：

```text
baseline/experience_transfer_experiment/final_gated_sample/gate_best_rules.json
```

我们方法 prompt 的单独摘录文档：

```text
baseline/experience_transfer_experiment/ours_method_prompt_extract.md
```

不要把候选规则、被拒规则、旧实验过程当成最终方法。正式汇报时以 `final_gated_sample` 里的门控成功版本为准。

## Baseline 配置

baseline 相关主脚本：

```text
baseline/experience_transfer_experiment/run_actual_5_python_methods.py
baseline/experience_transfer_experiment/run_coset_eagle_experiment.py
baseline/experience_transfer_experiment/run_language_method_matrix.py
```

当前固定比较方法一共是 10 个：9 个 baseline 加 1 个 ours。

| 方法 | 分组 | 当前最终评估任务 |
|---|---|---|
| Greedy | traditional | Secure |
| Greedy + Secure Prompt | traditional | Secure |
| Chain-of-Thought | traditional | Secure |
| Chain-of-Thought + Secure Prompt | traditional | Secure |
| AutoSafeCoder | agent | Secure |
| RA-Gen | agent | Secure |
| SWE-Agent | agent | Secure |
| AgentCoder | agent | Secure |
| SecAwareCoder | agent | Secure |
| Ours / SCT-Agent | ours | Secure |

所有方法最终都按安全代码生成方法比较。

## Baseline 运行设置

模型默认使用：

```text
glm-5.1
```

API 读取方式：

```powershell
$env:ZHIPU_API_KEY="<your key>"
$env:ZHIPU_API_BASE="https://open.bigmodel.cn/api/paas/v4"
```

脚本里固定关闭思考模式：

```python
extra_body={"thinking": {"type": "disabled"}}
```

推荐轻量 baseline 运行命令：

```powershell
cd baseline\experience_transfer_experiment

python run_actual_5_python_methods.py `
  --n 5 `
  --model glm-5.1 `
  --max_tokens 4096 `
  --temperature 0 `
  --retries 3 `
  --out_name actual_5_python_9_methods
```

输出位置：

```text
baseline/experience_transfer_experiment/out/actual_5_python_9_methods/
  actual_5_python_9_methods_report.md
  actual_5_python_9_methods_summary.json
  actual_5_python_9_methods_tasks.json
  generations/
  methods/
```

如果脚本历史输出里包含不安全相关列，整理正式结果时不要把这些列作为主结果展示。

## Ours / SCT-Agent 主流程运行设置

Ours 的经验迁移主脚本是：

```text
baseline/experience_transfer_experiment/run_coset_eagle_experiment.py
```

默认参数：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `se_train_size` | 200 | 从 SeCodePLT 中取多少条经验样本 |
| `code_train_size` | 30 | 从 CodeSecEval / SecEvoBasePlus 中取多少条经验样本 |
| `test_size` | 30 | 测试任务数量 |
| `repair_iters` | 3 | 每条任务最多修复轮数 |
| `workers` | 3 | 并发数 |
| `max_tokens` | 4096 | 单次生成最大 token |
| `model` | `glm-5.1` | 默认模型 |

Secure 主流程命令：

```powershell
cd baseline\experience_transfer_experiment

python run_coset_eagle_experiment.py `
  --model glm-5.1 `
  --workers 3 `
  --max_tokens 4096 `
  --se_train_size 200 `
  --code_train_size 30 `
  --test_size 30 `
  --repair_iters 3 `
  --out_name coset_eagle_final_gated `
  --variants no_memory,script_codeseceval,secodeplt_memory,coset_eagle_final_gated
```

当前正式主线使用 Secure-only 流程。

## 需要填写的表格

最终文档里建议至少放四张表：方法总表、Secure 细分表、运行设置表、多语言数据集表。

### 方法总表

方法总表用于展示 9 个 baseline + ours 的核心比较。

| 列名 | 怎么填 |
|---|---|
| Method | 方法名，例如 `Greedy`、`AutoSafeCoder`、`Ours / SCT-Agent` |
| Group | `traditional`、`agent`、`ours` |
| Secure Functional | Secure 功能通过数量和比例，例如 `4/5 (80.0%)` |
| Secure Security | Secure 安全测试通过数量和比例 |
| Secure Func+Sec | Secure 同时通过功能和安全的数量和比例 |
| All-Lang Secure | 同一任务在多语言 Secure 生成中是否都成功 |
| Repair Success | 失败后通过修复变成功的数量和比例 |
| Gen Errors | 生成阶段 API 报错或空结果数量 |
| Avg Tokens | 平均 token 消耗 |
| Avg Time | 平均运行时间 |

### 固定主指标

当前主指标固定为：

| 指标 | 含义 |
|---|---|
| `secure_functional` | 安全代码是否通过功能测试 |
| `secure_security` | 安全代码是否通过安全测试 |
| `secure_func_sec` | 安全代码是否同时功能正确且安全 |
| `all_language_secure` | 同一任务在多种目标语言中是否都安全生成成功 |
| `repair_success` | 初次失败后，经过修复是否成功 |
| `evolution_gain` | 使用自进化经验后，相比无经验或基础经验提升多少 |
| `prcs` | 可生产就绪综合得分，综合功能、安全、静态警告、复杂度和代码膨胀 |
| `eqs` | 工程质量拆分分数，只看静态警告、复杂度和代码膨胀，不包含功能/安全通过项 |
| `static_warning_density` | 每行代码的加权静态警告密度 |
| `loc_growth_ratio` | 安全代码相对指定基准代码的代码行增长比例；没有有效基准时不计算 |
| `complexity` | 轻量圈复杂度估计，用于衡量代码可维护性 |
| `generation_error_rate` | API 报错、空输出或无法解析代码的比例 |
| `cost` | token、时间和重试次数等成本 |

### PRCS 生产就绪质量指标

PRCS 全称是 `Production-Ready Composite Score`，用于补充 ICSE 更关心的工程实用性问题：代码不只要通过测试，还要尽量低警告、低复杂度、不过度膨胀。

当前公式：

```text
PRCS = 0.35 * Func
     + 0.35 * Sec
     + 0.15 * (1 - WarningPenalty)
     + 0.10 * (1 - ComplexityPenalty)
     + 0.05 * (1 - GrowthPenalty)
```

因为 `Func` 和 `Sec` 合计占 0.70，PRCS 在所有安全代码都通过测试时会偏高。为避免掩盖工程质量差异，同时新增 EQS：

```text
EQS = 0.50 * (1 - WarningPenalty)
    + 0.30 * (1 - ComplexityPenalty)
    + 0.20 * (1 - GrowthPenalty)
```

EQS 不包含功能和安全通过项，只衡量工程质量。正式结果建议同时展示：

- `Func/Sec`：说明代码是否可用、是否安全。
- `PRCS`：说明综合生产就绪度。
- `EQS`：单独说明可维护性、静态风险和代码膨胀，不让 Func/Sec 把分数抬太高。

各项含义：

| 项 | 含义 |
|---|---|
| `Func` | Secure 功能测试是否通过，当前来自 Docker Secure 验证结果 |
| `Sec` | Secure 安全测试是否通过，当前来自 Docker Secure 验证结果 |
| `WarningPenalty` | 静态警告惩罚，优先来自语言 SAST 工具；工具不可用时使用轻量 fallback |
| `ComplexityPenalty` | 复杂度惩罚，来自 Python AST 或 C++/Go 关键词规则估计 |
| `GrowthPenalty` | 代码膨胀惩罚，必须来自明确的生成代码和参考代码对；没有有效参考代码时不计算 |

代码膨胀基准不能混用。当前固定三种模式：

| 模式 | 什么时候用 | 含义 |
|---|---|---|
| `none` | 默认用于 `SecEvoBasePlus` 定稿数据集评分 | 不计算代码膨胀，只看静态警告和复杂度 |
| `python_source` | 只用于“Python 源任务直接生成目标语言代码”的实验输出 | 目标语言生成代码和 Python 源 Secure 代码比较 |
| `same_language_reference` | 只用于每条生成结果带有同语言参考代码时 | C++ 对 C++、Go 对 Go、Python 对 Python，不统一匹配到 Python |

特别注意：`SecEvoBasePlus` 里的 C++/Go/Java/JS 文件目前没有单独的“同语言原始参考代码”字段，只有当前定稿的 `Secure Code` 和部分 `Source Secure Code Python`。因此对 `SecEvoBasePlus` 做整体质量评分时，默认使用 `--growth-baseline none`。不要把 C++/Go/Java/JS 的 LoC 统一拿去和 Python 源代码比较，否则代码膨胀指标会混入语言天然冗长差异。

当前实现已经从“轻量规则为主”升级为“工具优先、轻量 fallback”：

| 语言 | 当前优先工具 | 当前状态 | fallback |
|---|---|---|---|
| Python | Bandit | 本机可用，已实测能输出 JSON finding | Python AST/正则轻量规则 |
| Go | Docker `golang:1.22` 的 `go vet`；Docker `securego/gosec` | Docker Go 已可用，`gosec` 已实测能输出 G114/G104 | Go 轻量规则 |
| Java | 计划接 CodeQL Java 或 SpotBugs + Find Security Bugs；可选 Semgrep | 本机有 JDK，但 CodeQL 不在 PATH，Semgrep Docker 当前拉取/启动超时 | Java 轻量规则 |
| C++ | 计划接 clang-tidy / Clang Static Analyzer / Infer | 尚未固定工具链 | C++ 轻量规则 |

工具模式说明：

- `--sast-mode tools`：优先调用语言 SAST 工具，失败或不可用时 fallback 到轻量规则。
- `--sast-mode lightweight`：强制只用轻量规则，适合快速 smoke。
- `--growth-baseline none`：不计算代码膨胀，适合当前 `SecEvoBasePlus` 定稿数据集。
- `--growth-baseline python_source`：只适合直接生成结果，也就是同一条 Python 源任务生成 Python/C++/Go 等目标代码后进行比较。
- `--growth-baseline same_language_reference`：只适合结果行里有同语言参考代码时使用。
- PRCS 公式不依赖具体工具，只读取统一格式的 warning 列表。

当前工具模式已实测：

```text
Python Bandit: available
Go docker go vet: available
Go docker gosec: available
Java CodeQL: not available on PATH
Java Semgrep Docker: timed out during image startup/pull
```

当前生成 PRCS/EQS 全量表的命令：

```powershell
$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder"

python -m translation_pipeline.run_quality_metrics `
  --dataset-root SecEvoBasePlus `
  --validation-results translation_work\docker_revalidation\current_best_after_remaining_fixes\results.jsonl `
  --output-root translation_work\quality_metrics\prcs_current_best_growth_none `
  --subsets Base Plus `
  --languages python cpp go `
  --sast-mode lightweight `
  --growth-baseline none
```

当前输出：

```text
translation_work/quality_metrics/prcs_current_best_growth_none/quality_rows.json
translation_work/quality_metrics/prcs_current_best_growth_none/quality_summary.json
translation_work/quality_metrics/prcs_current_best_growth_none/quality_metrics_report.md
```

工具模式 smoke 测试命令：

```powershell
$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder"

python -m translation_pipeline.run_quality_metrics `
  --dataset-root SecEvoBasePlus `
  --validation-results translation_work\docker_revalidation\current_best_after_remaining_fixes\results.jsonl `
  --output-root translation_work\quality_metrics\sast_tools_smoke_py_go_java `
  --subsets Base `
  --languages python go java `
  --limit 2 `
  --sast-mode tools `
  --growth-baseline none
```

工具模式 smoke 输出：

```text
translation_work/quality_metrics/sast_tools_smoke_py_go_java/quality_rows.json
translation_work/quality_metrics/sast_tools_smoke_py_go_java/quality_summary.json
translation_work/quality_metrics/sast_tools_smoke_py_go_java/quality_metrics_report.md
```

### Secure 细分表

这张表用于向老师解释安全代码生成具体发生了什么。

| Method | Secure Functional | Secure Security | Secure Func+Sec | Repair Success | Notes |
|---|---:|---:|---:|---:|---|

填写规则：

- 所有方法都填 Secure 三列。
- Ours 在 Notes 里说明使用 gated experience / self-evolution memory。
- 不添加旧双轨实验中的对照轨道指标。

### 运行设置表

这张表用于保证实验可复现。

| 项目 | 当前设置 |
|---|---|
| Model | `glm-5.1` |
| API Base | `https://open.bigmodel.cn/api/paas/v4` |
| Thinking | disabled |
| Temperature | `0` |
| Max Tokens | `4096` |
| Retries | `3` |
| Workers | `3` |
| Repair Iters | `3` |
| Baseline Sample Size | 轻量测试为 `5`，正式实验需写实际值 |
| Ours Test Size | 默认 `30` |
| SeCodePLT Train Size | `200` |
| CodeSecEval / SecEvoBasePlus Train Size | `30` |
| Output Root | `baseline/experience_transfer_experiment/out/` |

### 多语言数据集表

这张表用于说明当前完整 SecEvoBasePlus 数据集规模。

| 子集 | Python | C++ | Go | Java | JS |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

### Docker Secure 验证结果表

这张表用于说明 Python、C++、Go 三种语言的当前 Secure 验证状态。

| 子集 | 语言 | Secure |
|---|---|---:|
| Base | Python | 115/115 |
| Base | C++ | 115/115 |
| Base | Go | 115/115 |
| Plus | Python | 140/140 |
| Plus | C++ | 140/140 |
| Plus | Go | 140/140 |

Java 和 JS 目前只写数据集数量，不写 Docker 通过率，直到同学补齐镜像并完成验证。

### PRCS/EQS 当前结果表

这张表用于展示安全代码生成结果的工程质量。

当前表使用 `--sast-mode lightweight` 和 `--growth-baseline none`。也就是说，这里不展示代码膨胀，因为当前 `SecEvoBasePlus` 没有同语言原始参考代码。旧版曾把 C++/Go 统一对比到 Python 源代码，那个口径已经废弃。

| 子集 | 语言 | Total | Func+Sec | Avg PRCS | Avg EQS | Avg LoC | Avg Growth | Avg Complexity | Warnings |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | Python | 115 | 115 | 0.9895 | 0.9621 | 22.7565 | N/A | 8.1130 | 2 |
| Base | C++ | 115 | 115 | 0.9647 | 0.8736 | 62.6870 | N/A | 18.8348 | 8 |
| Base | Go | 115 | 115 | 0.9536 | 0.8202 | 40.6696 | N/A | 10.4783 | 186 |
| Plus | Python | 140 | 140 | 0.9753 | 0.9113 | 19.5214 | N/A | 8.6214 | 5 |
| Plus | C++ | 140 | 140 | 0.9672 | 0.8819 | 64.7643 | N/A | 21.3643 | 23 |
| Plus | Go | 140 | 140 | 0.9757 | 0.9091 | 45.7643 | N/A | 11.4929 | 80 |

总体结果：

```text
Total: 765
Func+Sec: 765 / 765
Avg PRCS: 0.9712
Avg EQS: 0.8938
Avg Growth: N/A
Static warnings: 304
```

典型拆分样例：

| 子集 | 语言 | Task ID | PRCS | EQS | 说明 |
|---|---|---|---:|---:|---|
| Plus | Go | `CWE-79_07` | 0.7544 | 0.0625 | 功能/安全通过，但 warning 和复杂度惩罚很重 |
| Plus | Go | `CWE-502_09` | 0.7719 | 0.1250 | Go 代码静态警告较多，EQS 比 PRCS 更明显暴露工程质量问题 |
| Base | Go | `CWE-090_codeql_1.py` | 0.7730 | 0.1288 | PRCS 因 Func/Sec 通过仍不低，但 EQS 显示 warning/复杂度压力 |
| Plus | C++ | `CWE-502_10` | 0.8158 | 0.3125 | C++ 代码复杂度很高，当前不计算 Growth，只看 warning 和复杂度 |

当前建议：`PRCS` 和 `EQS` 都保留。论文主表使用 `Func/Sec`、`PRCS`、`EQS` 三列并列展示；讨论工程质量时优先看 `EQS`。如果没有合法的代码膨胀基准，就在表中把 Growth 写成 N/A，不要硬算。

## 工作注意事项

- 搜索优先使用 `rg`；如果本机 `rg` 不可用，再用 PowerShell 自带搜索。
- 不要把真实 API Key 写进任何文件、日志或回复里。
- 不要随意删除 `translation_work/docker_revalidation/current_best_after_remaining_fixes/`，这是当前历史验证报告。
- 不要随意改 `SecEvoBasePlus/` 里的数据内容。必须改时，要说明改了哪条 `ID`、为什么改、改完怎么验证。
- 运行生成代码时必须通过 Docker 或明确的沙盒环境，不要直接信任生成代码。
- 新依赖、缓存、临时工作目录优先放在当前项目下的 `translation_work/` 或其他 D 盘目录，不要放到 C 盘。
- 最终论文和汇报默认使用 Secure-only 安全代码生成主线。

## 临时文件和收尾

完成任务后要及时整理：

- 一次性脚本、临时过滤 JSON、临时日志，任务结束后删除。
- `__pycache__/`、临时测试文件，如果不是实验结果，也要清理。
- 不要删除用户明确要求保留的实验数据、结果文件、轨迹目录或日志。

## 汇报方式

向用户汇报时，把用户当作刚接触这个项目的新手来解释：

- 先说结论：做了什么，是否完成。
- 再说原因：为什么这么改。
- 最后说证据：跑了什么命令，结果是多少。
- 第一次提到 Docker、JSONL、沙盒、验证器、门控、自进化时，用一句简单话解释。

## 文档维护规则

本文件只记录当前定稿流程，不再记录旧阶段流水账。

如果后续 Java/JS Docker 环境补齐，请只新增：

- Java/JS 固定镜像名。
- Java/JS Secure 验证命令。
- Java/JS 最新 Secure 验证结果。

不要把旧失败过程、临时尝试或候选方案再追加回本文件。
