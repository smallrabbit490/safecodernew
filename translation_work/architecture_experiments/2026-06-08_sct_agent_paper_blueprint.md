# SCT-Agent 论文方法蓝图

日期：2026-06-08

## 一句话判断

当前 `M1-M7` 不适合直接作为 A 类会议的最终主方法，但它已经足够作为消融矩阵和问题证据。

更合适的论文主方法应该是：

```text
SCT-Agent: Security-Contrastive Transfer Agent
```

它的核心不是“让大模型多轮修复代码”，而是：

```text
从 Python Secure/Insecure 成对代码中抽取安全语义差异，
再把这个差异迁移到 Go/C++，
并用成对 oracle 验证 Secure 和 Insecure 是否分别保持正确语义。
```

## 为什么 M1-M7 不够作为最终贡献

`M1-M7` 现在更像是现有方法的组合：

- `M1`：执行反馈修复。
- `M2`：Python delta memory。
- `M3`：失败类型修复。
- `M4`：自适应检索。
- `M5`：验证器引导演化。
- `M6`：skill evolution。
- `M7`：把上述组件组合起来。

这些组件都合理，但单独看不够新。近年 A 会和顶会工作已经覆盖了很多类似方向：

- Code translation + execution alignment，例如 TransAgent。
- LLM agent + program repair，例如 RepairAgent。
- Reflective prompt evolution，例如 GEPA。
- Self-improving skill/memory agent，例如 Hermes Agent。
- 安全代码生成中的多轮反馈和 Reflexion。

所以如果论文只写：

```text
我们把 Python 翻译到 Go/C++，失败后用模型修，再总结经验。
```

审稿人很可能会认为这是已有套路的组合。

## 外部证据表

| 方向 | 代表工作 | 核心点 | 对我们的影响 |
|---|---|---|---|
| LLM 代码翻译 | TRANSAGENT | 通过源/目标程序执行对齐定位错误块，再缩小修复空间 | 普通“翻译 + 报错修复”不够新，我们要强调安全差异迁移 |
| 程序修复 Agent | RepairAgent | LLM agent 使用工具、动态 prompt、状态机做自动程序修复 | `M1/M3` 只能当 baseline，不能当主贡献 |
| Prompt 自进化 | GEPA | 从轨迹中用自然语言反思，提出和测试 prompt 更新，并合并互补经验 | `M6` 的 skill evolution 必须有验证门控和晋升机制 |
| Self-improving Agent | Hermes Agent | 从经验创建 skills、使用中改进 skills、持久化记忆、搜索历史会话 | 我们的自进化要做成安全迁移专用的 Failure Atlas，而不是泛化记忆 |

参考链接：

- TRANSAGENT: https://arxiv.org/abs/2409.19894
- RepairAgent: https://www.software-lab.org/publications/icse2025_RepairAgent.pdf
- GEPA: https://arxiv.org/abs/2507.19457
- GEPA code: https://github.com/gepa-ai/gepa
- Hermes Agent: https://github.com/NousResearch/hermes-agent

这些工作共同说明：

```text
执行反馈、RAG、memory、skill evolution、self-improvement 都已经是热门路线。
论文必须把贡献压到“跨语言安全差异迁移”这个更窄但更明确的问题上。
```

## 真正应该强调的新问题

本项目最有潜力的问题不是普通代码翻译，而是：

```text
Python 中 Secure 和 Insecure 的安全差异，能不能迁移到其他语言？
```

这里有两个同时成立的目标：

1. Secure 目标代码要保留防护，并通过功能测试。
2. Insecure 目标代码不能被模型顺手修安全，而要保留原始 Python 不安全代码的预期失败或漏洞行为。

这比普通安全修复更难，因为普通安全修复只需要“越安全越好”。我们的任务要求模型知道：

```text
什么时候应该修安全，什么时候必须保留不安全。
```

这就是论文的核心差异。

## 本地证据

本地有效数据来自 `test=10` 的 M4/M6/M7 结果：

```text
M4_adaptive_retrieval
M6_skill_evolution
M7_full_method
```

诊断文件：

