# 方法矩阵 test=10 放大样本报告

日期：2026-06-07

## 结论

这次按你的要求把测试样本从 `test=2` 放大到了 `test=10`，同时把 dev 也从 `dev=2` 放大到了 `dev=10`。新的实验设置是：

```text
train = 30
dev = 10
test = 10
seed = 20260606
```

结论有变化：之前 `test=2` 时 `M6_skill_evolution` 和 `M7_full_method` 都是四轨全过，看起来非常强；但放大到 `test=10` 后，它们不再满分。也就是说，`test=2` 确实太小，会把结果看得过于乐观。

## 有效结果

本轮有效结果来自这些文件：

```text
translation_work/architecture_experiments/method_matrix_api_dev10_test10_key5_20260607/comparison_report.json
translation_work/architecture_experiments/method_matrix_api_dev10_test10_m6_only_20260607/comparison_report.json
translation_work/architecture_experiments/method_matrix_api_dev10_test10_m7_only_20260607/comparison_report.json
```

注意：`method_matrix_api_dev10_test10_key5_20260607` 中的 `M6/M7` 是一次无效混跑结果，出现了批量 `[Errno 22] Invalid argument`，所以不用于最终结论。后来已经把 `M6` 和 `M7` 单独重跑，得到有效结果。

| 方法 | Records | Secure Rate | Insecure Rate | All Four Rate | 时间秒 |
|---|---:|---:|---:|---:|---:|
| M1_feedback_repair | 10 | 0.70 | 0.60 | 0.20 | 1719.97 |
| M2_python_delta_memory | 10 | 0.80 | 0.70 | 0.20 | 807.05 |
| M4_adaptive_retrieval | 10 | 0.85 | 0.65 | 0.50 | 1011.39 |
| M6_skill_evolution | 10 | 0.80 | 0.70 | 0.50 | 1293.30 |
| M7_full_method | 10 | 0.80 | 0.80 | 0.40 | 1353.22 |

## 和 test=2 的对比

| 方法 | test=2 All Four | test=10 All Four | 变化 |
|---|---:|---:|---|
| M1_feedback_repair | 0.50 | 0.20 | 明显下降 |
| M2_python_delta_memory | 0.50 | 0.20 | 明显下降 |
| M4_adaptive_retrieval | 0.50 | 0.50 | 保持稳定 |
| M6_skill_evolution | 1.00 | 0.50 | 从满分回落 |
| M7_full_method | 1.00 | 0.40 | 从满分回落 |

这个变化说明：`test=2` 的结果不能支撑论文结论，`test=10` 更能暴露方法差异。

## 观察

1. `M1` 普通反馈修复变弱了。

   它在 `test=10` 下 All Four 只有 `0.20`。这说明只靠“错误反馈再修一次”，在更多 CWE 上不够稳定。

2. `M2` 的 Python 经验确实有帮助，但还不够。

   它的 Secure/Insecure rate 比 M1 都高一些，但 All Four 仍然只有 `0.20`。也就是说，单纯把 Python 经验塞进去，不一定能让同一条样本的四条轨道都过。

3. `M4` 是目前最稳定的候选之一。

   它的 Secure rate 最高：`0.85`，All Four 也是最高并列：`0.50`。这说明“自适应检索”比直接给经验更可靠。

4. `M6` 和 `M4` 的 All Four 持平。

   `M6` 加了 skill evolution 和 2 轮修复，但在 `test=10` 上没有明显超过 M4。它的 Insecure rate 比 M4 高一点，但 Secure rate 低一点。

5. `M7` 的 Insecure 最好，但整体四轨不是最高。

   `M7` 的 Insecure rate 是 `0.80`，说明完整方法更会保留不安全行为。但 All Four 是 `0.40`，低于 M4/M6 的 `0.50`。这说明双轨约束可能增强了 Insecure，但也可能干扰 Secure 或某些具体样本的四轨同时通过。

## 当前推荐

如果现在要选主线方法，不建议直接只选 `M7_full_method`。更稳的论文写法是：

```text
主候选：M4_adaptive_retrieval 或 M6_skill_evolution
重点分析：M7_full_method 为什么 Insecure 更好但 All Four 略低
```

原因是：

- `M4` 更轻，速度比 M6/M7 快，All Four 最高并列。
- `M6` 有自进化味道，也保持了 All Four 最高并列。
- `M7` 有研究亮点，但需要继续调双轨约束，否则可能不是总分最优。

## 下一步

建议下一轮不要再只看 2 条或 10 条。可以跑：

```text
train = 30
dev = 10
test = 30
方法 = M4, M6, M7
```

这样成本比全跑 M0-M7 低，但能验证三个最有希望的方法在更大样本上是否稳定。

## 已验证

单元测试：

```text
python -m pytest tests/test_architecture_experiment.py -q
15 passed in 0.75s
```

有效 API 实验：

```text
M1/M2/M4: method_matrix_api_dev10_test10_key5_20260607
M6: method_matrix_api_dev10_test10_m6_only_20260607
M7: method_matrix_api_dev10_test10_m7_only_20260607
```
