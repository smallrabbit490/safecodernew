# Coset Eagle 过拟合分析与 clean 重跑报告

更新时间：2026-06-15

## 1. 先说结论

上一版 `Coset Eagle` 的高分确实有明显过拟合风险。

原因不是“用了 checklist”本身，而是 checklist 里混进了**题目级测试信息**，包括：

- `Task["Test"]` 原文
- `assert_raises` 里的预期异常类型
- 具体权限模式，比如 `0o700`
- repair 阶段的 test_result

这些信息让模型在生成时更接近“对着测试写答案”，而不是“只根据题面和通用经验生成代码”。

## 2. 哪些地方过拟合了

### 2.1 最明显的泄漏点

`run_coset_eagle_experiment.py` 里，原版 `coset_eagle` 把下面这些都放进了 prompt / repair：

- `Functional and security tests used for evaluation`
- `Checklist` 中直接提取的 `expected_error_groups`
- `expected_permission_modes`
- `test_result`

这意味着模型在某些题上实际上看到了接近答案的测试约束。

### 2.2 为什么这是问题

因为最终评估本来就是要检验模型能不能从：

```text
题目说明 + 训练经验
```

推导出正确安全代码。

如果把最终测试细节直接塞进去，就不再是这个问题，而变成：

```text
题目说明 + 训练经验 + 测试答案线索
```

这会让分数虚高，论文里站不住。

## 3. clean 版本怎么改

我新增了一个不泄漏测试的版本：

```text
coset_eagle_clean
```

对应代码仍在同一个脚本里，但它：

- 不读取 `Test` 原文进入 prompt；
- 不把 `assert_raises` 和预期异常组作为 checklist 目标；
- 不把 `test_result` 传给 repair；
- 只保留通用的任务契约和泛化安全规则。

## 4. 两个版本的对比

### 4.1 leaky 版本

`coset_eagle` 在 30 条测试上的结果：

- `28/30`
- `93.33%`

### 4.2 clean 版本

`coset_eagle_clean` 在同样 30 条测试上的结果：

- `10/30`
- `33.33%`

这个落差非常大，说明上一版性能里有不少是靠题目级测试信息撑起来的。

## 5. clean 版的失败类型

clean 版失败主要是：

- `assertion_mismatch: 16`
- `permission_or_auth: 1`
- `other: 3`

这说明：

1. 去掉测试信息后，模型很难稳定猜到具体契约；
2. 仅靠泛化经验还不够，特别是在“异常类型/返回格式/边界行为”这类题上；
3. 过度依赖测试信息，确实会让结果看起来很好，但不代表方法真强。

## 6. 这说明了什么

对论文来说，最重要的不是“能不能跑出高分”，而是：

1. 结果是否公平；
2. 方法是否真的泛化；
3. 有没有泄漏评估答案。

这次 clean 重跑说明：

- `test-level checklist` 不适合放进最终方法；
- 保留下来的应该是更泛化的 contract checklist；
- 自检器应该检查“代码有没有明显违反题面”和“有没有常见安全问题”，而不是直接读取测试答案。

## 7. 建议保留的结构

更稳的结构应该是：

```text
LLM memory
  -> 泛化 contract checklist
  -> 生成
  -> 泛化 self-check
  -> 修复
  -> 沙盒测试
```

不要再把：

- `Test`
- `assert_raises`
- `expected_permission_modes`
- `test_result`

放进最终方法。

## 8. 当前实验文件

- 原版完整结果：`out/coset_eagle_full_v3/`
- clean 完整结果：`out/coset_eagle_clean_full_v1/`
- clean 脚本：`run_coset_eagle_experiment.py`
- clean 防泄漏单测：`test_coset_eagle_experiment.py`

## 9. 最后一句话

这次重跑已经证明：**之前的高分是有过拟合成分的**。  
如果要做论文，就应该以 clean 版为准，再在这个基础上继续增强泛化规则，而不是继续用测试级信息把分数“顶上去”。
