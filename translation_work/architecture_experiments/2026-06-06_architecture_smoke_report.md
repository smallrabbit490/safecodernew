# 多语言安全迁移自进化架构小规模测试报告

日期：2026-06-06

## 结论

本轮小规模测试已经跑通了“训练集经验生成 -> 测试集架构对比 -> 执行式双目标评估”的基本流程。

在 2 条测试样本上，当前最值得继续扩大的候选是 `memory_positive`。它的 Insecure 保留率最高，但 Secure 通过率低于加入负例/技能的架构。也就是说，现阶段还不能直接宣布最终架构，只能说：

- `memory_positive` 更擅长保留不安全行为。
- `memory_positive_negative` 和 `memory_skill_evolution` 更稳地保住 Secure 结果，但 Insecure C++ 仍然弱。
- `baseline_repair` 最弱，说明“无经验记忆”的普通修复不适合作为最终方法。

## 数据划分

数据源：

```text
DatasetAndMethod/CodeSecEval/SecEvaBase.json
```

本轮采用固定随机种子 `20260606`。

训练集 4 条，只用于生成经验，不参与测试：

- `CWE-601_sonar_2.py`
- `CWE-521_sonar_2.py`
- `CWE-434_pearce_1.py`
- `CWE-730_author_1.py`

测试集 2 条，只用于架构比较：

- `CWE-1204_sonar_1.py`
- `CWE-319_author_2.py`

## 对比架构

### A. baseline_repair

普通翻译与修复流程，不使用长期经验。

### B. memory_positive

只使用训练集里总结出的正向经验。经验只注入修复阶段，不注入初始翻译阶段。

### C. memory_positive_negative

使用正向经验，同时加入相反模式的 warning-only 负例。

### D. memory_skill_evolution

在 C 的基础上加入一个由训练集蒸馏得到的修复 skill，并允许最多 2 轮修复。

## 评估方法

采用一个统一评估协议：执行式双目标评估。

每条记录检查四条轨道：

- Secure C++
- Secure Go
- Insecure C++
- Insecure Go

Secure 轨道要求功能和安全测试通过。Insecure 轨道要求目标语言代码能编译/运行，并保留原 Python 不安全代码的预期错误或漏洞行为。

## 有效结果

有效合并报告：

```text
translation_work/architecture_experiments/api_smoke_20260606_combined_report.json
```

| 架构 | Secure Rate | Insecure Rate | All Four Rate | 备注 |
|---|---:|---:|---:|---|
| memory_positive | 0.50 | 1.00 | 0.00 | Insecure 最好，但 Secure 有损失 |
| memory_positive_negative | 1.00 | 0.50 | 0.00 | Secure 最稳，Insecure C++ 弱 |
| memory_skill_evolution | 1.00 | 0.50 | 0.00 | 与 C 类似，额外修复轮数未明显提升 |
| baseline_repair | 0.75 | 0.25 | 0.00 | 整体最弱 |

## 观察

1. 正向经验对 Insecure 保留有明显帮助。

   在 `memory_positive` 中，Insecure C++ 和 Insecure Go 都通过了；baseline 只通过了 Insecure Go。

2. 负例不是越多越好。

   `memory_positive_negative` 的 Secure 全过，但 Insecure C++ 没有通过。说明负例提示可能让模型变得更保守，或者干扰了“不安全行为保持”。

3. 当前 skill evolution 还不够成熟。

   `memory_skill_evolution` 使用了额外的 skill 和 2 轮修复，但没有明显优于 `memory_positive_negative`。这说明现在的 skill 还太粗，需要从更多训练样本和失败轨迹中蒸馏。

4. Insecure C++ 是主要短板。

   多个架构失败都集中在 Insecure C++，常见失败表现是目标代码没有保留预期的不安全输出长度或错误行为。

## 一次无效结果说明

第一次 `run1` 中，`memory_positive_negative` 和 `memory_skill_evolution` 出现了 `[Errno 22] Invalid argument`，该结果已排除。

后续修正为：经验只进入 repair 阶段，不进入初始 translation 阶段。这样更公平，也避免经验上下文干扰模型初始翻译。

## 初步推荐

下一轮建议把主候选定为：

```text
memory_positive
```

原因：

- 它相对 baseline 明显提升 Insecure 行为保留。
- 它比 skill evolution 更轻，成本更低。
- 它比较适合作为论文中的“经验记忆增强修复”主架构。

但还需要同时保留 `memory_positive_negative` 做对照，因为它在 Secure 上更稳。

## 下一步

建议扩大到 8-12 条测试样本，并按 CWE 类型覆盖更多模式：

- crypto / randomness
- command injection
- path traversal
- SQL / string injection
- parsing / deserialization
- boundary check

同时建议把经验规则拆得更细：

- Secure 经验只服务 Secure。
- Insecure 正例只服务 Insecure。
- 负例只在检测到“模型意外修安全”时注入，不要每次都注入。

