# SeCodePLT 经验迁移扩展实验说明

更新时间：2026-06-14

## 1. 先说结论

这轮实验把 SeCodePLT 的训练样本从 30 条扩展到 100 条，并把 CodeSecEval 的测试从 10 条扩展到 30 条。结果说明：

- SeCodePLT 是有用的，但前提是把经验压成更通用的安全规则，并且按当前题目动态检索相关经验。
- 直接把一大段原始经验塞给模型，效果不稳定。
- 均衡抽样后的 SeCodePLT 经验，比 NoMemory 略好，但没有 v2 那种偏置抽样下的强提升。

## 2. 为什么上轮 SeCodePLT 看起来和 NoMemory 一样

上轮效果像 NoMemory，主要有三个原因：

1. 训练样本太少，只有 30 条，覆盖面不够广。
2. 经验内容太长，直接整段放进 prompt，容易稀释真正有用的规则。
3. 经验和测试题的 CWE 不完全重叠，很多题需要的是异常类型、返回格式、目录约束等更细的行为，而不是泛泛的“安全修复”。

## 3. 这轮怎么修

我做了两件事：

### 3.1 扩大 SeCodePLT 训练到 100 条

而且不是单纯追加，而是做了均衡抽样，尽量让不同 CWE 都有样本，避免某个 CWE 占太多。

### 3.2 把经验改成“通用规则 + 检索到的样本”

不再把 100 条原始经验整段塞入 prompt，而是：

- 先根据题目识别 CWE 和关键词
- 再挑最相关的 3-5 条 SeCodePLT 经验
- 同时加入一些通用规则，比如路径约束、HTML 转义、命令注入防护、反序列化阻断、权限控制

这样更像真正可用的经验库。

## 4. 三组测试结果

测试集：30 条 CodeSecEval Plus。

主结果采用 v3：SeCodePLT 100 条训练样本做均衡抽样，测试 30 条 CodeSecEval Plus。

| 方法 | 功能通过 | 安全通过 | 功能+安全同时通过 |
|---|---:|---:|---:|
| SeCodePLT 新经验 | 27/30 | 16/30 | 16/30 |
| CodeSecEval 旧经验 | 26/30 | 17/30 | 16/30 |
| NoMemory | 28/30 | 15/30 | 15/30 |

这里最重要的是最后一列：功能和安全同时通过才算真正成功。

## 5. 具体怎么解释

### v2

v2 的 SeCodePLT 结果最好，`21/30`，明显高于 CodeSecEval 旧经验的 `17/30` 和 NoMemory 的 `13/30`。这说明：

- SeCodePLT 本身确实有迁移价值。
- 如果训练分布和检索偏向它擅长的漏洞类型，它能明显超过 NoMemory。

### v3

v3 改成更均衡的抽样后，SeCodePLT 结果回落到 `16/30`，和 CodeSecEval 旧经验持平，略高于 NoMemory 的 `15/30`。说明：

- SeCodePLT 的通用安全规则是有帮助的；
- 但它不是万能的，不能替代 CodeSecEval 风格经验。
- 如果训练样本太“平均”，反而可能削弱某些和 CodeSecEval 测试集更接近的局部经验。

## 6. 失败原因总结

失败主要集中在这些地方：

- 某些任务要求非常特定的异常类型，模型写对了逻辑，但异常不对。
- 某些任务是文件/数据库/脚本写入场景，必须同时照顾功能、路径和平台行为。
- 有些题需要“保留错误行为”，而安全经验会倾向于把它修得过头。

## 7. 对“为什么之前完全没效果”的最终判断

之前 SeCodePLT 和 NoMemory 都是 `5/10`，不是因为 SeCodePLT 没有安全知识，而是因为使用方式太粗：

1. 30 条训练样本太少，覆盖不到足够多的 CWE。
2. 原始 diff 直接塞进 prompt，不等于模型真的会用。
3. 没有按当前题目检索相关经验，导致很多无关经验干扰生成。
4. CodeSecEval 的测试会卡具体异常类型和返回格式，而 SeCodePLT 更偏通用修复策略。

这次改成 100 条经验、通用规则、Top-K 检索后，SeCodePLT 至少能超过 NoMemory，说明问题在“经验使用方式”，不在“数据完全无效”。

## 8. 现在的更稳结论

SeCodePLT 可以作为外部经验来源，但更适合做成：

- 统一安全规则卡
- 按 CWE 和题目关键词检索的经验池
- 再配合 CodeSecEval 风格经验做最终生成

也就是说，SeCodePLT 不是没用，而是要“学成规则”，不能“整段照搬”。

## 9. 产物位置

实验脚本：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\run_experiment.py
```

v3 主结果目录：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\v3
```

v3 总报告：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\v3\report.md
```

v3 三组逐题结果：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\v3\runs\secodeplt_memory\results.jsonl
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\v3\runs\codeseceval_memory\results.jsonl
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\v3\runs\no_memory\results.jsonl
```
