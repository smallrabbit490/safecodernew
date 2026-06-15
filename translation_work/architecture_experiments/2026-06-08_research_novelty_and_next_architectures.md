# 跨语言安全迁移方法新颖性评估与下一版架构建议

日期：2026-06-08

## 结论

当前 `M1-M7` 不建议直接作为 A 类会议论文的最终主方法。它更适合作为一套消融实验矩阵，用来证明哪些组件有用、哪些组件不足。

主要原因是：`M1-M7` 目前看起来仍然像几类已有方法的组合：

- 代码翻译：Python 翻译到 Go/C++。
- 执行反馈修复：运行失败后把错误信息交给模型修。
- RAG/Memory：把训练样本总结成经验，再检索给模型。
- Self-evolution：从失败轨迹里总结 skill，再用于下一轮。
- 安全代码生成：让 Secure 版本更安全。

这些方向本身都已有近年工作。因此论文真正要突出的新意，应该从“多轮修复更好”升级为：

```text
从 Python Secure/Insecure 成对样本中抽取安全语义差异，
并把这个差异迁移到 Go/C++，
同时保证 Secure 保留防护、Insecure 保留预期失败或漏洞行为。
```

一句话版本：

```text
我们不是只做代码翻译，而是做 Security-Contrastive Cross-Language Transfer。
```

## Sub-agent 反馈汇总

本轮开了两个只读 sub-agent。

### Einstein：新颖性评估

Einstein 的结论是：`M1-M7` 可以作为实验框架和消融矩阵，但不够作为 A 会主贡献。

它指出的最大缺口是：

```text
M1-M7 还没有把“跨语言安全语义迁移”抽象成清楚、可验证、可复用的新方法。
```

它建议强化以下贡献：

- `Security Delta IR`：把 Python Secure/Insecure 差异抽成结构化中间表示。
- `Paired Differential Oracle`：Secure 和 Insecure 成对验证，而不是孤立验证。
- `Cross-Language Failure Atlas`：总结 Python 到 Go/C++ 的语言特定失败模式。
- `CWE-Conditional Router`：按 CWE、语言、轨道选择不同方法。
- `Evidence-Driven Self-Evolution`：只有被验证确实有效的经验才进入长期记忆。

### Boyle：实验设计

Boyle 的结论是：应该把下一版方法设计为一个组合框架，而不是继续把所有模块堆到 `M7` 里。

推荐主线：

```text
Contrastive Security Transfer Agent

Python Secure/Insecure Pair
        ↓
Security Delta IR
        ↓
CWE + Language + Mode Router
        ↓
Go/C++ Secure/Insecure Generation
        ↓
Paired Differential Oracle
        ↓
Risk-Budgeted Repair
        ↓
Failure Atlas / Evolution Memory
```

这个建议和 Einstein 的判断一致：论文创新点要围绕“安全差异如何跨语言保留”，不是围绕“多跑几轮 repair”。

## 外部工作对照

### TransAgent：代码翻译已经在做执行对齐

TransAgent 是 FSE 2026 接收的 LLM 代码翻译工作。它的核心是通过源程序和目标程序之间的细粒度执行对齐定位错误代码块，从而缩小修复范围。

参考：

- https://arxiv.org/abs/2409.19894

对我们的启发：

- 如果只说“翻译失败后根据错误修复”，新意不够。
- 我们要强调自己不是普通功能等价翻译，而是 Secure/Insecure 安全差异的迁移。
- 可以借鉴“对齐”的写法，但对齐对象应从执行轨迹升级为安全语义差异。

### RepairAgent：执行反馈修复本身已经不新

RepairAgent 是 ICSE 2025 的自动程序修复工作。它把 LLM 作为 agent，使用工具、动态 prompt 和状态机进行修复。

参考：

- https://www.software-lab.org/publications/icse2025_RepairAgent.pdf

对我们的启发：

- `M1_feedback_repair` 和 `M3_failure_typed_repair` 不能作为主创新。
- RepairAgent 已经说明“工具 + 反馈 + 多轮修复”是强基线。
- 我们需要把 repair 变成安全迁移专用，例如 `Risk-Budgeted Repair`。

### GEPA：自进化已经有成熟叙事

