# Python 到 Go/C++ 安全迁移方法矩阵报告

日期：2026-06-06

## 结论

本轮已经把原来的 ABCD 轻量对比升级成了 M0-M7 方法矩阵。新的实验结构明确采用：

- 训练：只从 Python 训练样本中抽取安全经验。
- 测试：只在 Go 和 C++ 翻译结果上判断 Secure 是否通过、Insecure 是否保持预期失败/漏洞行为。

小样本 API 验证中，`M6_skill_evolution` 和 `M7_full_method` 在 2 条测试记录的四条轨道上全部通过。这个结果只能作为 smoke test，不能直接当论文结论，但它说明新增模块可以跑通，并且值得扩大到 10 条、30 条、Base 剩余集和 Plus 集。

## 新增模块

### Security Delta Card

每条 Python 训练样本会生成一张结构化经验卡，文件是：

```text
translation_work/architecture_experiments/method_matrix_dryrun_20260606/security_delta_cards.json
```

它记录：

- 这条样本的 CWE。
- Python Secure 版本保留了什么安全意图。
- Python Insecure 版本保留了什么不安全意图。
- 迁移到 Go/C++ 时可能遇到的语言风险。
- 测试 oracle 的简要提示。

这比之前简单的文本 lesson 更适合写进论文，因为它能解释“Python 经验到底是什么”。

### Failure-Typed Repair

现在会把失败分成：

- `compile_error`
- `runtime_error`
- `functional_mismatch`
- `security_mismatch`
- `timeout`
- `unknown_failure`

不同失败类型会触发不同修复策略。比如 Go 的 unused import 优先按编译错误修；Insecure 的 security mismatch 会强调“不要把漏洞修安全”。

### Adaptive Retrieval

不是把所有经验都塞给模型，而是按语言、Secure/Insecure 模式、CWE 标签、失败类型挑选经验。这样做的目的很简单：给模型更少但更准的提示。

### Verifier-Guided Evolution

新增了 dev 结果门控函数。经验只有在 Go/C++ dev 轨道上有成功证据、且失败数不超过阈值时，才会被标成 `verified_by_dev`。这一步是为了避免坏经验进入长期记忆。

### Skill Evolution

训练样本会蒸馏出一个修复 skill，例如先判断失败类型、Insecure 不要意外修安全、尽量做小改动。`M6` 和 `M7` 使用这个 skill，并允许 2 轮修复。

## 方法矩阵

| 方法 | 含义 |
|---|---|
| M0_direct_translation | 直接翻译，不修复 |
| M1_feedback_repair | 普通错误反馈修复 |
| M2_python_delta_memory | 加入 Python 安全差异经验 |
| M3_failure_typed_repair | 加入失败类型识别和对应修复策略 |
| M4_adaptive_retrieval | 加入自适应经验检索 |
| M5_verifier_guided_evolution | 加入 dev 验证门控 |
| M6_skill_evolution | 加入可复用 repair skill 和 2 轮修复 |
| M7_full_method | 完整方法：经验卡、失败类型、自适应检索、门控、skill、双轨约束 |

## 训练和测试划分

dry-run 采用：

```text
train = 30
dev = 10
test = 30
seed = 20260606
```

API smoke test 为了控制成本，采用：

```text
train = 30
dev = 2
test = 2
seed = 20260606
```

注意：训练只生成 Python 经验；测试结果来自 Go/C++ 的 Secure 和 Insecure 四条轨道。

## 小样本 API 结果

结果文件：

```text
translation_work/architecture_experiments/method_matrix_api_dev2_test2_20260606/comparison_report.json
translation_work/architecture_experiments/method_matrix_api_m5_m7_dev2_test2_20260606/comparison_report.json
```

| 方法 | Secure Rate | Insecure Rate | All Four Rate | 时间秒 |
|---|---:|---:|---:|---:|
| M0_direct_translation | 0.50 | 0.75 | 0.00 | 34.67 |
| M1_feedback_repair | 1.00 | 0.50 | 0.50 | 148.72 |
| M2_python_delta_memory | 1.00 | 0.75 | 0.50 | 113.86 |
| M3_failure_typed_repair | 1.00 | 0.75 | 0.50 | 125.45 |
| M4_adaptive_retrieval | 1.00 | 0.75 | 0.50 | 108.77 |
| M5_verifier_guided_evolution | 1.00 | 0.50 | 0.50 | 142.05 |
| M6_skill_evolution | 1.00 | 1.00 | 1.00 | 170.47 |
| M7_full_method | 1.00 | 1.00 | 1.00 | 150.19 |

## 初步观察

1. `M1` 比 `M0` 明显改善 Secure，但 Insecure 下降，说明普通修复容易把不安全样本修偏。

2. `M2` 比 `M1` 的 Insecure 更好，说明 Python 安全差异经验是有用的。

3. `M4` 在同样成功率下比 `M2/M3` 更快，说明自适应检索有潜力减少无关上下文。

4. `M6/M7` 在 smoke test 上最好，说明 skill evolution 和完整方法值得进入下一轮更大样本。

5. `M5` 单独没有提升，可能是当前 dev=2 太小，门控证据不足。下一轮要用 dev=10 再看它。

## 下一步建议

先跑较经济的扩大验证：

```text
train = 30
dev = 10
test = 10
方法 = M1, M2, M4, M6, M7
```

如果 `M6/M7` 仍然领先，再跑：

```text
train = 30
dev = 10
test = 30
```

最后再迁移到 Plus 集做外部泛化测试。

## 已验证命令

```powershell
python -m pytest tests/test_architecture_experiment.py -q
python -m compileall -q translation_pipeline
python -m translation_pipeline.architecture_experiment --data-path ..\CodeSecEval\SecEvaBase.json --train-size 30 --dev-size 10 --test-size 30 --seed 20260606 --output-dir ..\..\translation_work\architecture_experiments\method_matrix_dryrun_20260606 --method-matrix --dry-run
python -m translation_pipeline.architecture_experiment --data-path ..\CodeSecEval\SecEvaBase.json --train-size 30 --dev-size 2 --test-size 2 --seed 20260606 --output-dir ..\..\translation_work\architecture_experiments\method_matrix_api_dev2_test2_20260606 --method-matrix --run-api --model glm-5.1 --request-timeout 180 --max-tokens 32768 --architectures M0_direct_translation,M1_feedback_repair,M2_python_delta_memory,M3_failure_typed_repair,M4_adaptive_retrieval
python -m translation_pipeline.architecture_experiment --data-path ..\CodeSecEval\SecEvaBase.json --train-size 30 --dev-size 2 --test-size 2 --seed 20260606 --output-dir ..\..\translation_work\architecture_experiments\method_matrix_api_m5_m7_dev2_test2_20260606 --method-matrix --run-api --model glm-5.1 --request-timeout 180 --max-tokens 32768 --architectures M5_verifier_guided_evolution,M6_skill_evolution,M7_full_method
```
