"""
Security-Aware Code Generation Workflow

This module implements a security-focused code generation workflow that:
1. Analyzes the problem to identify potential security risks
2. Generates security test cases for the identified risks
3. Generates code that addresses the security risks
4. Executes and repairs code until tests pass or attempts are exhausted
5. Switches to alternative security risk types when repair attempts fail
"""

from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_openai import ChatOpenAI
from configuration import CG_Configuration
from langchain_core.runnables import RunnableConfig
import logging
import os
import re
import tiktoken

from utils import setup_openai_api, format_log_message, create_llm_with_reasoning_control
from prompts import (
    security_analyzer_prompt,
    security_testcase_generator_prompt,
    security_aware_code_generation_prompt,
    security_aware_code_repair_prompt,
    security_testcase_generator_all_risks_prompt,
    security_aware_code_generation_all_risks_prompt,
    security_aware_code_repair_all_risks_prompt,
    feedback_prompt,
    insecure_code_analyzer_prompt,
    testcase_generator_for_repair_prompt,
    code_fixer_prompt,
    code_repairer_for_repair_mode_prompt,
    testcase_generator_problem_prompt,
    code_generator_problem_prompt,
    code_repairer_problem_prompt,
)
from state import SecurityAwareState, RepairModeState
from tools_and_schemas import (
    SecurityAnalysis, SecurityTestSuite,
    InsecureCodeAnalysis, RepairTestSuite,
)

load_dotenv()


# ==================== Token Usage and Cost Tracking ====================

# Price per 1M tokens (USD) - update these as needed
MODEL_PRICING = {
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-5": {"input": 5.00, "output": 15.00},  # Estimated
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    "o3": {"input": 15.00, "output": 60.00},  # Estimated
    "o3-mini": {"input": 1.10, "output": 4.40},
    # Claude models (if using via OpenAI-compatible API)
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    # DeepSeek models
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-coder": {"input": 0.14, "output": 0.28},
    # Default fallback
    "default": {"input": 1.00, "output": 2.00},
}


def get_model_pricing(model_name: str) -> dict:
    """Get pricing for a model, with fallback to default."""
    model_lower = model_name.lower()
    for key in MODEL_PRICING:
        if key in model_lower:
            return MODEL_PRICING[key]
    return MODEL_PRICING["default"]


def extract_token_usage(response, model_name: str) -> dict:
    """Extract token usage from LLM response and calculate cost."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}

    try:
        # For AIMessage responses
        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if "token_usage" in metadata:
                token_usage = metadata["token_usage"]
                usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                usage["total_tokens"] = token_usage.get("total_tokens", 0)
            elif "usage" in metadata:
                token_usage = metadata["usage"]
                usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                usage["total_tokens"] = token_usage.get("total_tokens", 0)

        # For structured output responses (Pydantic models)
        elif hasattr(response, "__dict__"):
            # Try to get from the underlying response if available
            pass

        # Calculate cost
        pricing = get_model_pricing(model_name)
        usage["cost"] = (
            (usage["prompt_tokens"] / 1_000_000) * pricing["input"] +
            (usage["completion_tokens"] / 1_000_000) * pricing["output"]
        )
    except Exception as e:
        logger.warning(f"Could not extract token usage: {e}")

    return usage


def accumulate_token_usage(state: dict, new_usage: dict) -> dict:
    """Accumulate token usage into state."""
    current = state.get("token_usage", {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "calls": []
    })

    return {
        "prompt_tokens": current.get("prompt_tokens", 0) + new_usage.get("prompt_tokens", 0),
        "completion_tokens": current.get("completion_tokens", 0) + new_usage.get("completion_tokens", 0),
        "total_tokens": current.get("total_tokens", 0) + new_usage.get("total_tokens", 0),
        "cost": current.get("cost", 0.0) + new_usage.get("cost", 0.0),
        "calls": current.get("calls", []) + [new_usage]
    }


def get_logger(
    name="SecurityAwareLogger",
    log_file="logs/security_aware.log",
    console_level=logging.INFO,
    file_level=logging.DEBUG,
):
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    logger.addHandler(console)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)
    return logger


logger = get_logger()


# ==================== LLM Call Wrappers with Full Logging ====================

def invoke_structured_llm(structured_llm, prompt: str, task_id: str, step_name: str, model_name: str, max_retries: int = 2):
    """
    Invoke structured LLM with comprehensive logging for debugging and retry mechanism.

    Records the full prompt, raw response, and parsed result.
    Retries up to max_retries times if parsing fails.
    Raises detailed error if all retries fail.
    """
    logger.debug(format_log_message(f"[{task_id}] [{step_name}] === PROMPT ===\n{prompt}"))

    last_error = None
    last_raw_content = ""

    for attempt in range(max_retries + 1):  # max_retries + 1 total attempts (initial + retries)
        if attempt > 0:
            logger.warning(f"[{task_id}] [{step_name}] Retry attempt {attempt}/{max_retries}")

        try:
            result = structured_llm.invoke(prompt)
        except Exception as e:
            last_error = e
            logger.error(f"[{task_id}] [{step_name}] LLM invoke failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                continue
            logger.error(format_log_message(f"[{task_id}] [{step_name}] Failed prompt:\n{prompt}"))
            raise

        raw_response = result.get("raw")
        parsed = result.get("parsed")

        # Log raw response content
        raw_content = ""
        if raw_response:
            if hasattr(raw_response, 'content'):
                raw_content = raw_response.content
            else:
                raw_content = str(raw_response)

        logger.debug(format_log_message(f"[{task_id}] [{step_name}] === RAW RESPONSE (attempt {attempt + 1}) ===\n{raw_content}"))

        # Check if parsing succeeded
        if parsed is None:
            last_raw_content = raw_content
            error_msg = (
                f"[{task_id}] [{step_name}] Failed to parse LLM response into structured output (attempt {attempt + 1}).\n"
                f"Raw response: {raw_content[:2000]}..."  # Truncate for log readability
            )
            logger.error(error_msg)

            if attempt < max_retries:
                logger.warning(f"[{task_id}] [{step_name}] Retrying due to parsing failure...")
                continue
            else:
                logger.error(format_log_message(f"[{task_id}] [{step_name}] Full failed prompt:\n{prompt}"))
                raise ValueError(f"Structured output parsing failed for {step_name} after {max_retries + 1} attempts. Check logs for details.")

        # Success!
        if attempt > 0:
            logger.info(f"[{task_id}] [{step_name}] Successfully parsed after {attempt + 1} attempts")

        logger.debug(format_log_message(f"[{task_id}] [{step_name}] === PARSED RESULT ===\n{parsed}"))

        # Extract token usage
        token_usage = extract_token_usage(raw_response, model_name)
        token_usage["step"] = step_name
        token_usage["attempts"] = attempt + 1

        return parsed, raw_response, token_usage

    # This should not be reached, but just in case
    raise ValueError(f"Structured output parsing failed for {step_name} after {max_retries + 1} attempts. Check logs for details.")


def invoke_llm(llm, prompt: str, task_id: str, step_name: str, model_name: str, max_retries: int = 2):
    """
    Invoke LLM with comprehensive logging for debugging and retry mechanism.

    Records the full prompt and response content.
    Retries up to max_retries times if invocation fails.
    """
    logger.debug(format_log_message(f"[{task_id}] [{step_name}] === PROMPT ===\n{prompt}"))

    last_error = None

    for attempt in range(max_retries + 1):  # max_retries + 1 total attempts (initial + retries)
        if attempt > 0:
            logger.warning(f"[{task_id}] [{step_name}] Retry attempt {attempt}/{max_retries}")

        try:
            raw_response = llm.invoke(prompt)
        except Exception as e:
            last_error = e
            logger.error(f"[{task_id}] [{step_name}] LLM invoke failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                logger.warning(f"[{task_id}] [{step_name}] Retrying due to invocation failure...")
                continue
            else:
                logger.error(format_log_message(f"[{task_id}] [{step_name}] Failed prompt:\n{prompt}"))
                raise

        # Success!
        if attempt > 0:
            logger.info(f"[{task_id}] [{step_name}] Successfully invoked after {attempt + 1} attempts")

        content = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
        logger.debug(format_log_message(f"[{task_id}] [{step_name}] === RESPONSE (attempt {attempt + 1}) ===\n{content}"))

        # Extract token usage
        token_usage = extract_token_usage(raw_response, model_name)
        token_usage["step"] = step_name
        token_usage["attempts"] = attempt + 1

        return content, raw_response, token_usage

    # This should not be reached, but just in case
    raise last_error if last_error else Exception(f"LLM invoke failed for {step_name} after {max_retries + 1} attempts")


def sanitize(code: str, lang: str = None) -> str:
    """Extract code from markdown code block."""
    pattern = rf"```(?:{lang})?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, code)
    return match.group(1).strip() if match else code.strip()


def num_tokens_from_string(string: str, model_name="gpt-4o-mini") -> int:
    """Returns the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(string))
    return num_tokens