GEPA 是 ICLR 2026 Oral。它通过自然语言反思，从轨迹中诊断问题、提出 prompt 更新，并用 Pareto frontier 合并互补经验。

参考：

- https://arxiv.org/abs/2507.19457
- https://github.com/gepa-ai/gepa

对我们的启发：

- `M6_skill_evolution` 如果只是总结经验，不够新。
- 自进化必须有“验证门控”：经验是否真的提升 Secure 或正确保留 Insecure。
- 我们可以做安全领域特化的 `Evidence-Driven Self-Evolution`。

### Hermes Agent：自改进 agent 强调 memory 和 skills

Hermes Agent 官方 README 把它定位为 self-improving agent，强调从经验创建 skills、在使用中改进 skills、持久化知识、搜索过去对话。

参考：

- https://github.com/NousResearch/hermes-agent
- https://www.sourcepulse.org/projects/27162442

对我们的启发：

- 不能只说“我们也有 skill evolution”。
- 应该明确 skill 的来源、存储、验证、晋升和回滚。
- 对本项目来说，skill 不应该是泛化经验，而应该是安全迁移经验。

### Secure Code Generation with Reflexion

该方向说明，安全代码生成里使用多轮反思和反馈已经是自然思路。

参考：

- https://arxiv.org/abs/2511.03898

对我们的启发：

- 论文不能只证明 Secure 代码更安全。
- 我们的独特任务是双轨：Secure 要安全，Insecure 要正确保留错误示范。

## 本地离线诊断结果

本轮没有直接继续烧 API，而是先用已有 `test=10` 有效结果做低成本诊断。

使用的有效结果文件：

```text
translation_work/architecture_experiments/method_matrix_api_dev10_test10_key5_20260607/M4_adaptive_retrieval.records.json
translation_work/architecture_experiments/method_matrix_api_dev10_test10_m6_only_20260607/M6_skill_evolution.records.json
translation_work/architecture_experiments/method_matrix_api_dev10_test10_m7_only_20260607/M7_full_method.records.json
```

注意：`method_matrix_api_dev10_test10_key5_20260607` 里的 `M6/M7` 是无效混跑结果，不能用于最终结论。M6/M7 要看单独重跑目录。

### 单方法结果

| 方法 | Secure C++ | Secure Go | Insecure C++ | Insecure Go | All-Four |
|---|---:|---:|---:|---:|---:|
| M4 | 8/10 | 9/10 | 7/10 | 6/10 | 5/10 |
| M6 | 8/10 | 8/10 | 7/10 | 7/10 | 5/10 |
| M7 | 7/10 | 9/10 | 8/10 | 8/10 | 4/10 |

解释给新手：

- `Secure C++` 和 `Secure Go` 是安全版本能不能通过功能测试。
- `Insecure C++` 和 `Insecure Go` 是不安全版本能不能表现出和原始 Python 不安全代码一致的失败或漏洞行为。
- `All-Four` 是同一条题目四个版本都对，要求最严格。

### Oracle Router 上界

如果在每条样本上从 `M4/M6/M7` 里选择最好的一个，结果是：

```text
records = 10
all_four_ok = 7
all_four_rate = 0.70
mean_track_score = 0.90
```

这说明一个重要现象：

```text
单一方法最强只有 5/10，
但不同方法之间有互补性，
如果能学会“什么时候选哪个方法”，理论上可以到 7/10。
```

因此 `CWE-Conditional Method Router` 值得作为下一版架构核心之一。

进一步计算 router regret：

| 方法 | All-Four | Oracle All-Four | Regret |
|---|---:|---:|---:|
| M4 | 0.50 | 0.70 | 0.20 |
| M6 | 0.50 | 0.70 | 0.20 |
| M7 | 0.40 | 0.70 | 0.30 |

解释：

```text
Regret 可以理解为“这个固定方法离理想选择还差多少”。
M4/M6 差 0.20，M7 差 0.30，
说明继续押注单一固定架构会浪费不同方法之间的互补性。
```

### Track-level 失败归因

新增诊断统计了每个方法四条轨道的通过率：