```text
translation_work/architecture_experiments/research_diagnostics_test10_20260608.json
```

### 证据 1：固定方法不够强

| 方法 | All-Four |
|---|---:|
| M4 | 0.50 |
| M6 | 0.50 |
| M7 | 0.40 |

说明：

```text
没有一个固定架构能稳定解决四条轨道。
```

### 证据 2：Oracle Router 有明显上界

| 方法 | All-Four |
|---|---:|
| 最强固定方法 | 0.50 |
| Oracle Router | 0.70 |

说明：

```text
不同方法之间有互补性。
如果能判断什么时候用 M4/M6/M7，结果有提升空间。
```

### 证据 3：简单 track router 不够

简单按轨道选择最佳方法：

| 轨道 | 选择 |
|---|---|
| Secure C++ | M6 |
| Secure Go | M7 |
| Insecure C++ | M7 |
| Insecure Go | M7 |

结果：

```text
Track-wise Router All-Four = 0.40
```

说明：

```text
只看 Secure/ Insecure 或 Go/C++ 不够。
Router 必须进一步看 CWE、失败类型和 Security Delta。
```

### 证据 4：M7 对 Go pair 有价值，但不是全局最好

| 方法 | C++ Pair | Go Pair |
|---|---:|---:|
| M4 | 0.50 | 0.60 |
| M6 | 0.60 | 0.60 |
| M7 | 0.50 | 0.70 |

说明：

```text
M7 更擅长 Go 的 Secure/Insecure 成对一致性，
但 C++ 上不是最好。
```

这支持 `language-aware router`，也支持 `paired oracle`。

### 证据 5：失败类型混杂，普通 repair 不够

Failure Atlas 显示失败包括：

- `compile_error`
- `cpp_compile_error`
- `go_undefined_symbol`
- `runtime_error`

说明：

```text
失败不是一种原因，不能只用统一 repair prompt。
```

更合理的是：

```text
先判断失败类型，再限制修复范围。
```

这支持 `Risk-Budgeted Repair`。

## 推荐主方法

### 方法名

```text
SCT-Agent: Security-Contrastive Transfer Agent
```

### 总流程

```text
Python Secure/Insecure Pair
        ↓
Security Delta Extraction
        ↓
Delta-Aware Router
        ↓
Dual-Track Translation
        ↓
Paired Differential Oracle
        ↓
Risk-Budgeted Repair
        ↓
Failure Atlas / Evidence-Driven Evolution
```

### 组件 1：Security Delta Extraction

输入：

```text
Python Secure Code
Python Insecure Code
Problem Description
Tests
CWE ID
```

输出 `Security Delta IR`：

```json
{
  "id": "CWE-078_author_1.py",
  "cwe": "CWE-078",
  "vulnerability_type": "command injection",
  "secure_guard": "avoid shell concatenation or validate command arguments",
  "insecure_missing_guard": "user input reaches shell command",
  "expected_secure_behavior": "payload cannot alter command structure",
  "expected_insecure_behavior": "payload can affect command execution",
  "go_mapping": {
    "secure_pattern": "exec.Command with separated args",
    "insecure_pattern": "shell command string with user input"
  },
  "cpp_mapping": {
    "secure_pattern": "avoid system() with user input",
    "insecure_pattern": "system() receives user-controlled string"
  }
}
```

论文贡献点：

```text
把 Secure/Insecure 差异显式表示出来，而不是隐含在 prompt 里。
```

### 组件 2：Delta-Aware Router

Router 不只看轨道，还看：

- CWE 类型
- 目标语言
- Secure/Insecure 模式
- Security Delta 类型
- 历史失败类型
- 当前方法在相似样本上的表现

输出：

```json
{
  "id": "CWE-078_author_1.py",
  "language": "go",
  "mode": "insecure",
  "selected_strategy": "vulnerability_preserving_translation",
  "base_architecture": "M7",
  "reason": "M7 has higher Go pair rate and this case requires insecure behavior preservation"
}
```

论文贡献点：

```text
不是所有样本都用同一种生成策略，而是让安全差异和语言特性决定策略。
```

### 组件 3：Dual-Track Translation