def trunc_prompt(prompt, model_name: str, max_length: int, max_tokens: int):
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


# ==================== Helper Functions ====================


def format_all_risks_text(risks: list) -> str:
    """Format all security risks into a readable text for prompts."""
    lines = []
    for i, risk in enumerate(risks, 1):
        lines.append(f"""
Risk {i}:
- CWE ID: {risk.cwe_id}
- Risk Name: {risk.risk_name}
- Risk Description: {risk.risk_description}
- Mitigation Strategy: {risk.mitigation_strategy}
""")
    return "\n".join(lines)


def create_llm(configurable, api: dict = None):
    """
    Create a ChatOpenAI instance with reasoning control.
    This function now uses the unified create_llm_with_reasoning_control from utils.
    """
    return create_llm_with_reasoning_control(
        model_name=configurable.model_name,
        temperature=configurable.temperature,
        max_tokens=configurable.max_tokens,
        top_p=configurable.top_p,
        disable_reasoning=True  # Always disable reasoning
    )


# ==================== Workflow Nodes ====================


def security_analyzer(state: SecurityAwareState, config: RunnableConfig):
    """
    Analyze the problem to identify potential security risks.

    This node examines the problem description and identifies up to 4
    security vulnerabilities that should be considered during implementation.
    """
    logger.info(f"Task {state['task_id']} Starting Security Analysis Step")
    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = security_analyzer_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(SecurityAnalysis, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="security_analyzer",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Identified {len(response.possible_security_risks)} security risks: "
        f"{[r.cwe_id for r in response.possible_security_risks]}"
    )
    logger.info(f"Task {state['task_id']} Token usage for security_analyzer: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"security_analysis": response, "token_usage": accumulated_usage}


def testcase_generator(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate security test cases for the current security risk.

    This node creates test cases specifically designed to verify that
    the implementation properly handles the identified security risk.
    """
    logger.info(f"Task {state['task_id']} Starting Test Case Generation Step")

    # Get the next security risk to try
    if len(state["security_analysis"].possible_security_risks) == 0:
        raise ValueError("No more security risks to try.")

    current_risk = state["security_analysis"].possible_security_risks.pop(0)
    logger.info(
        f"Task {state['task_id']} Targeting Risk: {current_risk.cwe_id} - {current_risk.risk_name}. "
        f"Remaining risks: {[r.cwe_id for r in state['security_analysis'].possible_security_risks]}"
    )

    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = security_testcase_generator_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        cwe_id=current_risk.cwe_id,
        risk_name=current_risk.risk_name,
        risk_description=current_risk.risk_description,
        mitigation_strategy=current_risk.mitigation_strategy,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(SecurityTestSuite, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="testcase_generator",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Generated {len(response.test_cases)} test cases for {current_risk.cwe_id}"
    )
    logger.info(f"Task {state['task_id']} Token usage for testcase_generator: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {
        "current_risk": current_risk,
        "generated_tests": response,
        "max_repair_attempts": configurable.max_repair_attempts,
        "security_analysis": state["security_analysis"],
        "token_usage": accumulated_usage,
    }


def code_generator(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate secure code that addresses the current security risk.

    This node creates an implementation that follows the mitigation
    strategy for the identified security vulnerability.
    """
    logger.info(f"Task {state['task_id']} Starting Code Generation Step")
    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = security_aware_code_generation_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        cwe_id=state["current_risk"].cwe_id,
        risk_name=state["current_risk"].risk_name,
        risk_description=state["current_risk"].risk_description,
        mitigation_strategy=state["current_risk"].mitigation_strategy,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="code_generator",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_generator: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "token_usage": accumulated_usage}


def code_executor(state: SecurityAwareState, config: RunnableConfig):
    """
    Execute the generated code against security test cases.

    This node runs both the original test cases (if provided) and
    the generated security test cases to verify the implementation.

    Note: Test data should be copied to RACE/Temp/Test by the run script before execution.
    The run script also handles cleanup after execution completes.
    """
    logger.info(f"Task {state['task_id']} Starting Code Execution Step")
    configurable = CG_Configuration.from_runnable_config(config)

    code = sanitize(state["code"], lang="python")
    test_code = state["generated_tests"].test_code
    entry_point = state["task"]["entry_point"]

    # Also include original tests if provided
    original_tests = state["task"].get("original_tests", "")

    # Combine code and test code for execution
    full_code = f"""
{code}

# Generated Security Tests
{test_code}

# Run the tests
try:
    check({entry_point})
    print("ALL_TESTS_PASSED")
except AssertionError as e:
    print(f"ASSERTION_ERROR: {{e}}")
except Exception as e:
    print(f"EXECUTION_ERROR: {{type(e).__name__}}: {{e}}")
"""

    # Execute the code
    # Note: Test data is copied to RACE/Temp/Test by the run script before execution
    # and cleaned up after execution completes
    import subprocess
    import tempfile

    exec_result = {"passed": False, "output": "", "error": ""}

    # Determine the Temp directory path
    temp_dir = os.path.join(os.getcwd(), "Temp")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(full_code)
            temp_file = f.name

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_dir,
        )

        exec_result["output"] = result.stdout
        exec_result["error"] = result.stderr

        if "ALL_TESTS_PASSED" in result.stdout:
            exec_result["passed"] = True
            exec_outcome = ["PASSED"]
        elif "ASSERTION_ERROR" in result.stdout:
            exec_outcome = ["WRONG_ANSWER"]
        elif "EXECUTION_ERROR" in result.stdout or result.returncode != 0:
            exec_outcome = ["RUNTIME_ERROR"]
        else:
            exec_outcome = ["UNKNOWN_ERROR"]

        os.unlink(temp_file)

    except subprocess.TimeoutExpired:
        exec_outcome = ["TIME_LIMIT_EXCEEDED"]
        exec_result["error"] = "Execution timed out after 30 seconds"
        if "temp_file" in locals():
            os.unlink(temp_file)
    except Exception as e:
        exec_outcome = ["RUNTIME_ERROR"]
        exec_result["error"] = str(e)
        if "temp_file" in locals():
            os.unlink(temp_file)

    # Record the attempt
    all_infos = state.get("all_infos", [])
    all_infos.append(
        {
            "current_risk": state["current_risk"].model_dump(),
            "generated_tests": {
                "target_risk": state["generated_tests"].target_risk,
                "test_cases": [tc.model_dump() for tc in state["generated_tests"].test_cases],
            },
            "max_repair_attempts": state["max_repair_attempts"],
            "code": state["code"],
            "exec_outcome": exec_outcome,
            "exec_output": exec_result["output"],
            "exec_error": exec_result["error"],
        }
    )

    logger.info(f"Task {state['task_id']} Execution Outcome: {exec_outcome}")

    return {
        "exec_unittests": [exec_result],
        "exec_outcome": exec_outcome,
        "all_infos": all_infos,
    }


