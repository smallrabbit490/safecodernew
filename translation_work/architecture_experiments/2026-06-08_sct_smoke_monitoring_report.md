# SCT-Agent 小并发验证监控报告

日期：2026-06-08

## 运行目的

这次不是做论文主结果，而是做一个低成本 smoke test：

1. 验证智谱 `glm-5.1` key 是否可用。
2. 用低并发观察现有 M4/M7 流程是否能正常跑完。
3. 用监控结果反推 SCT-Agent 还需要优化哪里。

## 运行配置

API 测试：

```text
model = glm-5.1
prompt = 只回答OK
result = OK
```

说明：智谱 key 可用。

小并发实验：

```text
并发 = 2
方法 = M4_adaptive_retrieval, M7_full_method
train_size = 4
dev_size = 1
test_size = 1
seed = 20260608
test record = CWE-434_pearce_2.py
request_timeout = 180
max_tokens = 8192
```

日志目录：

```text
translation_work/logs/sct_smoke_20260608_022104
```

结果目录：

```text
translation_work/architecture_experiments/sct_smoke_api_20260608_022104
```

## 监控过程

两个进程均正常启动，日志显示它们按顺序完成：

```text
Secure Code -> C++
Insecure Code -> C++
Secure Code -> Go
Insecure Code -> Go
```

两个任务都跑完并写出：

```text
comparison_report.json
*.records.json
*.summary.json
```

没有发现 key 失效或 API 拒绝。

## 结果

### M4_adaptive_retrieval

```text
records = 1
secure_cpp_ok = 0
secure_go_ok = 0
insecure_cpp_ok = 1
insecure_go_ok = 0
all_four_ok = 0
elapsed_seconds = 322.92
```

### M7_full_method

```text
records = 1
secure_cpp_ok = 0
secure_go_ok = 0
insecure_cpp_ok = 1
insecure_go_ok = 0
all_four_ok = 0
elapsed_seconds = 368.28
```

解释给新手：

```text
这条样本上，M4 和 M7 都只把 Insecure C++ 做对了。
安全版本 C++、安全版本 Go、不安全版本 Go 都没有成功。
```

## SCT 诊断结果

诊断输出：

```text
translation_work/architecture_experiments/sct_smoke_api_20260608_022104/smoke_diagnostics.json
```

### 失败类型

M4 和 M7 的失败类型一致：

```text
runtime_error = 3
失败轨道 = secure_cpp, secure_go, insecure_go
```

这说明这条 CWE-434 样本不是简单编译错误，而是运行行为和测试预期没有对齐。

### Paired Outcome

C++ pair：

```text
category = insecure_only
action = repair_secure
```

意思是：

```text
Insecure C++ 已经符合预期，但 Secure C++ 没有通过。
下一步应该只修 Secure C++，不能动 Insecure C++。
```

Go pair：

```text
category = both_fail
diff_preserved = false
action = repair_both
```

意思是：

```text
Go 的 Secure 和 Insecure 都失败了，
而且 Secure/Insecure 差异也塌缩了。
下一步 Go 需要双边重修，并且必须显式保持安全差异。
```

### Security Delta IR

规则版 IR 对 Python 原始差异的判断是：

```text
Python secure/insecure security shape is weakly separated.
```

这说明当前规则版 IR 对 CWE-434 这种上传类漏洞不够敏感。

它只看到了 `path`，没有清楚抽出：

```text
文件扩展名检查
上传路径限制
危险文件类型阻断
```

这正好说明：论文里不能只靠规则版 IR，真实 SCT-Agent 应该用：

```text
规则 IR + LLM/schema IR + 人工抽样校验
```

## 反推优化点

### 优化 1：Security Delta IR 要覆盖 CWE-434

当前关键词偏向 command/path/crypto/parsing，不能很好识别文件上传安全差异。

建议加入：

```text
upload
filename
extension
mime
content_type
allowed_extensions
secure_filename
file size
path traversal
```

论文好点子：

```text
Security Delta IR 不是通用关键词，而是 CWE-aware schema。
每类 CWE 有自己的安全差异槽位。
```

### 优化 2：Paired Repair Action 应进入真实 repair prompt

这次诊断已经能给出动作：

```text
C++: repair_secure
Go: repair_both
```

但当前 M4/M7 真实 API 流程还没有使用这个动作计划。

下一步应该实现：

```text
把 paired_repair_actions + repair_policy + security_delta_ir 拼进 repair prompt。
```

这样模型不会盲目重写，而是知道：

```text
C++ 只修 Secure，不要破坏已经正确的 Insecure。
Go 两边都修，并且必须重新拉开 Secure/Insecure 差异。
```

### 优化 3：Go 需要更强的 delta-preserving prompt

Go 的结果是：

```text
both_fail + diff_preserved=false
```

说明 Go 仍然是重点难点。

建议在 Go prompt 中加入更强要求：

```text
Secure Go must implement the secure guard.
Insecure Go must intentionally omit the guard.
Do not let the two versions converge to the same implementation.
```

### 优化 4：小样本验证要选“失败动作样本”，不是随机样本

这次随机到 `CWE-434_pearce_2.py`，虽然失败多，但很有诊断价值。

下一轮建议直接选已有诊断中带这些动作的样本：

```text
repair_delta
repair_insecure
repair_secure
repair_both
```

每类 1-2 条，比随机 test=1 更能验证 SCT-Agent 的价值。

## 写论文的好点子

### 点子 1：把 Insecure 的正确性讲成 “negative behavioral fidelity”

可以这样表述：

```text
Insecure code is not evaluated by normal correctness, but by negative behavioral fidelity:
it should preserve the intended vulnerable behavior of the source insecure program.
```

中文解释：

```text
不安全代码不是越安全越好，而是要忠实保留原始错误示范。
```

### 点子 2：把 Paired Oracle 讲成双轨一致性验证

普通验证只看单段代码。我们的验证看：

```text
Secure 和 Insecure 是否同时对，
以及二者之间的安全差异是否还在。
```

这能解释为什么 `both_ok` 还不一定够：

```text
如果 both_ok 但 diff_preserved=false，说明它们可能都过了测试，但安全差异塌缩了。
```

### 点子 3：把 Failure Atlas 写成 self-evolution 的核心，而不是附属日志

不要写成：

```text
我们记录失败日志。
```

要写成：

```text
We maintain an evidence-gated failure atlas that promotes only repair rules that improve paired transfer without causing regressions.
```

### 点子 4：用这次 smoke 作为 motivation case

`CWE-434_pearce_2.py` 可以作为论文里的一个 motivating example：

- Insecure C++ 成功。
- Secure C++ 失败。
- Go 双边失败。
- Go diff collapse。
- 规则 IR 无法识别文件上传安全差异。

这能自然引出：

```text
CWE-aware Security Delta IR
Paired Oracle
Risk-Budgeted Repair
```

## 下一步建议

优先级从高到低：

1. 扩展 Security Delta IR，加入 CWE-434/upload 类安全槽位。
2. 实现 `SCT-Agent-lite repair prompt`，输入包含：
   - security_delta_ir
   - paired_repair_action
   - repair_policy
   - previous error report
3. 选 6-8 条失败动作样本，小并发 2 运行。
4. 统计：
   - action success rate
   - false secure rate
   - repair drift rate
   - code growth ratio
5. 再决定是否扩到 test=30。

## 当前结论

```text
智谱 API 可用；
小并发流程可以正常跑完；
M4/M7 在这条 CWE-434 上都失败较多；
诊断组件能给出明确下一步修复动作；
当前最值得优化的是 CWE-aware Security Delta IR 和 action-guided repair prompt。
```