| 方法 | Secure C++ | Secure Go | Insecure C++ | Insecure Go | 最弱轨道 |
|---|---:|---:|---:|---:|---|
| M4 | 0.80 | 0.90 | 0.70 | 0.60 | Insecure Go |
| M6 | 0.80 | 0.80 | 0.70 | 0.70 | Insecure C++ / Insecure Go |
| M7 | 0.70 | 0.90 | 0.80 | 0.80 | Secure C++ |

这个结果很关键：

```text
M4 更会做 Secure，但 Insecure Go 弱。
M7 更会保留 Insecure，但 Secure C++ 弱。
M6 比较均衡，但没有单点压倒性优势。
```

因此下一版方法不能只问“哪个 M 最强”，而要问：

```text
什么样的 CWE / 语言 / 轨道应该交给哪种策略？
```

这就是 Router 和 Paired Oracle 的实验必要性。

### Track-wise Router 模拟

为了避免只看 oracle 上界，本轮又加了一个更接近真实可实现的规则模拟：

```text
对每一条轨道，选择该轨道整体通过率最高的方法。
```

得到的策略是：

| 轨道 | 选择方法 | 该轨道通过率 |
|---|---|---:|
| Secure C++ | M6 | 0.80 |
| Secure Go | M7 | 0.90 |
| Insecure C++ | M7 | 0.80 |
| Insecure Go | M7 | 0.80 |

但组合后的 All-Four 是：

```text
track-wise router all_four_rate = 0.40
```

这个结果很重要，因为它说明：

```text
只按“轨道整体通过率”选方法还不够。
```

原因是 All-Four 要求同一条样本的四个轨道同时成功。某个方法在一条轨道上平均最好，并不代表它对某个具体 CWE 或具体样本也最好。

因此 router 不能只看：

```text
Secure C++ / Secure Go / Insecure C++ / Insecure Go
```

还必须加入：

```text
CWE、目标语言、Secure/Insecure 模式、历史失败类型、Security Delta 类型
```

这进一步支持 `CWE-Conditional Method Router`，而不是简单的 track router。

### Diff Preservation 诊断

诊断脚本还检查了目标语言 Secure/Insecure 是否保留了明显的安全差异。

结果：

| 方法 | Diff Preservation |
|---|---:|
| M4 | 6/10 |
| M6 | 5/10 |
| M7 | 6/10 |

大部分塌缩都发生在 Go。

解释：

```text
如果 Secure 和 Insecure 在 Go 里看起来差不多，
说明模型可能把不安全样本顺手修安全了，
或者没有把 Python 中的安全差异真正迁移过去。
```

这支撑了 `Paired Differential Oracle` 和 `Security Delta IR` 的必要性。

### Paired Outcome 诊断

为了更贴近 `Paired Differential Oracle`，本轮又加入了成对结果统计。

这里不再单独看 Secure 或 Insecure，而是按语言成对看：

```text
C++ pair = Secure C++ + Insecure C++
Go pair = Secure Go + Insecure Go
```

每个 pair 分成四类：

- `both_ok`：Secure 和 Insecure 都符合各自预期。
- `secure_only`：Secure 对，但 Insecure 没有保持预期失败或漏洞行为。
- `insecure_only`：Insecure 对，但 Secure 没通过。
- `both_fail`：两边都失败。

结果如下：

| 方法 | C++ both_ok | C++ pair rate | Go both_ok | Go pair rate |
|---|---:|---:|---:|---:|
| M4 | 5/10 | 0.50 | 6/10 | 0.60 |
| M6 | 6/10 | 0.60 | 6/10 | 0.60 |
| M7 | 5/10 | 0.50 | 7/10 | 0.70 |

这个结果说明：

```text
M7 在 Go 的 Secure/Insecure 成对一致性上最好，
但在 C++ 上并不比 M6 好。
```

所以 M7 的价值不是“全局最强”，而是：

```text
它更擅长某些语言或轨道上的 Insecure 保留。
```

这进一步支持下一版方法中必须有：

- `Paired Differential Oracle`：用成对结果指导修复，而不是单轨道判断。
- `CWE/Language Router`：不同语言可能应该选不同策略。
- `Risk-Budgeted Repair`：当出现 `secure_only` 时，重点修 Insecure 但不能把漏洞修没；当出现 `insecure_only` 时，重点修 Secure 但不能污染 Insecure。