def feedback_generator(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate feedback from execution results for code repair.
    """
    logger.info(f"Task {state['task_id']} Generating Feedback")

    feedback_lines = []
    for idx, result in enumerate(state["exec_unittests"], start=1):
        outcome = state["exec_outcome"][idx - 1] if idx <= len(state["exec_outcome"]) else "UNKNOWN"

        if outcome == "PASSED":
            feedback_lines.append(f"Test {idx}: PASSED")
        elif outcome == "WRONG_ANSWER":
            feedback_lines.append(
                f"Test {idx}: WRONG_ANSWER\n"
                f"Output: {result.get('output', 'N/A')}\n"
                f"Error: {result.get('error', 'N/A')}"
            )
        elif outcome == "RUNTIME_ERROR":
            feedback_lines.append(
                f"Test {idx}: RUNTIME_ERROR\n"
                f"Error: {result.get('error', 'N/A')}\n"
                f"Output: {result.get('output', 'N/A')}"
            )
        elif outcome == "TIME_LIMIT_EXCEEDED":
            feedback_lines.append(f"Test {idx}: TIME_LIMIT_EXCEEDED\nExecution timed out.")
        else:
            feedback_lines.append(
                f"Test {idx}: {outcome}\n"
                f"Output: {result.get('output', 'N/A')}\n"
                f"Error: {result.get('error', 'N/A')}"
            )

    feedback_text = "\n\n".join(feedback_lines)
    return {"feedback": feedback_text}


def code_repairer(state: SecurityAwareState, config: RunnableConfig):
    """
    Repair code that failed security tests.
    """
    logger.info(f"Task {state['task_id']} Starting Code Repair Step")
    logger.info(f"Task {state['task_id']} Repair Attempts Left: {state['max_repair_attempts']}")

    configurable = CG_Configuration.from_runnable_config(config)

    repair_prompt = security_aware_code_repair_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        cwe_id=state["current_risk"].cwe_id,
        risk_name=state["current_risk"].risk_name,
        mitigation_strategy=state["current_risk"].mitigation_strategy,
        buggy_code=sanitize(state["code"], lang="python"),
        feedback=state["feedback"],
    )

    repair_prompt = trunc_prompt(
        repair_prompt,
        model_name=configurable.model_name,
        max_length=configurable.max_length,
        max_tokens=configurable.max_tokens,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, repair_prompt,
        task_id=state['task_id'],
        step_name="code_repairer",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_repairer: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "max_repair_attempts": state["max_repair_attempts"] - 1, "token_usage": accumulated_usage}


def route_repair_switch_risk_or_end(state: SecurityAwareState):
    """
    Determine the next step based on execution results (single mode).

    Routes to:
    - END: All tests passed
    - code_repairer: Tests failed but repair attempts remain
    - testcase_generator: Repair attempts exhausted, try next security risk
    - END: All security risks exhausted
    """
    # 1. All tests passed -> END
    if all(outcome == "PASSED" for outcome in state["exec_outcome"]):
        logger.info(f"Task {state['task_id']} All tests PASSED. Ending workflow.")
        return "should_end"

    # 2. Still have repair attempts -> repair
    if state["max_repair_attempts"] > 0:
        logger.info(
            f"Task {state['task_id']} Tests failed. "
            f"Attempting repair ({state['max_repair_attempts']} attempts left)."
        )
        return "need_repair"

    # 3. Repair attempts exhausted -> try next security risk
    if len(state["security_analysis"].possible_security_risks) > 0:
        logger.info(
            f"Task {state['task_id']} Repair attempts exhausted. "
            f"Switching to next security risk type."
        )
        return "need_new_risk"

    # 4. All security risks exhausted -> END
    logger.info(f"Task {state['task_id']} All security risks exhausted. Ending workflow.")
    return "should_end"


# ==================== All-Risks Mode Nodes ====================


def testcase_generator_all_risks(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate security test cases for ALL identified security risks at once.
    """
    logger.info(f"Task {state['task_id']} Starting All-Risks Test Case Generation Step")

    # Store all risks
    all_risks = list(state["security_analysis"].possible_security_risks)
    all_risks_text = format_all_risks_text(all_risks)

    logger.info(
        f"Task {state['task_id']} Generating tests for ALL {len(all_risks)} risks: "
        f"{[r.cwe_id for r in all_risks]}"
    )

    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = security_testcase_generator_all_risks_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        all_risks=all_risks_text,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(SecurityTestSuite, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="testcase_generator_all_risks",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Generated {len(response.test_cases)} test cases for all risks"
    )
    logger.info(f"Task {state['task_id']} Token usage for testcase_generator_all_risks: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {
        "all_risks": [r.model_dump() for r in all_risks],
        "all_risks_text": all_risks_text,
        "generated_tests": response,
        "max_repair_attempts": configurable.max_repair_attempts,
        "token_usage": accumulated_usage,
    }


def code_generator_all_risks(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate secure code that addresses ALL security risks at once.
    """
    logger.info(f"Task {state['task_id']} Starting All-Risks Code Generation Step")
    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = security_aware_code_generation_all_risks_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        all_risks=state["all_risks_text"],
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="code_generator_all_risks",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_generator_all_risks: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "token_usage": accumulated_usage}


def code_executor_all_risks(state: SecurityAwareState, config: RunnableConfig):
    """
    Execute the generated code against ALL security test cases.

    Note: Test data should be copied to RACE/Test by the run script before execution.
    The run script also handles cleanup after execution completes.
    """
    logger.info(f"Task {state['task_id']} Starting All-Risks Code Execution Step")
    configurable = CG_Configuration.from_runnable_config(config)

    code = sanitize(state["code"], lang="python")
    test_code = state["generated_tests"].test_code
    entry_point = state["task"]["entry_point"]

    # Combine code and test code for execution
    full_code = f"""
{code}

# Generated Security Tests (All Risks)
{test_code}

# Run the tests
try:
    check({entry_point})
    print("ALL_TESTS_PASSED")
except AssertionError as e:
    print(f"ASSERTION_ERROR: {{e}}")
except Exception as e:
    print(f"EXECUTION_ERROR: {{type(e).__name__}}: {{e}}")
"""

    # Execute the code
    # Note: Test data is copied to RACE/Temp/Test by the run script before execution
    # and cleaned up after execution completes
    import subprocess
    import tempfile

    exec_result = {"passed": False, "output": "", "error": ""}

    # Determine the Temp directory path
    temp_dir = os.path.join(os.getcwd(), "Temp")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(full_code)
            temp_file = f.name

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_dir,
        )

        exec_result["output"] = result.stdout
        exec_result["error"] = result.stderr

        if "ALL_TESTS_PASSED" in result.stdout:
            exec_result["passed"] = True
            exec_outcome = ["PASSED"]
        elif "ASSERTION_ERROR" in result.stdout:
            exec_outcome = ["WRONG_ANSWER"]
        elif "EXECUTION_ERROR" in result.stdout or result.returncode != 0:
            exec_outcome = ["RUNTIME_ERROR"]
        else:
            exec_outcome = ["UNKNOWN_ERROR"]

        os.unlink(temp_file)

    except subprocess.TimeoutExpired:
        exec_outcome = ["TIME_LIMIT_EXCEEDED"]
        exec_result["error"] = "Execution timed out after 30 seconds"
        if "temp_file" in locals():
            os.unlink(temp_file)
    except Exception as e:
        exec_outcome = ["RUNTIME_ERROR"]
        exec_result["error"] = str(e)
        if "temp_file" in locals():
            os.unlink(temp_file)

    # Record the attempt
    all_infos = state.get("all_infos", [])
    all_infos.append(
        {
            "all_risks": state["all_risks"],
            "generated_tests": {
                "target_risk": state["generated_tests"].target_risk,
                "test_cases": [tc.model_dump() for tc in state["generated_tests"].test_cases],
            },
            "max_repair_attempts": state["max_repair_attempts"],
            "code": state["code"],
            "exec_outcome": exec_outcome,
            "exec_output": exec_result["output"],
            "exec_error": exec_result["error"],
        }
    )

    logger.info(f"Task {state['task_id']} All-Risks Execution Outcome: {exec_outcome}")

    return {
        "exec_unittests": [exec_result],
        "exec_outcome": exec_outcome,
        "all_infos": all_infos,
    }


def code_repairer_all_risks(state: SecurityAwareState, config: RunnableConfig):
    """
    Repair code that failed security tests (all-risks mode).
    """
    logger.info(f"Task {state['task_id']} Starting All-Risks Code Repair Step")
    logger.info(f"Task {state['task_id']} Repair Attempts Left: {state['max_repair_attempts']}")

    configurable = CG_Configuration.from_runnable_config(config)

    repair_prompt = security_aware_code_repair_all_risks_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        all_risks=state["all_risks_text"],
        buggy_code=sanitize(state["code"], lang="python"),
        feedback=state["feedback"],
    )

    repair_prompt = trunc_prompt(
        repair_prompt,
        model_name=configurable.model_name,
        max_length=configurable.max_length,
        max_tokens=configurable.max_tokens,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, repair_prompt,
        task_id=state['task_id'],
        step_name="code_repairer_all_risks",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_repairer_all_risks: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "max_repair_attempts": state["max_repair_attempts"] - 1, "token_usage": accumulated_usage}


def route_repair_or_end_all_risks(state: SecurityAwareState):
    """
    Determine the next step based on execution results (all-risks mode).

    Routes to:
    - END: All tests passed or repair attempts exhausted
    - code_repairer_all_risks: Tests failed but repair attempts remain
    """
    # 1. All tests passed -> END
    if all(outcome == "PASSED" for outcome in state["exec_outcome"]):
        logger.info(f"Task {state['task_id']} All tests PASSED. Ending workflow.")
        return "should_end"

    # 2. Still have repair attempts -> repair
    if state["max_repair_attempts"] > 0:
        logger.info(
            f"Task {state['task_id']} Tests failed. "
            f"Attempting repair ({state['max_repair_attempts']} attempts left)."
        )
        return "need_repair"

    # 3. Repair attempts exhausted -> END
    logger.info(f"Task {state['task_id']} Repair attempts exhausted. Ending workflow.")
    return "should_end"


# ==================== Problem Mode Nodes ====================


def testcase_generator_problem(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate security test cases for the problem without prior security analysis.

    This node creates test cases based on the problem description alone,
    covering common security vulnerabilities that might arise during implementation.
    """
    logger.info(f"Task {state['task_id']} Starting Problem Mode Test Case Generation Step")

    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = testcase_generator_problem_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(SecurityTestSuite, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="testcase_generator_problem",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Generated {len(response.test_cases)} test cases for problem mode"
    )
    logger.info(f"Task {state['task_id']} Token usage for testcase_generator_problem: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {
        "generated_tests": response,
        "max_repair_attempts": configurable.max_repair_attempts,
        "token_usage": accumulated_usage,
    }


def code_generator_problem(state: SecurityAwareState, config: RunnableConfig):
    """
    Generate secure code for the problem without prior security analysis.

    This node creates an implementation that follows secure coding practices
    to prevent common vulnerabilities.
    """
    logger.info(f"Task {state['task_id']} Starting Problem Mode Code Generation Step")
    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = code_generator_problem_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="code_generator_problem",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_generator_problem: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "token_usage": accumulated_usage}


def code_executor_problem(state: SecurityAwareState, config: RunnableConfig):
    """
    Execute the generated code against security test cases (problem mode).

    This node runs the generated security test cases to verify the implementation.

    Note: Test data should be copied to RACE/Temp/Test by the run script before execution.
    The run script also handles cleanup after execution completes.
    """
    logger.info(f"Task {state['task_id']} Starting Problem Mode Code Execution Step")
    configurable = CG_Configuration.from_runnable_config(config)

    code = sanitize(state["code"], lang="python")
    test_code = state["generated_tests"].test_code
    entry_point = state["task"]["entry_point"]

    # Combine code and test code for execution
    full_code = f"""
{code}

# Generated Security Tests (Problem Mode)
{test_code}

# Run the tests
try:
    check({entry_point})
    print("ALL_TESTS_PASSED")
except AssertionError as e:
    print(f"ASSERTION_ERROR: {{e}}")
except Exception as e:
    print(f"EXECUTION_ERROR: {{type(e).__name__}}: {{e}}")
"""

    # Execute the code
    # Note: Test data is copied to RACE/Temp/Test by the run script before execution
    # and cleaned up after execution completes
    import subprocess
    import tempfile

    exec_result = {"passed": False, "output": "", "error": ""}

    # Determine the Temp directory path
    temp_dir = os.path.join(os.getcwd(), "Temp")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(full_code)
            temp_file = f.name

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_dir,
        )

        exec_result["output"] = result.stdout
        exec_result["error"] = result.stderr

        if "ALL_TESTS_PASSED" in result.stdout:
            exec_result["passed"] = True
            exec_outcome = ["PASSED"]
        elif "ASSERTION_ERROR" in result.stdout:
            exec_outcome = ["WRONG_ANSWER"]
        elif "EXECUTION_ERROR" in result.stdout or result.returncode != 0:
            exec_outcome = ["RUNTIME_ERROR"]
        else:
            exec_outcome = ["UNKNOWN_ERROR"]

        os.unlink(temp_file)

    except subprocess.TimeoutExpired:
        exec_outcome = ["TIME_LIMIT_EXCEEDED"]
        exec_result["error"] = "Execution timed out after 30 seconds"
        if "temp_file" in locals():
            os.unlink(temp_file)
    except Exception as e:
        exec_outcome = ["RUNTIME_ERROR"]
        exec_result["error"] = str(e)
        if "temp_file" in locals():
            os.unlink(temp_file)

    # Record the attempt
    all_infos = state.get("all_infos", [])
    all_infos.append(
        {
            "generated_tests": {
                "target_risk": state["generated_tests"].target_risk,
                "test_cases": [tc.model_dump() for tc in state["generated_tests"].test_cases],
            },
            "max_repair_attempts": state["max_repair_attempts"],
            "code": state["code"],
            "exec_outcome": exec_outcome,
            "exec_output": exec_result["output"],
            "exec_error": exec_result["error"],
        }
    )

    logger.info(f"Task {state['task_id']} Problem Mode Execution Outcome: {exec_outcome}")

    return {
        "exec_unittests": [exec_result],
        "exec_outcome": exec_outcome,
        "all_infos": all_infos,
    }


