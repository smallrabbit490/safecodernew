# SecEvo BasePlus

这个文件夹整理当前项目使用的五种语言 SecEvo Base/Plus 数据集。

## 目录结构

```text
SecEvoBasePlus/
├─ Base/
│  ├─ Python_Base.json
│  ├─ Cpp_Base.json
│  ├─ Go_Base.json
│  ├─ Java_Base.json
│  └─ JS_Base.json
├─ Plus/
│  ├─ Python_Plus.json
│  ├─ Cpp_Plus.json
│  ├─ Go_Plus.json
│  ├─ Java_Plus.json
│  └─ JS_Plus.json
└─ manifest.json
```

## 数据来源

- Python：`DatasetAndMethod/CodeSecEval/SecEvaBase.json` 和 `SecEvalPlus.json`
- C++ / Go：`translation_work/outputs` 中已经验证和人工补全后的最终文件
- Java / JavaScript：`datasets.zip` 解压得到的 `Base` 和 `Plus` 数据

## 条数说明

- Python Base：115 条
- C++ Base：115 条
- Go Base：115 条
- Java Base：116 条
- JavaScript Base：116 条
- 五种语言 Plus：均为 140 条

Java/JavaScript Base 为 116 条是 `datasets.zip` 自带文件的实际条数；Python/C++/Go Base 为 115 条，保持原始 CodeSecEval/SecEvaBase 的数量。

## 字段说明

- Python 文件保留原始 CodeSecEval 字段。
- C++ / Go 文件已拆成单语言文件，统一使用 `Secure Code` 和 `Insecure Code` 保存对应语言代码，同时保留 Python 源代码字段作为来源参考。
- Java / JavaScript 文件保留 zip 内原始字段，如 `Function Test` 和 `Secure Test`。

## Java / JavaScript Docker 校验说明

`docker_validate_java_js/` 会对每条样本做 4 次验证：

1. `Secure Code` + `Function Test`
2. `Secure Code` + `Secure Test`
3. `Insecure Code` + `Function Test`
4. `Insecure Code` + `Secure Test`

判定很直接：

- Secure：前两项都要过
- Insecure：功能测试要过，但安全测试要失败

Java 样本里很多测试文件本身已经带 `check()`，所以验证器会把候选实现和测试里的 `check()` 合到一起，再统一跑 `Runner.main()`。
JS 样本则用 `vm` 和 CommonJS 包装，避免 `module.exports`、`require()`、重复声明这些常见冲突。