### Failure Atlas 诊断

本轮进一步把失败按类别归到 failure atlas。结果如下：

| 方法 | 总失败轨道数 | 主要失败类型 |
|---|---:|---|
| M4 | 10 | compile_error 3、cpp_compile_error 3、runtime_error 3、go_undefined_symbol 1 |
| M6 | 10 | runtime_error 6、cpp_compile_error 2、compile_error 1、go_undefined_symbol 1 |
| M7 | 8 | cpp_compile_error 4、compile_error 3、runtime_error 1 |

从轨道看：

| 方法 | 失败最多的轨道 |
|---|---|
| M4 | Insecure Go 4 次 |
| M6 | Insecure C++ 3 次、Insecure Go 3 次 |
| M7 | Secure C++ 3 次 |

这说明：

```text
失败不是一种原因。
有些是 Go/C++ 语法或依赖问题，
有些是运行行为问题，
有些是 Insecure 轨道的预期失败没有保留。
```

因此下一版修复不能继续用统一 repair prompt。更合理的是：

```text
先判断失败类型，再决定允许模型改什么。
```

例如：

- Go `undefined` 或缺包：只允许改 import / 依赖 / API 名称。
- C++ compile error：只允许改 include、类型、函数签名。
- Runtime error：允许小范围修异常和边界。
- Insecure behavior mismatch：禁止新增安全防护，只允许恢复预期漏洞行为。

这直接支撑 `Failure Atlas + Risk-Budgeted Repair`：

```text
Failure Atlas 负责告诉系统“这类错误通常是什么原因”；
Risk-Budgeted Repair 负责限制“这一轮最多能改到哪里”。
```

本轮已经把 failure atlas 自动合成为 `repair_policy`。例如：

| 失败类别 | 修复预算 |
|---|---|
| cpp_compile_error | 只允许改 include、类型、函数签名 |
| compile_error | 只允许改语法、import、类型 |
| go_undefined_symbol | 只允许改 import、依赖、API 名称 |
| runtime_error | 只允许做最小运行时修复 |
| behavior_mismatch | Secure 可修 guard；Insecure 禁止消除预期漏洞行为 |

这表示 `Risk-Budgeted Repair` 已经不只是概念，而是可以由诊断脚本产出一张规则表，供下一轮 repair prompt 使用。

## 下一版方法候选

### M8：CWE-Conditional Method Router

核心想法：

```text
不要固定使用 M4/M6/M7。
根据 CWE、目标语言、Secure/Insecure 轨道、历史失败类型，选择最合适的方法。
```

建议存储结构：

```json
{
  "cwe": "CWE-078",
  "target_language": "go",
  "security_mode": "insecure",
  "selected_architecture": "M7_full_method",
  "confidence": 0.82,
  "evidence_record_ids": ["CWE-078_author_1.py"],
  "historical_success_rate": 0.8
}
```

主要指标：

- Router All-Four Rate
- Track-level Success Rate
- Router Regret，也就是和 oracle router 上界差多少
- Cost-aware Score，也就是成功率除以平均耗时

为什么有创意：

```text
它不是继续堆模块，而是承认“不同 CWE 和语言需要不同迁移策略”。
```

### M9：Security Delta IR

核心想法：

```text
先从 Python Secure/Insecure 对中抽取安全差异，再指导 Go/C++ 生成。
```

建议存储结构：

```json
{
  "ID": "CWE-078_author_1.py",
  "cwe": "CWE-078",
  "vulnerability_type": "command injection",
  "secure_guard": "avoid shell string concatenation or validate command input",
  "insecure_missing_guard": "passes user-controlled string into command execution",
  "expected_secure_behavior": "reject or safely execute without injection",
  "expected_insecure_failure": "injection payload remains effective or expected unsafe behavior is preserved",
  "language_mapping": {
    "go": {
      "secure_pattern": "exec.Command with separated args and validation",
      "insecure_pattern": "shell execution with concatenated command"
    },
    "cpp": {
      "secure_pattern": "avoid system() with user input",
      "insecure_pattern": "system() receives user-controlled command"
    }
  }
}
```