def code_repairer_problem(state: SecurityAwareState, config: RunnableConfig):
    """
    Repair code that failed security tests (problem mode).
    """
    logger.info(f"Task {state['task_id']} Starting Problem Mode Code Repair Step")
    logger.info(f"Task {state['task_id']} Repair Attempts Left: {state['max_repair_attempts']}")

    configurable = CG_Configuration.from_runnable_config(config)

    repair_prompt = code_repairer_problem_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        buggy_code=sanitize(state["code"], lang="python"),
        feedback=state["feedback"],
    )

    repair_prompt = trunc_prompt(
        repair_prompt,
        model_name=configurable.model_name,
        max_length=configurable.max_length,
        max_tokens=configurable.max_tokens,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, repair_prompt,
        task_id=state['task_id'],
        step_name="code_repairer_problem",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_repairer_problem: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "max_repair_attempts": state["max_repair_attempts"] - 1, "token_usage": accumulated_usage}


def route_repair_or_end_problem(state: SecurityAwareState):
    """
    Determine the next step based on execution results (problem mode).

    Routes to:
    - END: All tests passed or repair attempts exhausted
    - code_repairer_problem: Tests failed but repair attempts remain
    """
    # 1. All tests passed -> END
    if all(outcome == "PASSED" for outcome in state["exec_outcome"]):
        logger.info(f"Task {state['task_id']} All tests PASSED. Ending workflow.")
        return "should_end"

    # 2. Still have repair attempts -> repair
    if state["max_repair_attempts"] > 0:
        logger.info(
            f"Task {state['task_id']} Tests failed. "
            f"Attempting repair ({state['max_repair_attempts']} attempts left)."
        )
        return "need_repair"

    # 3. Repair attempts exhausted -> END
    logger.info(f"Task {state['task_id']} Repair attempts exhausted. Ending workflow.")
    return "should_end"


