from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranslationResult:
    code: str
    language: str
    source_field: str
    model: str
    attempts: int = 1
    error: str | None = None


@dataclass
class ValidationResult:
    ok: bool
    language: str
    mode: str
    stdout: str = ""
    stderr: str = ""
    details: dict[str, Any] = field(default_factory=dict)
