from pydantic import BaseModel, Field
from typing import List

class AlgorithmInfo(BaseModel):
    algorithm_name: str = Field(description="Name of the algorithm or approach.")
    time_complexity: str = Field(description="Time complexity of the algorithm.")
    space_complexity: str = Field(description="Space complexity of the algorithm.")
    algorithm_explanation: str = Field(description="Explanation of why the algorithm is applicable or rejected.")

class ProblemAnalysis(BaseModel):
    input_output_constraints: str = Field(description="Constraints related to input and output formats.")
    explicit_constraints: str = Field(description="Explicit constraints of the problem.")
    implicit_constraints: str = Field(description="Implicit constraints of the problem.")
    problem_type_identification: str = Field(description="Identification of the problem type.")

class FeasibleComplexityEstimation(BaseModel):
    estimated_time_complexity: str = Field(description="Estimated time complexity for solving the problem.")
    estimated_memory_complexity: str = Field(description="Estimated memory complexity for solving the problem.")
    potential_resource_bottlenecks: str = Field(description="Potential resource bottlenecks in solving the problem.")

class Analysis(BaseModel):
    problem_analysis: ProblemAnalysis = Field(description="Detailed analysis of the problem.")
    feasible_complexity_estimation: FeasibleComplexityEstimation = Field(
        description="Estimation of feasible complexities."
    )
    possible_algorithms_complexity: List[AlgorithmInfo] = Field(
        description="List of possible algorithms with name, complexity, and explanation."
    )

class PlannerOutput(BaseModel):
    data_structures: str = Field(description="Recommended data structures to use.")
    algorithm_plan: str = Field(description="high-level algorithmic plan to solve the problem.")
    resource_planning_notes: str = Field(description="Notes on resource planning for efficient implementation.")

class CodeAnalysisOutput(BaseModel):
    summary: str = Field(description="Summary of the provided source code.")
    algorithms: List[str] = Field(description="List of algorithms used in the code.")
    data_structures: List[str] = Field(description="List of data structures used in the code.")
    time_complexity: str = Field(description="Time complexity of the code.")
    space_complexity: str = Field(description="Space complexity of the code.")

class TranslationAnalysisOutput(BaseModel):
    algorithm_identification: AlgorithmInfo = Field(description="Identified algorithm with name, complexity, and explanation.")
    alternative_algorithms: List[AlgorithmInfo] = Field(description="List of alternative algorithms with name, complexity, and explanation.")

class SelfPlanningOutput(BaseModel):
    plan: str = Field(description="Detailed step-by-step plan to accomplish the task.")

class WithoutAlgExplorationAnalysis(BaseModel):
    problem_analysis: ProblemAnalysis = Field(description="Detailed analysis of the problem.")
    feasible_complexity_estimation: FeasibleComplexityEstimation = Field(
        description="Estimation of feasible complexities."
    )
    most_recommended_algorithm: AlgorithmInfo = Field(description="Most recommended algorithm with name, complexity, and explanation.")

class TranslationWithoutAlgExplorationAnalysis(BaseModel):
    algorithm_identification: AlgorithmInfo = Field(description="Identified algorithm with name, complexity, and explanation.")


# ==================== Security-Aware Code Generation Schemas ====================

class SecurityRiskInfo(BaseModel):
    """Information about a specific security risk type."""
    cwe_id: str = Field(description="CWE identifier, e.g., 'CWE-20', 'CWE-79', 'CWE-89'.")
    risk_name: str = Field(description="Name of the security risk, e.g., 'Input Validation', 'SQL Injection'.")
    risk_description: str = Field(description="Brief description of how this risk applies to the given problem.")
    mitigation_strategy: str = Field(description="Recommended strategy to mitigate this security risk.")


class SecurityAnalysis(BaseModel):
    """Output of the security analyzer."""
    problem_summary: str = Field(description="Brief summary of the problem requirements.")
    security_considerations: str = Field(description="General security considerations for this problem.")
    possible_security_risks: List[SecurityRiskInfo] = Field(
        description="List of possible security risks that may apply to this problem, ordered by relevance."
    )


class SecurityTestCase(BaseModel):
    """A single security-focused test case."""
    test_input: str = Field(description="The input for this test case.")
    expected_behavior: str = Field(description="Expected behavior or output for this test case.")
    test_purpose: str = Field(description="What security aspect this test case is checking.")


class SecurityTestSuite(BaseModel):
    """Generated security test cases for a specific risk type."""
    target_risk: str = Field(description="The security risk type these tests are targeting.")
    test_cases: List[SecurityTestCase] = Field(description="List of security test cases.")
    test_code: str = Field(description="Complete executable test code in Python.")


# ==================== Repair Mode Schemas ====================

class FunctionalIssue(BaseModel):
    """A functional bug or logic error in the code."""
    issue_location: str = Field(description="Where in the code this issue exists (line/section description).")
    issue_description: str = Field(description="What's wrong functionally.")
    fix_needed: str = Field(description="How to fix this functional issue.")


class SecurityVulnerability(BaseModel):
    """A security vulnerability in the code."""
    cwe_id: str = Field(description="CWE identifier, e.g., 'CWE-20', 'CWE-78'.")
    vulnerability_location: str = Field(description="Where in the code this vulnerability exists.")
    vulnerability_description: str = Field(description="What's the security issue.")
    enhancement_needed: str = Field(description="How to add security protection.")


class InsecureCodeAnalysis(BaseModel):
    """Analysis of insecure code identifying functional issues and security vulnerabilities."""
    intended_behavior: str = Field(description="What the code is trying to accomplish.")
    behavioral_correctness: str = Field(description="Whether the core logic is correct or needs fixes.")
    functional_issues: List[FunctionalIssue] = Field(
        description="List of functional bugs that need fixing."
    )
    security_vulnerabilities: List[SecurityVulnerability] = Field(
        description="List of security vulnerabilities that need enhancement."
    )
    priority_fixes: str = Field(description="Which issues should be addressed first and why.")


class RepairTestCase(BaseModel):
    """A test case for verifying code repair (functional or security)."""
    test_category: str = Field(description="Category: 'functional' or 'security'.")
    test_input: str = Field(description="Description of the test input.")
    expected_behavior: str = Field(description="Expected behavior or output.")
    test_purpose: str = Field(description="What aspect is being tested (include CWE ID for security tests).")


class RepairTestSuite(BaseModel):
    """Generated test cases for code repair verification."""
    functional_tests_summary: str = Field(description="Summary of functional tests.")
    security_tests_summary: str = Field(description="Summary of security tests covering which CWE IDs.")
    test_cases: List[RepairTestCase] = Field(description="List of test cases.")
    test_code: str = Field(description="Complete executable test code in Python.")