# ==================== Repair Mode Nodes ====================


def insecure_code_analyzer(state: RepairModeState, config: RunnableConfig):
    """
    Analyze insecure code to identify functional issues and security vulnerabilities.

    This node examines the provided insecure code and identifies:
    1. The intended behavior
    2. Functional bugs that need fixing
    3. Security vulnerabilities that need enhancement
    """
    logger.info(f"Task {state['task_id']} Starting Insecure Code Analysis Step")
    configurable = CG_Configuration.from_runnable_config(config)

    formatted_prompt = insecure_code_analyzer_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        insecure_code=state["insecure_code"],
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(InsecureCodeAnalysis, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="insecure_code_analyzer",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Identified {len(response.functional_issues)} functional issues "
        f"and {len(response.security_vulnerabilities)} security vulnerabilities"
    )
    logger.info(f"Task {state['task_id']} Token usage for insecure_code_analyzer: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"analysis": response, "token_usage": accumulated_usage}


def testcase_generator_for_repair(state: RepairModeState, config: RunnableConfig):
    """
    Generate test cases for verifying code repair (both functional and security tests).
    """
    logger.info(f"Task {state['task_id']} Starting Repair Test Case Generation Step")
    configurable = CG_Configuration.from_runnable_config(config)

    # Format functional issues and security vulnerabilities for prompt
    functional_issues_text = "\n".join([
        f"- Location: {issue.issue_location}\n  Description: {issue.issue_description}\n  Fix: {issue.fix_needed}"
        for issue in state["analysis"].functional_issues
    ])

    security_vulnerabilities_text = "\n".join([
        f"- CWE-{vuln.cwe_id} at {vuln.vulnerability_location}\n  Description: {vuln.vulnerability_description}\n  Enhancement: {vuln.enhancement_needed}"
        for vuln in state["analysis"].security_vulnerabilities
    ])

    formatted_prompt = testcase_generator_for_repair_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        insecure_code=state["insecure_code"],
        functional_issues=functional_issues_text,
        security_vulnerabilities=security_vulnerabilities_text,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)
    structured_llm = llm.with_structured_output(RepairTestSuite, method="json_mode", include_raw=True)

    response, _, token_usage = invoke_structured_llm(
        structured_llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="testcase_generator_for_repair",
        model_name=configurable.model_name
    )

    logger.info(
        f"Task {state['task_id']} Generated {len(response.test_cases)} test cases for repair verification"
    )
    logger.info(f"Task {state['task_id']} Token usage for testcase_generator_for_repair: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {
        "generated_tests": response,
        "max_repair_attempts": configurable.max_repair_attempts,
        "token_usage": accumulated_usage,
    }


