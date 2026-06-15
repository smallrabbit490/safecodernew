import os
from pydantic import BaseModel, Field
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig


class CG_Configuration(BaseModel):
    """The configuration for code generation."""

    model_name: str = Field(
        default="gpt-4o-mini",
        metadata={"description": "Default LLM to use when CG_State.model_name is empty."},
    )
    temperature: float = Field(
        default=0.0,
        metadata={"description": "Sampling temperature for all LLM calls."},
    )
    max_length: int = Field(
        default=128000,
        metadata={"description": "Maximum supported length of the model"},
    )
    max_tokens: int = Field(
        default=2048,
        metadata={"description": "Maximum number of tokens to generate."},
    )
    top_p: float = Field(
        default=1.0,
        metadata={"description": "Top-p (nucleus) sampling parameter."},
    )
    target_language: str = Field(
        default="python",
        metadata={"description": "Target programming language for code generation."},
    )
    limits_by_lang: dict[str, int] = Field(
        default_factory=lambda: {
            "cpu": 2,          # CPU time in seconds
            "nofile": 1,
            "nproc": 1,      # Number of processes
            "_as": 512 * 1024 * 1024,    # Address space in bytes (512 MB)
        },
        metadata={
            "description": "Resource limits for code execution."
        },
    )
    max_repair_attempts: int = Field(
        default=2,
        metadata={"description": "Maximum number of repair attempts for code generation."},
    )
    security_mode: str = Field(
        default="single",
        metadata={
            "description": "Security risk handling mode: "
                           "'single' - address one risk at a time until tests pass; "
                           "'all' - address all identified risks at once."
        },
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "CG_Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)

class CT_Configuration(BaseModel):
    """The configuration for code generation."""

    model_name: str = Field(
        default="gpt-4o-mini",
        metadata={"description": "Default LLM to use when CT_State.model_name is empty."},
    )
    temperature: float = Field(
        default=0.0,
        metadata={"description": "Sampling temperature for all LLM calls."},
    )
    max_length: int = Field(
        default=128000,
        metadata={"description": "Maximum supported length of the model"},
    )
    max_tokens: int = Field(
        default=2048,
        metadata={"description": "Maximum number of tokens to generate."},
    )
    top_p: float = Field(
        default=1.0,
        metadata={"description": "Top-p (nucleus) sampling parameter."},
    )
    source_language: str = Field(
        default="java",
        metadata={"description": "Source programming language for code translation."},
    )
    target_language: str = Field(
        default="js",
        metadata={"description": "Target programming language for code translation."},
    )
    limits_by_lang: dict[str, int] = Field(
        default_factory=lambda: {
            "cpu": 2,          # CPU time in seconds
            "nofile": 1,
            "nproc": 1,      # Number of processes
            "_as": 512 * 1024 * 1024,    # Address space in bytes (512 MB)
        },
        metadata={
            "description": "Resource limits for code execution."
        },
    )
    max_repair_attempts: int = Field(
        default=2,
        metadata={"description": "Maximum number of repair attempts for code generation."},
    )
    

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "CT_Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)