Secure 和 Insecure 不再分开独立生成，而是共享同一个 `Security Delta IR`：

```text
Secure 生成时：必须实现 secure_guard。
Insecure 生成时：必须保留 insecure_missing_guard。
```

这样能减少两种错误：

- Secure 没有修安全。
- Insecure 被误修成安全。

### 组件 4：Paired Differential Oracle

普通验证只问：

```text
这段代码能不能通过测试？
```

SCT-Agent 的验证问：

```text
同一个语言里的 Secure 和 Insecure 是否同时符合各自预期？
二者之间的安全差异是否和 Python 原始差异一致？
```

输出：

```json
{
  "id": "CWE-078_author_1.py",
  "language": "go",
  "secure_ok": true,
  "insecure_ok": true,
  "delta_match": true,
  "category": "both_ok"
}
```

论文贡献点：

```text
Insecure 的失败也变成了一种正确性要求。
```

### 组件 5：Risk-Budgeted Repair

修复前先判断失败类型：

| 失败类型 | 允许改动 |
|---|---|
| Go import / undefined | 只改 import、依赖、API 名称 |
| C++ compile error | 只改 include、类型、函数签名 |
| Secure behavior mismatch | 允许补安全 guard |
| Insecure behavior mismatch | 禁止补安全 guard，只恢复漏洞行为 |
| runtime error | 小范围修异常、边界、返回值 |

论文贡献点：

```text
修复不是越多越好，而是有安全语义边界。
```

### 组件 6：Failure Atlas / Evidence-Driven Evolution

每次失败都记录成结构化经验：

```json
{
  "failure_type": "go_undefined_symbol",
  "language": "go",
  "mode": "insecure",
  "cwe": "CWE-611",
  "symptom": "undefined symbol in generated Go code",
  "repair_rule": "use standard library XML parser or explicit dependency mapping",
  "negative_rule": "do not invent unavailable package APIs",
  "support_count": 3,
  "success_after_repair_count": 2,
  "confidence": 0.67
}
```

经验进入长期 memory 前必须通过门控：

```text
只有在 dev 上提升成功率，且不导致已成功样本回退，才晋升为规则。
```

论文贡献点：

```text
自进化不是模型随便总结，而是有证据、有晋升、有拒绝、有回滚。
```

## Baseline 和消融

### Baseline

| 名称 | 含义 |
|---|---|
| B0 Direct Translation | 直接翻译 Python 到 Go/C++ |
| B1 Feedback Repair | 翻译后失败再修 |
| B2 RAG / Memory | 使用 Python delta memory |
| B3 Failure-Typed Repair | 按失败类型修复 |
| B4 Skill Evolution | 使用经验总结 skill |
| B5 Fixed Full Method | 当前 M7 |

### SCT-Agent 消融

| 名称 | 移除组件 |
|---|---|
| SCT w/o Delta IR | 不显式抽取安全差异 |
| SCT w/o Router | 所有样本固定使用同一策略 |
| SCT w/o Paired Oracle | Secure/Insecure 分开验证 |
| SCT w/o Risk Budget | repair 不限制改动范围 |
| SCT w/o Failure Atlas | 不沉淀失败经验 |

## RQ 设计

### RQ1：SCT-Agent 是否比固定架构更能完成跨语言安全迁移？

比较：

- M4
- M6
- M7
- SCT-Agent

指标：

- All-Four Rate
- Secure Rate
- Insecure Expected-Behavior Rate

### RQ2：Security Delta IR 是否减少 Secure/Insecure 语义塌缩？

比较：

- w/o Delta IR
- with Delta IR

指标：

- Diff Preservation Rate
- Collapse Rate
- False Secure Rate
- False Vulnerable Rate

### RQ3：Delta-Aware Router 是否优于固定方法和简单 track router？

比较：

- 最强固定方法
- Track-wise Router
- CWE/Delta-aware Router
- Oracle Router

指标：

- All-Four Rate
- Router Regret
- Pair Success Rate

### RQ4：Paired Differential Oracle 是否能提升双轨一致性？

比较：

- 单轨验证
- 成对验证