主要指标：

- Delta Preservation Rate
- Collapse Rate
- Guard Transfer Accuracy
- Vulnerability Preservation Accuracy

为什么有创意：

```text
它把论文贡献从 prompt engineering 变成了安全语义表示。
```

### M10：Paired Differential Oracle

核心想法：

```text
同一个题目的 Secure 和 Insecure 必须成对验证。
Secure 不能有漏洞，Insecure 不能被误修成安全。
```

建议存储结构：

```json
{
  "ID": "CWE-078_author_1.py",
  "language": "go",
  "secure_ok": true,
  "insecure_ok": true,
  "secure_behavior_signature": "safe command execution",
  "insecure_behavior_signature": "command injection preserved",
  "expected_delta": "safe args vs shell concatenation",
  "observed_delta": "safe args vs shell concatenation",
  "delta_match": true,
  "failure_reason": null
}
```

主要指标：

- Pair Consistency Rate
- Insecure Expected-Failure Match Rate
- False Secure Rate：Insecure 被修安全的比例
- False Vulnerable Rate：Secure 仍然不安全的比例

为什么有创意：

```text
它把 Insecure 的“失败”也变成一种正确性要求。
```

### M11：Risk-Budgeted Repair

核心想法：

```text
修复时先判断错误类型，再限制允许改动的范围。
```

例如：

- 编译错误：只能改 include/import、类型、函数签名。
- 运行错误：可以小范围修边界和异常。
- Secure 安全错误：允许补安全检查。
- Insecure 安全漂移：禁止新增安全检查，只能修能运行的外壳。

建议存储结构：

```json
{
  "ID": "CWE-078_author_1.py",
  "language": "go",
  "security_mode": "insecure",
  "round": 2,
  "previous_error_type": "compile_error",
  "allowed_change_scope": "imports_and_signature_only",
  "code_length_before": 44,
  "code_length_after": 47,
  "security_delta_changed": false,
  "accepted": true,
  "reject_reason": null
}
```

主要指标：

- Repair Acceptance Rate
- Drift Rate
- Code Growth Ratio
- Same-error Repeat Rate
- Minimal Fix Success Rate

为什么有创意：

```text
它专门解决 Insecure 被越修越安全、代码越修越长的问题。
```

### M12：Failure Atlas + Evidence-Driven Self-Evolution

核心想法：

```text
把失败类型沉淀成跨语言失败图谱，并且只有验证有效的规则才能进入长期记忆。
```

建议存储结构：

```json
{
  "failure_type": "go_unused_import",
  "language": "go",
  "security_mode": "secure",
  "cwe": "CWE-020",
  "symptom": "imported and not used",
  "root_cause": "model copied a broad import block",
  "repair_rule": "remove unused imports before final validation",
  "negative_rule": "do not add new imports unless directly used",
  "support_count": 8,
  "success_after_repair_count": 6,
  "confidence": 0.75
}
```

配套 evolution memory：

```json
{
  "version": "2026-06-08-001",
  "promoted_rules": ["go_unused_import_minimal_fix"],
  "rejected_rules": ["always_add_os_exec_wrapper"],
  "promotion_evidence": ["dev_success_delta=+0.12"],
  "regression_evidence": []
}
```

主要指标：

- Rule Precision
- Regression Count
- Memory Promotion Rate
- Cross-CWE Generalization Rate

为什么有创意：

```text
它把自进化从“模型自己总结一句经验”变成“有证据、有门控、有回滚的知识库演化”。
```

## 推荐论文主架构

建议最终不要叫 `M7_full_method`。可以把论文方法命名为：

```text
SCT-Agent: Security-Contrastive Transfer Agent
```

主流程：

```text
1. Security Delta Extraction
   从 Python Secure/Insecure 中抽取安全差异。

2. Delta-Aware Routing
   根据 CWE、语言、轨道和历史失败类型选择生成策略。

3. Dual-Track Translation
   同时生成 Secure 和 Insecure，且两者共享同一个安全差异契约。

4. Paired Differential Verification
   成对验证 Go/C++ 的 Secure/Insecure 差异是否和 Python 一致。

5. Risk-Budgeted Repair
   根据错误类型限制修复范围，避免安全语义漂移。

6. Evidence-Driven Evolution
   把真正有效的失败经验和修复规则加入 Failure Atlas。
```