def code_fixer(state: RepairModeState, config: RunnableConfig):
    """
    Fix insecure code by addressing functional issues and security vulnerabilities.
    """
    logger.info(f"Task {state['task_id']} Starting Code Fixing Step")
    configurable = CG_Configuration.from_runnable_config(config)

    # Format issues for prompt
    functional_issues_text = "\n".join([
        f"- Location: {issue.issue_location}\n  Description: {issue.issue_description}\n  Fix: {issue.fix_needed}"
        for issue in state["analysis"].functional_issues
    ])

    security_vulnerabilities_text = "\n".join([
        f"- CWE-{vuln.cwe_id} at {vuln.vulnerability_location}\n  Description: {vuln.vulnerability_description}\n  Enhancement: {vuln.enhancement_needed}"
        for vuln in state["analysis"].security_vulnerabilities
    ])

    formatted_prompt = code_fixer_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        insecure_code=state["insecure_code"],
        functional_issues=functional_issues_text,
        security_vulnerabilities=security_vulnerabilities_text,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, formatted_prompt,
        task_id=state['task_id'],
        step_name="code_fixer",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_fixer: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "token_usage": accumulated_usage}


def code_executor_repair_mode(state: RepairModeState, config: RunnableConfig):
    """
    Execute the fixed code against repair test cases.
    """
    logger.info(f"Task {state['task_id']} Starting Code Execution Step (Repair Mode)")
    configurable = CG_Configuration.from_runnable_config(config)

    code = sanitize(state["code"], lang="python")
    test_code = state["generated_tests"].test_code
    entry_point = state["task"]["entry_point"]

    # Combine code and test code for execution
    full_code = f"""
{code}

# Generated Repair Tests (Functional + Security)
{test_code}

# Run the tests
try:
    check({entry_point})
    print("ALL_TESTS_PASSED")
except AssertionError as e:
    print(f"ASSERTION_ERROR: {{e}}")
except Exception as e:
    print(f"EXECUTION_ERROR: {{type(e).__name__}}: {{e}}")
"""

    # Execute the code
    import subprocess
    import tempfile

    exec_result = {"passed": False, "output": "", "error": ""}

    # Determine the Temp directory path
    temp_dir = os.path.join(os.getcwd(), "Temp")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(full_code)
            temp_file = f.name

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_dir,
        )

        exec_result["output"] = result.stdout
        exec_result["error"] = result.stderr

        if "ALL_TESTS_PASSED" in result.stdout:
            exec_result["passed"] = True
            exec_outcome = ["PASSED"]
        elif "ASSERTION_ERROR" in result.stdout:
            exec_outcome = ["WRONG_ANSWER"]
        elif "EXECUTION_ERROR" in result.stdout or result.returncode != 0:
            exec_outcome = ["RUNTIME_ERROR"]
        else:
            exec_outcome = ["UNKNOWN_ERROR"]

        os.unlink(temp_file)

    except subprocess.TimeoutExpired:
        exec_outcome = ["TIME_LIMIT_EXCEEDED"]
        exec_result["error"] = "Execution timed out after 30 seconds"
        if "temp_file" in locals():
            os.unlink(temp_file)
    except Exception as e:
        exec_outcome = ["RUNTIME_ERROR"]
        exec_result["error"] = str(e)
        if "temp_file" in locals():
            os.unlink(temp_file)

    # Record the attempt
    all_infos = state.get("all_infos", [])
    all_infos.append(
        {
            "analysis": state["analysis"].model_dump(),
            "generated_tests": {
                "functional_tests_summary": state["generated_tests"].functional_tests_summary,
                "security_tests_summary": state["generated_tests"].security_tests_summary,
            },
            "max_repair_attempts": state["max_repair_attempts"],
            "code": state["code"],
            "exec_outcome": exec_outcome,
            "exec_output": exec_result["output"],
            "exec_error": exec_result["error"],
        }
    )

    logger.info(f"Task {state['task_id']} Execution Outcome: {exec_outcome}")

    return {
        "exec_unittests": [exec_result],
        "exec_outcome": exec_outcome,
        "all_infos": all_infos,
    }