指标：

- C++ Pair Rate
- Go Pair Rate
- secure_only 数量
- insecure_only 数量

### RQ5：Risk-Budgeted Repair 是否减少修复漂移？

比较：

- 普通 repair
- failure-typed repair
- risk-budgeted repair

指标：

- Repair Success Rate
- Drift Rate
- Code Growth Ratio
- Same-error Repeat Rate

### RQ6：Failure Atlas 的自进化规则是否能跨 CWE 泛化？

比较：

- 无 memory
- 普通 lessons memory
- evidence-gated failure atlas

指标：

- Rule Precision
- Regression Count
- Dev-to-Test Transfer
- Cross-CWE Generalization

### RQ7：成本是否可接受？

这个 RQ 放最后，不作为主创新。

指标：

- API 调用次数
- token 数
- 平均运行时间
- 每个成功样本的成本

## 实验顺序

### Step 1：离线诊断扩展

已完成：

- Oracle Router 上界。
- Track-wise Router 模拟。
- Router Regret。
- Track-level outcomes。
- Paired outcomes。
- Failure Atlas。
- Risk-Budgeted Repair Policy 合成。
- 规则版 Security Delta IR 抽取。
- Paired Repair Action Plan。
- Diff Preservation。

### Step 1.1：Failure Atlas 到 Repair Policy

本轮已经把 failure atlas 进一步转成 repair policy。也就是说，诊断不只是告诉我们失败了，还能告诉下一轮 repair：

```text
这类错误最多允许改什么。
```

示例规则：

| 失败类别 | 允许改动范围 |
|---|---|
| cpp_compile_error | includes_types_signatures_only |
| compile_error | syntax_imports_types_only |
| go_undefined_symbol | imports_dependencies_api_names_only |
| runtime_error | minimal_runtime_fix |
| behavior_mismatch | Secure 允许修 guard；Insecure 必须保留预期漏洞行为 |

这个组件对应 SCT-Agent 的 `Risk-Budgeted Repair`。它的意义是：

```text
修复不再是“把错误信息丢给模型随便改”，
而是先根据失败类型生成改动边界，
再让模型在边界内修。
```

当前生成位置：

```text
translation_work/architecture_experiments/research_diagnostics_test10_20260608.json
字段：repair_policy
```

### Step 1.2：规则版 Security Delta IR

本轮已经实现一个不调用 API 的规则版 `Security Delta IR`。它会从每条记录中抽取：

- `cwe`
- Python Secure/Insecure 的 shared security groups
- Python Secure-only / Insecure-only groups
- Go/C++ 目标代码中的 Secure/Insecure 差异是否保留
- risk notes

输出位置：

```text
translation_work/architecture_experiments/research_diagnostics_test10_20260608.json
字段：security_delta_ir
```

这个 IR 现在还是规则版，作用不是替代最终 LLM 分析，而是先让 SCT-Agent-lite 有一个可运行的中间表示。

示例含义：

```text
如果 Python Secure 有 validation，而 Insecure 没有，
IR 会把 validation 标成 secure_only_groups。

如果 Go/C++ 的 Secure/Insecure 目标代码差异消失，
IR 会把 diff_preserved 标成 false，
后续 Paired Oracle 或 Repair 就可以针对这个问题修。
```

这一步让 `Security Delta IR` 从论文概念变成了实际数据结构。

### Step 1.3：Paired Repair Action Plan

本轮已经把 Paired Outcome 和 Security Delta IR 串起来，生成每条样本的下一步动作：

| Pair 状态 | Delta 状态 | 动作 |
|---|---|---|
| Secure/Insecure 都通过 | delta 保留 | accept_pair |
| Secure/Insecure 都通过 | delta 塌缩 | repair_delta |
| 只有 Secure 通过 | 任意 | repair_insecure |
| 只有 Insecure 通过 | 任意 | repair_secure |
| 两边都失败 | 任意 | repair_both |

输出位置：

```text
translation_work/architecture_experiments/research_diagnostics_test10_20260608.json
字段：paired_repair_actions
```

这一步让 SCT-Agent-lite 的执行逻辑更清楚：

