# CodeSecEval AI Translation Pipeline

这个工具用来把 `CodeSecEval` 数据集里的 Python 代码翻译成 C++ 和 Go。

它会处理两份代码：

- `Secure Code`：安全正确版本。翻译后会尽量生成目标语言测试程序，并检查 C++/Go 是否能通过功能测试。
- `Insecure Code`：不安全或错误示范版本。翻译时要求保留原来的不安全行为，不把漏洞修好。验证时目标是让 C++/Go 行为尽量和原 Python 不安全代码一致。

## 工作目录

所有新生成的文件都放在当前项目下面：

```text
D:\thecourceofdasi\safecodernew\translation_work\
```

子目录含义：

- `cache\`：API 调用缓存，避免同一条重复花 token。
- `temp\`：C++/Go 编译和运行时的临时文件。
- `logs\`：后续可放运行日志。
- `outputs\`：生成的新 JSON 文件。
- `downloads\`：新下载依赖或 pip 缓存。

## 先跑小样本

从 `DatasetAndMethod/SecAwareCoder` 目录运行：

```powershell
python -m translation_pipeline.run_translate_dataset `
  --data-path ..\CodeSecEval\SecEvaBase.json `
  --output-path ..\..\translation_work\outputs\SecEvaBase.translated.json `
  --model glm-4.7 `
  --max-workers 4 `
  --limit 5 `
  --request-timeout 180 `
  --max-repair-attempts 2
```

`--limit 5` 的意思是只跑前 5 条，适合先确认 API、编译器和输出格式都没问题。

如果只想先确认“翻译 API 速度”，不想让模型继续生成验证程序，可以加：

```powershell
--skip-validation
```

这样会翻译四份代码，但不会跑 C++/Go 功能验证，速度更容易观察。

如果想先验证 `Secure Code`，但暂时不验证 `Insecure Code` 的错误行为，可以加：

```powershell
--skip-insecure-validation
```

这个适合第二阶段烟雾测试：先确认安全代码功能测试能跑，再单独处理不安全代码行为匹配。

如果反过来只想验证 `Insecure Code`，暂时跳过 `Secure Code` 功能测试，可以加：

```powershell
--skip-secure-validation
```

这个适合检查“不安全错误示范是否被保留”。

## 跑完整数据集

小样本确认后，再跑完整文件：

```powershell
python -m translation_pipeline.run_translate_dataset `
  --data-path ..\CodeSecEval\SecEvaBase.json `
  --output-path ..\..\translation_work\outputs\SecEvaBase.translated.json `
  --model glm-4.7 `
  --max-workers 4 `
  --resume `
  --request-timeout 180 `
  --max-repair-attempts 2
```

```powershell
python -m translation_pipeline.run_translate_dataset `
  --data-path ..\CodeSecEval\SecEvalPlus.json `
  --output-path ..\..\translation_work\outputs\SecEvalPlus.translated.json `
  --model glm-4.7 `
  --max-workers 4 `
  --resume `
  --request-timeout 180 `
  --max-repair-attempts 2
```

`--resume` 表示如果输出文件里已经有某个 `ID`，就跳过它，方便中断后续跑。

## 不调用 API 的检查

如果只想检查程序能不能读写 JSON，不想花 API token，可以加：

```powershell
--skip-api
```

这不会真正翻译，只会生成带空翻译字段的输出文件。

## 防卡住机制

程序会把当前阶段写到：

```text
D:\thecourceofdasi\safecodernew\translation_work\logs\translation_pipeline.log
```

默认每个 API 请求最多等待 180 秒。某个字段失败时，会把错误写进对应结果字段，不会让整条记录完全丢失。

## 清理临时文件

如果只是想清理编译产生的临时文件，可以删除：

```text
D:\thecourceofdasi\safecodernew\translation_work\temp\
```

建议保留：

- `translation_work\outputs\`
- `translation_work\cache\`
- `translation_work\logs\`

因为输出结果、API 缓存和日志后续还有用。

