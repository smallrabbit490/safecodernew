import json
import os
import logging
import tiktoken
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def format_log_message(message: str) -> str:
    """Format a log message with visual separators."""
    separator = "=" * 50
    return f"\n{separator}\n{message}\n{separator}"


def setup_openai_api(model_name: str) -> dict:
    """
    Setup API credentials based on model name.

    Supported models:
    - gpt-*: OpenAI
    - glm-*, codegeex-*: Zhipu
    - claude-*: Anthropic
    - deepseek-*: DeepSeek
    - moonshot-*: Moonshot
    - qwen-*: Qwen
    - gemini-*: Google

    Returns:
        dict with 'api_key' and 'api_base'
    """
    model_name = model_name.lower()
    api_key, api_base = None, None

    if model_name.startswith("gpt"):
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")


    elif model_name.startswith("glm") or model_name.startswith("codegeex"):
        api_key = os.getenv("ZHIPU_API_KEY")
        api_base = os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")


    elif model_name.startswith("claude"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        api_base = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com")


    elif model_name.startswith("deepseek"):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")


    elif model_name.startswith("moonshot"):
        api_key = os.getenv("MOONSHOT_API_KEY")
        api_base = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")


    elif model_name.startswith("qwen"):
        api_key = os.getenv("QWEN_API_KEY")
        api_base = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")

 
    elif model_name.startswith("gemini"):
        api_key = os.getenv("GOOGLE_API_KEY")
        api_base = os.getenv("GOOGLE_API_BASE", "https://generativelanguage.googleapis.com/v1beta")

    else:
        raise ValueError(f"Unrecognized model prefix: {model_name}.")

    # 检查是否缺少配置
    if not api_key:
        raise ValueError(
            f"Missing API key for model '{model_name}'. "
            f"Please set the corresponding environment variable in .env file."
        )

    logger.debug(f"Using API base: {api_base} for model {model_name}")

    return {
        "api_key": api_key,
        "api_base": api_base,
    }


def num_tokens_from_string(string: str, model_name: str = "gpt-4o-mini") -> int:
    """Returns the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(string))


def trunc_prompt(prompt: str, model_name: str, max_length: int, max_tokens: int) -> str:
    """Truncate prompt if it exceeds the maximum length."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = num_tokens_from_string(prompt, model_name)
    if num_tokens > max_length:
        logger.warning(
            f"Prompt length {num_tokens} exceeds {max_length} token limit, truncating to {max_length}"
        )
        prompt = encoding.encode(prompt)[: max_length - max_tokens]
        prompt = encoding.decode(prompt)
    return prompt


def track_llm_stats(*args, **kwargs):
    """Placeholder for LLM stats tracking (not implemented)."""
    pass


def should_disable_reasoning(model_name: str) -> bool:
    """
    Check if the model should have reasoning disabled.

    Returns True for models that have reasoning capabilities that should be disabled.
    """
    model_lower = model_name.lower()

    # Models with reasoning capabilities
    reasoning_models = [
        'o1',           # OpenAI o1 series
        'o3',           # OpenAI o3 series
        'gpt-5',        # GPT-5
        'gemini-3',     # Gemini 3.x series
        'deepseek',     # DeepSeek models
        'qwen-coder',   # Qwen Coder models
        'claude',       # Claude models with thinking
    ]

    return any(keyword in model_lower for keyword in reasoning_models)


def get_reasoning_disabled_kwargs(model_name: str, max_tokens: int) -> dict:
    """
    Get model_kwargs to disable or minimize reasoning for models that support it.

    Args:
        model_name: The model name
        max_tokens: The max_tokens value to use

    Returns:
        Dictionary of model_kwargs to control reasoning, or empty dict if not needed
    """
    model_lower = model_name.lower()

    # For OpenAI reasoning models
    if 'gpt-5' in model_lower:
        # GPT-5 doesn't support "none", use "low" instead
        return {
            "reasoning_effort": "low",  # Minimize reasoning
            "max_completion_tokens": max_tokens,
        }
    elif any(x in model_lower for x in ['o1', 'o3']):
        # o1 and o3 support "none"
        return {
            "reasoning_effort": "none",  # Disable reasoning
            "max_completion_tokens": max_tokens,
        }

    # For other models through OpenAI-compatible API
    # Most don't support extra reasoning control parameters, so return empty dict
    # The reasoning is controlled by the prompt and temperature instead
    return {}


def create_llm_with_reasoning_control(
    model_name: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    disable_reasoning: bool = True
) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance with unified reasoning control.

    Args:
        model_name: The model name
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        top_p: Top-p sampling parameter
        disable_reasoning: Whether to disable reasoning (default: True)

    Returns:
        Configured ChatOpenAI instance
    """
    api = setup_openai_api(model_name)
    model_lower = model_name.lower()

    # Check if reasoning should be disabled for this model
    if disable_reasoning and should_disable_reasoning(model_name):
        logger.info(f"Attempting to minimize reasoning for model: {model_name}")

        # Get model-specific kwargs for reasoning control
        model_kwargs = get_reasoning_disabled_kwargs(model_name, max_tokens)

        # OpenAI reasoning models (o1, o3, gpt-5) have special requirements
        if any(x in model_lower for x in ['o1', 'o3', 'gpt-5']):
            # Log the specific reasoning_effort value being used
            reasoning_effort = model_kwargs.get("reasoning_effort", "unknown")
            logger.info(f"Using reasoning_effort='{reasoning_effort}' for OpenAI reasoning model: {model_name}")
            # OpenAI reasoning models require temperature=1
            return ChatOpenAI(
                model=model_name,
                temperature=1,
                openai_api_key=api["api_key"],
                openai_api_base=api["api_base"],
                model_kwargs=model_kwargs,
            )
        else:
            # For other models (gemini, deepseek, qwen, claude), use standard config
            # Reasoning is minimized by using temperature=0.0
            logger.info(f"Using low temperature (T={temperature}) to minimize reasoning for: {model_name}")
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                openai_api_key=api["api_key"],
                openai_api_base=api["api_base"],
            )
    else:
        # Standard configuration for models without reasoning concerns
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            openai_api_key=api["api_key"],
            openai_api_base=api["api_base"],
        )