def code_repairer_repair_mode(state: RepairModeState, config: RunnableConfig):
    """
    Repair code that failed tests in repair mode.
    """
    logger.info(f"Task {state['task_id']} Starting Code Repair Step (Repair Mode)")
    logger.info(f"Task {state['task_id']} Repair Attempts Left: {state['max_repair_attempts']}")

    configurable = CG_Configuration.from_runnable_config(config)

    # Format issues for prompt
    functional_issues_text = "\n".join([
        f"- Location: {issue.issue_location}\n  Description: {issue.issue_description}\n  Fix: {issue.fix_needed}"
        for issue in state["analysis"].functional_issues
    ])

    security_vulnerabilities_text = "\n".join([
        f"- CWE-{vuln.cwe_id} at {vuln.vulnerability_location}\n  Description: {vuln.vulnerability_description}\n  Enhancement: {vuln.enhancement_needed}"
        for vuln in state["analysis"].security_vulnerabilities
    ])

    repair_prompt = code_repairer_for_repair_mode_prompt.format(
        problem_description=state["task"]["problem_description"],
        entry_point=state["task"]["entry_point"],
        buggy_code=sanitize(state["code"], lang="python"),
        feedback=state["feedback"],
        functional_issues=functional_issues_text,
        security_vulnerabilities=security_vulnerabilities_text,
    )

    repair_prompt = trunc_prompt(
        repair_prompt,
        model_name=configurable.model_name,
        max_length=configurable.max_length,
        max_tokens=configurable.max_tokens,
    )

    api = setup_openai_api(configurable.model_name)
    llm = create_llm(configurable, api)

    response, _, token_usage = invoke_llm(
        llm, repair_prompt,
        task_id=state['task_id'],
        step_name="code_repairer_repair_mode",
        model_name=configurable.model_name
    )

    logger.info(f"Task {state['task_id']} Token usage for code_repairer_repair_mode: {token_usage}")

    accumulated_usage = accumulate_token_usage(state, token_usage)
    return {"code": response, "max_repair_attempts": state["max_repair_attempts"] - 1, "token_usage": accumulated_usage}


def route_repair_or_end_repair_mode(state: RepairModeState):
    """
    Determine the next step based on execution results (repair mode).

    Routes to:
    - END: All tests passed or repair attempts exhausted
    - code_repairer_repair_mode: Tests failed but repair attempts remain
    """
    # 1. All tests passed -> END
    if all(outcome == "PASSED" for outcome in state["exec_outcome"]):
        logger.info(f"Task {state['task_id']} All tests PASSED. Ending workflow.")
        return "should_end"

    # 2. Still have repair attempts -> repair
    if state["max_repair_attempts"] > 0:
        logger.info(
            f"Task {state['task_id']} Tests failed. "
            f"Attempting repair ({state['max_repair_attempts']} attempts left)."
        )
        return "need_repair"

    # 3. Repair attempts exhausted -> END
    logger.info(f"Task {state['task_id']} Repair attempts exhausted. Ending workflow.")
    return "should_end"


# ==================== Workflow Builder ====================