```text
不是看到失败就统一 repair，
而是先用 paired oracle 判断失败形态，
再决定修 Secure、修 Insecure、修 delta，还是接受结果。
```

这也能直接服务论文实验：

- 统计多少样本是 `repair_insecure`，说明 Insecure 保留仍是难点。
- 统计多少样本是 `repair_delta`，说明 Secure/Insecure 差异塌缩仍是难点。
- 统计多少样本是 `accept_pair`，说明成对迁移已经成功。

### Step 2：实现 SCT-Agent-lite

先实现最小可跑版本：

```text
Security Delta IR
+ Paired Differential Oracle
+ Risk-Budgeted Repair
+ rule-based Delta-Aware Router
```

暂时不做复杂 learned router。

### Step 3：小样本 API 验证

建议：

```text
train = 30
dev = 10
test = 10
methods = M4, M6, M7, SCT-Agent-lite
```

目的：

```text
先看 SCT-Agent-lite 是否在 All-Four、Go Pair、Diff Preservation 上超过 M4/M6/M7。
```

### Step 4：扩大到 test=30

如果 test=10 有提升，再跑：

```text
train = 30
dev = 20
test = 30
```

### Step 5：Base / Plus 全量

最后再跑 Base 和 Plus 全量，作为论文主结果。

## 对老师汇报版本

可以这样说：

```text
我们现在的 M1-M7 还不能直接作为 A 会主方法。
因为它本质上仍然像翻译、测试反馈、RAG 和记忆演化的组合。

但是实验发现了一个更有价值的现象：
不同方法对 Secure、Insecure、Go、C++ 的能力不一样。
例如 M7 在 Go 的 Secure/Insecure 成对一致性最好，
但 C++ 不如 M6；Oracle Router 能从 0.50 提到 0.70。

所以我们准备把主方法升级为 SCT-Agent。
它不只是翻译代码，而是先抽取 Python Secure/Insecure 的安全差异，
再根据 CWE、语言和失败类型选择生成/修复策略，
最后用 Paired Oracle 检查 Secure 和 Insecure 是否同时保持正确语义。

这样论文贡献从“多轮修复”升级为“跨语言安全差异迁移”。
```

## 当前状态

已经完成：

- 新颖性评估。
- A 会相关工作对照。
- 多 sub-agent 方案分析。
- 离线诊断实验。
- 诊断脚本和测试。
- 投稿级方法蓝图。
- 小并发智谱 smoke test 和监控报告。

还没完成：

- SCT-Agent-lite 的真实实现。
- SCT-Agent-lite API 实验。
- 更大样本验证。

## Smoke Test 后的补充结论

小并发验证报告：

```text
translation_work/architecture_experiments/2026-06-08_sct_smoke_monitoring_report.md
```

本次用 `glm-5.1`，并发 2，跑了 `M4` 和 `M7` 在 `CWE-434_pearce_2.py` 上的极小验证。

结果：

```text
M4: 只通过 Insecure C++
M7: 只通过 Insecure C++
Secure C++ / Secure Go / Insecure Go 均失败
```

这个结果不能作为论文主实验，但可以作为方法优化证据：

```text
CWE-434 文件上传类样本暴露出规则版 Delta IR 的不足。
当前 IR 只看到 path，没有明确抽出文件上传安全差异，
例如 extension、MIME、secure_filename、上传路径限制等。
```

因此 SCT-Agent-lite 的下一步要优先做：

```text
CWE-aware Security Delta IR
Action-guided Repair Prompt
```

其中 repair prompt 应该显式输入：

- `security_delta_ir`
- `paired_repair_action`
- `repair_policy`
- 上一轮错误报告

这会让模型知道：

```text
C++ 是 repair_secure，不能动已经正确的 Insecure C++；
Go 是 repair_both，而且要重新拉开 Secure/Insecure 差异。
```

所以现在的判断是：

```text
当前 M1-M7 不够发；
升级后的 SCT-Agent 方向有论文潜力；
下一步应该实现 SCT-Agent-lite 并跑 test=10 / test=30 验证。
```
