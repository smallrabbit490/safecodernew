# LLM 经验摘取与自进化更新实验说明

更新时间：2026-06-14

## 1. 这次做了什么

这次把经验学习从“脚本抽 diff”升级成“让大模型总结泛化规则”。

整体流程是：

```text
100 条 SeCodePLT 成对样本
  -> GLM 5.1 总结泛化安全经验
  -> 用这套经验跑 30 条 CodeSecEval 测试
  -> 读取失败案例
  -> GLM 5.1 总结新的泛化规则
  -> 更新记忆库
  -> 再跑同一批 30 条测试
```

这里的“泛化”要求是：规则不能写成某个具体 CWE、某个题号、某个文件名，而要写成通用的代码生成原则。

## 2. 三类经验的区别

| 经验类型 | 怎么来的 | 特点 | 风险 |
|---|---|---|---|
| 旧脚本经验 | 脚本读取 pair，保留 CWE、policy、diff 和手写通用规则 | 更贴近原始代码变化，信息具体 | 容易依赖样本格式，泛化表达弱 |
| LLM 摘取经验 | 大模型阅读 100 条 pair，总结通用安全规则 | 更像论文里的经验蒸馏，规则更抽象 | 容易太泛，和测试细节脱节 |
| 自进化更新经验 | 大模型阅读失败案例，总结新增泛化规则 | 能从失败中补充规则 | 如果只是长文本追加，生成阶段不一定真正执行 |

## 3. LLM 摘取到了什么经验

大模型总结出的规则包括：

- 正则回溯防护
- 安全反序列化
- URL / 重定向目标白名单
- HTML 输出编码
- 动态执行前做 AST 校验
- 路径规范化和目录约束
- 命令参数化执行
- XML 安全解析
- TLS 证书校验
- 加密安全随机数
- 资源大小限制
- 敏感信息过滤
- 精确 allowlist 匹配
- 授权检查
- CSRF 校验
- 竞争条件防护

这些规则确实比原来的 diff 更“泛化”，更像经验库。

## 4. 自进化阶段新增了什么

自进化阶段读取 LLM 摘取经验版的失败案例，然后新增了 7 条泛化规则：

1. 精确异常类型匹配
2. 保持指定返回格式
3. 对非法输入必须显式拒绝
4. 避免过度安全化影响正常功能
5. 严格遵守题目行为契约
6. 失败后清理副作用
7. 精确执行解析边界

这些规则没有绑定具体 CWE，而是围绕通用失败模式展开，符合“泛化更新”的要求。

## 5. 测试结果

同一批 30 条 CodeSecEval Plus 测试结果如下：

| 方法 | Func+Sec |
|---|---:|
| NoMemory | 15/30 |
| 旧脚本 SeCodePLT 经验 v3 | 16/30 |
| 旧 CodeSecEval 经验 v3 | 16/30 |
| LLM 摘取 SeCodePLT 经验 v1 | 14/30 |
| LLM 自进化更新后 v1 | 15/30 |
| LLM 摘取 SeCodePLT 经验 v2 | 15/30 |
| LLM 自进化更新后 v2 | 15/30 |

## 6. 结果怎么解释

这次结果说明：

1. 大模型确实能总结出更泛化的安全经验。
2. 但“泛化经验”直接作为长文本提示，不一定比脚本经验更有效。
3. 自进化更新确实产生了有意义的新规则，但还没有在分数上带来提升。
4. 当前瓶颈不是“有没有规则”，而是“生成阶段能不能强制执行这些规则”。

对新手来说，可以这样理解：

```text
大模型已经写出了更好的错题总结，
但考试时学生只是看了一眼很长的总结，
不一定每道题都真的按总结执行。
```

## 7. 为什么没有明显提升

主要原因有三个：

1. LLM 摘取的规则太泛，比如“路径要规范化”“命令要参数化”，但 CodeSecEval 测试还会卡具体异常类型、返回格式和文件副作用。
2. 记忆库直接作为长文本进入 prompt，规则之间会互相稀释。
3. 自进化新增规则虽然正确，但没有变成硬约束或检查清单，所以生成时仍可能忘记执行。

## 8. 下一步建议

下一步应该把“记忆”从长文本改成可执行的生成前检查表：

```text
当前任务
  -> 检索 3-5 条相关规则
  -> 生成前生成 contract checklist
  -> 代码生成
  -> 生成后自检：
       是否满足返回格式？
       是否使用正确异常？
       是否有资源清理？
       是否过度安全化？
  -> 再运行测试
```

也就是说，LLM 经验更适合当“规则库 + checklist”，不适合直接当大段背景材料。

## 9. 产物位置

LLM 经验实验脚本：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\run_llm_memory_experiment.py
```

LLM v2 报告：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\llm_v2\report.md
```

LLM 摘取规则：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\llm_v2\memory\llm_distilled_rules.json
```

自进化更新规则：

```text
D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment\out\llm_v2\memory\llm_evolved_updates.json
```