## 建议 RQ

### RQ1：跨语言安全差异迁移是否比普通代码翻译更有效？

比较：

- Direct Translation
- Feedback Repair
- M4/M6/M7
- SCT-Agent

指标：

- Secure Pass Rate
- Insecure Expected-Failure Match Rate
- All-Four Rate

### RQ2：Security Delta IR 是否能减少 Secure/Insecure 塌缩？

比较：

- 没有 Delta IR
- 有 Delta IR

指标：

- Delta Preservation Rate
- Collapse Rate
- False Secure Rate
- False Vulnerable Rate

### RQ3：CWE-Conditional Router 是否优于单一固定架构？

比较：

- M4
- M6
- M7
- Rule Router
- Learned Router
- Oracle Router 上界

指标：

- Router All-Four Rate
- Router Regret
- Cost-aware Score

### RQ4：Risk-Budgeted Repair 是否提升 Insecure Go/C++ 的稳定性？

比较：

- 普通 repair
- Failure-typed repair
- Risk-budgeted repair

指标：

- Insecure Go Success
- Insecure C++ Success
- Drift Rate
- Code Growth Ratio

### RQ5：Evidence-Driven Self-Evolution 是否能跨 CWE 泛化？

比较：

- 无 memory
- 普通 lessons memory
- Failure Atlas + promotion gate

指标：

- Rule Precision
- Regression Count
- Cross-CWE Generalization
- Dev-to-Test Transfer

### RQ6：方法在不同目标语言上是否稳定？

比较：

- Go
- C++
- 后续可加入 Java/JS

指标：

- Per-language Secure Rate
- Per-language Insecure Rate
- Per-language All-Four Rate
- 失败类型分布

### RQ7：方法成本是否可接受？

这里不建议作为核心 RQ，但可以作为补充 RQ。

指标：

- 平均 API 调用次数
- 平均 token
- 平均运行时间
- 每成功样本成本

## 下一步实验计划

建议先做不烧 API 的三步：

1. 扩展 `research_diagnostics.py`
   - 已完成 track-level 失败归因。
   - 已完成 router regret 计算。
   - 已完成 failure atlas 失败类型归因。
   - 已完成 repair policy 合成。
   - 已完成规则版 Security Delta IR 抽取。
   - 已完成 paired repair action plan。
   - 后续可以继续加更细的 security mismatch / false secure 检测。

2. 在 `test=10` 和更大已有结果上跑诊断
   - 先验证 M4/M6/M7 的互补性是否稳定。
   - 如果 test=30 或 Base 全量也显示 oracle router 明显高于单方法，再实现真实 router。

3. 实现最小版 `SCT-Agent`
   - 不必一次做完 M8-M12。
   - 第一版只做 `Security Delta IR + Paired Differential Oracle + Risk-Budgeted Repair`。
   - Router 可以先用规则版。

之后再烧 API 跑：

```text
train = 30
dev = 10 或 20
test = 30
methods = M4, M6, M7, SCT-Agent-lite
languages = Go, C++
```

如果 `SCT-Agent-lite` 在 All-Four、Diff Preservation、Insecure Go 上都有提升，再扩到 Base/Plus 全量。

## 已验证

本轮验证命令：

```text
cd D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder
python -m pytest tests/test_research_diagnostics.py -q
python -m pytest tests/test_architecture_experiment.py tests/test_research_diagnostics.py -q
```

结果：

```text
4 passed in 0.05s
19 passed in 1.03s
```

离线诊断输出：

```text
D:\thecourceofdasi\safecodernew\translation_work\architecture_experiments\research_diagnostics_test10_20260608.json
```

报告结论：

```text
M1-M7 不够作为最终 A 会主方法；
M1-M7 应作为消融矩阵；
下一版主方法建议升级为 SCT-Agent；
本地 oracle router 结果已经显示方法选择有 0.50 -> 0.70 的潜在提升空间；
diff preservation 只有 0.5-0.6，说明安全差异迁移确实是当前短板。
```