def build_security_aware_workflow(security_mode: str = "single"):
    """
    Build the security-aware code generation workflow.

    Args:
        security_mode: "single" - address one risk at a time until tests pass
                       "all" - address all identified risks at once
                       "repair" - fix provided insecure code
                       "problem" - skip security analysis, generate tests/code directly from problem

    Single Mode Workflow:
        START -> security_analyzer -> testcase_generator -> code_generator -> code_executor
                        ^                                                         |
                        |                                                         v
                        +--- need_new_risk <--- [route] --- need_repair --> feedback_generator
                                                   |                              |
                                                   v                              v
                                              should_end -> END           code_repairer
                                                                               |
                                                                               v
                                                                         code_executor

    All Mode Workflow:
        START -> security_analyzer -> testcase_generator_all_risks -> code_generator_all_risks
                                                                              |
                                                                              v
                                                                    code_executor_all_risks
                                                                              |
                                                                              v
                      code_repairer_all_risks <-- need_repair <-- [route] --> should_end -> END
                              |                                       ^
                              v                                       |
                      feedback_generator -----> code_executor_all_risks

    Repair Mode Workflow:
        START -> insecure_code_analyzer -> testcase_generator_for_repair -> code_fixer
                                                                                |
                                                                                v
                                                                      code_executor_repair_mode
                                                                                |
                                                                                v
                      code_repairer_repair_mode <-- need_repair <-- [route] --> should_end -> END
                              |                                       ^
                              v                                       |
                      feedback_generator -----> code_executor_repair_mode

    Problem Mode Workflow:
        START -> testcase_generator_problem -> code_generator_problem -> code_executor_problem
                                                                              |
                                                                              v
                      code_repairer_problem <-- need_repair <-- [route] --> should_end -> END
                              |                                       ^
                              v                                       |
                      feedback_generator -----> code_executor_problem
    """
    logger.info(f"Building security-aware workflow with mode: {security_mode}")

    if security_mode == "repair":
        # Repair mode: fix provided insecure code
        workflow_builder = StateGraph(RepairModeState, context_schema=RunnableConfig)
    else:
        workflow_builder = StateGraph(SecurityAwareState, context_schema=RunnableConfig)

    if security_mode == "repair":
        # Repair mode: fix provided insecure code
        workflow_builder.add_node("insecure_code_analyzer", insecure_code_analyzer)
        workflow_builder.add_node("testcase_generator_for_repair", testcase_generator_for_repair)
        workflow_builder.add_node("code_fixer", code_fixer)
        workflow_builder.add_node("code_executor_repair_mode", code_executor_repair_mode)
        workflow_builder.add_node("feedback_generator", feedback_generator)
        workflow_builder.add_node("code_repairer_repair_mode", code_repairer_repair_mode)

        # Define edges
        workflow_builder.add_edge(START, "insecure_code_analyzer")
        workflow_builder.add_edge("insecure_code_analyzer", "testcase_generator_for_repair")
        workflow_builder.add_edge("testcase_generator_for_repair", "code_fixer")
        workflow_builder.add_edge("code_fixer", "code_executor_repair_mode")
        workflow_builder.add_edge("feedback_generator", "code_repairer_repair_mode")
        workflow_builder.add_edge("code_repairer_repair_mode", "code_executor_repair_mode")

        # Conditional routing after execution
        workflow_builder.add_conditional_edges(
            "code_executor_repair_mode",
            route_repair_or_end_repair_mode,
            {
                "need_repair": "feedback_generator",
                "should_end": END,
            },
        )

        workflow_name = "security_aware_workflow_repair.png"

    elif security_mode == "all":
        # All-risks mode: address all risks at once
        workflow_builder.add_node("security_analyzer", security_analyzer)
        workflow_builder.add_node("testcase_generator_all_risks", testcase_generator_all_risks)
        workflow_builder.add_node("code_generator_all_risks", code_generator_all_risks)
        workflow_builder.add_node("code_executor_all_risks", code_executor_all_risks)
        workflow_builder.add_node("feedback_generator", feedback_generator)
        workflow_builder.add_node("code_repairer_all_risks", code_repairer_all_risks)

        # Define edges
        workflow_builder.add_edge(START, "security_analyzer")
        workflow_builder.add_edge("security_analyzer", "testcase_generator_all_risks")
        workflow_builder.add_edge("testcase_generator_all_risks", "code_generator_all_risks")
        workflow_builder.add_edge("code_generator_all_risks", "code_executor_all_risks")
        workflow_builder.add_edge("feedback_generator", "code_repairer_all_risks")
        workflow_builder.add_edge("code_repairer_all_risks", "code_executor_all_risks")

        # Conditional routing after execution
        workflow_builder.add_conditional_edges(
            "code_executor_all_risks",
            route_repair_or_end_all_risks,
            {
                "need_repair": "feedback_generator",
                "should_end": END,
            },
        )

        workflow_name = "security_aware_workflow_all.png"

    elif security_mode == "problem":
        # Problem mode: skip security analysis, generate tests/code directly from problem
        workflow_builder.add_node("testcase_generator_problem", testcase_generator_problem)
        workflow_builder.add_node("code_generator_problem", code_generator_problem)
        workflow_builder.add_node("code_executor_problem", code_executor_problem)
        workflow_builder.add_node("feedback_generator", feedback_generator)
        workflow_builder.add_node("code_repairer_problem", code_repairer_problem)

        # Define edges
        workflow_builder.add_edge(START, "testcase_generator_problem")
        workflow_builder.add_edge("testcase_generator_problem", "code_generator_problem")
        workflow_builder.add_edge("code_generator_problem", "code_executor_problem")
        workflow_builder.add_edge("feedback_generator", "code_repairer_problem")
        workflow_builder.add_edge("code_repairer_problem", "code_executor_problem")

        # Conditional routing after execution
        workflow_builder.add_conditional_edges(
            "code_executor_problem",
            route_repair_or_end_problem,
            {
                "need_repair": "feedback_generator",
                "should_end": END,
            },
        )

        workflow_name = "security_aware_workflow_problem.png"
    else:
        # Single mode (default): address one risk at a time
        workflow_builder.add_node("security_analyzer", security_analyzer)
        workflow_builder.add_node("testcase_generator", testcase_generator)
        workflow_builder.add_node("code_generator", code_generator)
        workflow_builder.add_node("code_executor", code_executor)
        workflow_builder.add_node("feedback_generator", feedback_generator)
        workflow_builder.add_node("code_repairer", code_repairer)

        # Define edges
        workflow_builder.add_edge(START, "security_analyzer")
        workflow_builder.add_edge("security_analyzer", "testcase_generator")
        workflow_builder.add_edge("testcase_generator", "code_generator")
        workflow_builder.add_edge("code_generator", "code_executor")
        workflow_builder.add_edge("feedback_generator", "code_repairer")
        workflow_builder.add_edge("code_repairer", "code_executor")

        # Conditional routing after execution
        workflow_builder.add_conditional_edges(
            "code_executor",
            route_repair_switch_risk_or_end,
            {
                "need_repair": "feedback_generator",
                "need_new_risk": "testcase_generator",
                "should_end": END,
            },
        )

        workflow_name = "security_aware_workflow_single.png"

    # Compile the workflow
    workflow = workflow_builder.compile()

    # Save workflow diagram
    try:
        workflow_img = workflow.get_graph().draw_mermaid_png()
        with open(workflow_name, "wb") as f:
            f.write(workflow_img)
        logger.info(f"Workflow diagram saved to {workflow_name}")
    except Exception as e:
        logger.warning(f"Could not save workflow diagram: {e}")

    return workflow


if __name__ == "__main__":
    # Test all workflow builds
    workflow_single = build_security_aware_workflow(security_mode="single")
    print("Security-aware workflow (single mode) built successfully!")

    workflow_all = build_security_aware_workflow(security_mode="all")
    print("Security-aware workflow (all mode) built successfully!")

    workflow_repair = build_security_aware_workflow(security_mode="repair")
    print("Security-aware workflow (repair mode) built successfully!")

    workflow_problem = build_security_aware_workflow(security_mode="problem")
    print("Security-aware workflow (problem mode) built successfully!")
