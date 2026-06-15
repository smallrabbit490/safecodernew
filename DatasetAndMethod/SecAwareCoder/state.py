from typing import TypedDict
from tools_and_schemas import (
    AlgorithmInfo, Analysis, PlannerOutput,
    SecurityAnalysis, SecurityRiskInfo, SecurityTestSuite,
    InsecureCodeAnalysis, RepairTestSuite
)
import operator

class CG_State(TypedDict):
    task_id: str
    task: str
    code: str

class CT_State(TypedDict):
    task_id: str
    source_code: str
    prompt: str
    response: str
    code: str

class OverallState(TypedDict):
    task_id: str
    task: dict
    analysis: Analysis
    trying_algorithm: AlgorithmInfo
    planning: PlannerOutput
    code: str
    feedback: str
    all_infos: list
    exec_unittests: list
    exec_outcome: list
    max_repair_attempts: int

class CT_OverallState(TypedDict):
    task_id: str
    task: dict
    code: str
    feedback: str
    all_infos: list
    exec_unittests: list
    exec_outcome: list
    analysis: dict
    max_repair_attempts: int

class SelfPlanningState(TypedDict):
    task_id: str
    task: str
    plan: str
    code: str

class CT_SelfPlanningState(TypedDict):
    task_id: str
    source_code: str
    plan: str
    code: str


# ==================== Security-Aware Code Generation State ====================

class SecurityAwareState(TypedDict):
    """State for security-aware code generation workflow."""
    task_id: str
    task: dict  # Contains: problem_description, entry_point
    security_analysis: SecurityAnalysis  # Analysis of security risks
    current_risk: SecurityRiskInfo  # Current security risk being addressed (single mode)
    all_risks: list  # All security risks to address (all mode)
    all_risks_text: str  # Formatted text of all risks for prompts (all mode)
    generated_tests: SecurityTestSuite  # Generated security test cases
    code: str  # Generated code
    feedback: str  # Execution feedback
    all_infos: list  # History of all attempts
    exec_unittests: list  # Execution results
    exec_outcome: list  # Execution outcomes
    max_repair_attempts: int  # Remaining repair attempts
    token_usage: dict  # Token usage statistics: {prompt_tokens, completion_tokens, total_tokens, cost}


# ==================== Repair Mode State ====================

class RepairModeState(TypedDict):
    """State for repair mode workflow - fixing insecure code."""
    task_id: str
    task: dict  # Contains: problem_description, entry_point, insecure_code
    insecure_code: str  # The original insecure code to be fixed
    analysis: InsecureCodeAnalysis  # Analysis of functional issues and security vulnerabilities
    generated_tests: RepairTestSuite  # Generated test cases for repair verification
    code: str  # Fixed code
    feedback: str  # Execution feedback
    all_infos: list  # History of all repair attempts
    exec_unittests: list  # Execution results
    exec_outcome: list  # Execution outcomes
    max_repair_attempts: int  # Remaining repair attempts
    token_usage: dict  # Token usage statistics