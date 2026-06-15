

code_generation_prompt = """Please provide a self-contained {target_language} program that solves the following problem in a markdown code block:\n```\n{task_description}\n```\nBelow is a {target_language} program with a self-contained function that solves the problem and passes corresponding tests:\n```{target_language}"""

code_generation_cot_prompt = """You are a coding expert. Given a competition-level coding problem in a markdown code block, you need to write a {target_language} program to solve it. You may start by outlining your thought process. In the end, please provide the self-contained complete code in a code block enclosed with ```{target_language} ```.
Here is the problem:
```
{task_description}
```

"""

task_analyzer_prompt = """
# Task
You are a competitive programming problem analyst. Your goal is to read a problem statement and systematically extract all information required for designing an efficient algorithm that satisfies the given time and memory limits.

# Input
Problem: A problem description, including input format, output format, constraints, and any additional context.
Limits: Time and memory limits for the problem.

# Guidelines for Analysis

## Step 1: Problem Analysis
Extract the core structural information of the problem, including input/output constraints, explicit constraints, implicit constraints, and problem type identification.

###  Input and Output Constraints
Identify the Input size range and Output requirements and I/O format properties.

### Explicit Constraints
A brief explanation of all constraints explicitly stated in the problem.

### Implicit Constraints
A brief explanation of all constraints that are not explicitly stated but can be inferred from the problem context.

### Problem Type Identification
Identify the problem type(s) (e.g., graph, DP, greedy, math, string, geometry). Include multiple types if applicable.

## Step 2: Feasible Complexity Estimation
Based on the "Limits", information from Step 1, and general heuristics, estimate feasible time and memory complexities and identify potential resource bottlenecks.

### Time Complexity Estimation
Estimate feasible time complexity.

### Memory Complexity Estimation
Estimate feasible memory complexity.

### Potential Resource Bottlenecks
A brief explanation to Identify factors that may cause time or memory violations, such as high constant factors, large intermediate structures, recursion depth, heavy data structures, or worst-case combinatorial explosion.

## Step 3: Possible Algorithms and Complexity
Based on Step 1 and Step 2, infer feasible algorithms and their complexities. provide a list of no more than **4** possible algorithms. Each item must be a dictionary with the following keys:
- `algorithm_name`: the algorithm or approach being considered.
- `time_complexity`: The estimated time complexity.
- `space_complexity`: The estimated space complexity.
- `algorithm_explanation`: A brief explanation of why this algorithm is feasible under the constraints.

## Output Format
Provide your analysis in `json` format strictly with the following keys:
- `problem_analysis`: A dictionary containing:
  - `input_output_constraints`: str
  - `explicit_constraints`: str
  - `implicit_constraints`: str
  - `problem_type_identification`: str
- `feasible_complexity_estimation`: A dictionary containing:
  - `estimated_time_complexity`: str
  - `estimated_memory_complexity`: str
  - `potential_resource_bottlenecks`: str
- `possible_algorithms_complexity`: A list of dictionaries, where each dictionary contains:
  - `algorithm_name`: str
  - `time_complexity`: str
  - `space_complexity`: str
  - `algorithm_explanation`: str

Now please analyze the following problem based on the above guidelines:
Problem Description:
{task_description}

Limits:
Time Limit: {time_limits} s
Memory Limit: {memory_limits} MB
"""

planner_prompt = """
## Task
You are a competitive programming resource planner. Your goal is to take a candidate algorithm and create a brief resource-aware plan for implementing it efficiently.

## Input
- Problem description
- Candidate algorithm

## Guidelines
For the given algorithm, provide the following information in JSON format:

1. `data_structures`: A brief explanation of main data structures that will be used, and why they are appropriate for this problem.
2. `algorithm_plan`: A brief explanation of of High-level steps of the algorithm. Focus on logic, not code.
3. `resource_planning_notes`: A brief explanation of of Important considerations for time and memory efficiency, such as:
   - Preprocessing
   - Memory allocation and reuse
   - Avoiding unnecessary copies
   - Handling large inputs
   - Edge cases that could impact performance

## Output Format
Provide your plan in `json` format strictly with the following keys:
- `data_structures`: str
- `algorithm_plan`: str
- `resource_planning_notes`: str

Now plan resources for the problem using the candidate algorithm:
Problem description: 
{task_description}

Candidate algorithm: 
algorithm_name: {algorithm_name}
time_complexity: {time_complexity}
space_complexity: {space_complexity}
algorithm_explanation: {algorithm_explanation}
"""


code_generation_limit_aware_agent_prompt = """
## Task
You are an expert competitive programming coder. Your goal is to implement a {target_language} solution according to a given resource plan, ensuring the code is efficient and follows the provided algorithm and resource constraints.

## Input
- Problem description
- Resource plan containing:
  - `data_structures`: List of data structures to use
  - `algorithm_plan`: High-level steps of the algorithm
  - `resource_planning_notes`: Time/memory optimization advice

## Guidelines
- Implement the algorithm described in `algorithm_plan`.
- Use the specified `data_structures`.
- Follow all `resource_planning_notes` to ensure the solution is efficient in terms of time and memory.
- Include necessary input/output handling as per problem description.
- Ensure the code is complete and runnable.

## Output Format
Provide the {target_language} solution in a markdown code block. 

Now please generate the code solution for the following problem:
Problem description:
{task_description}

Resource plan:
data_structures: {data_structures}
algorithm_plan: {algorithm_plan}
resource_planning_notes: {resource_planning_notes}

Below is a self-contained {target_language} program that implements the solution:
```{target_language}
# Your code here
```
"""

wrong_answer_feedback_prompt = """
execution status: {status}
input: {input}
expected output: {expected_output}
actual output: {actual_output}
"""

time_limit_exceeded_feedback_prompt = """
execution status: {status}
input: {input}
expected output: {expected_output}
actual output: {actual_output}
time comsumed: {time_consumed} seconds
"""

memory_limit_exceeded_feedback_prompt = """
execution status: {status}
input: {input}
expected output: {expected_output}
actual output: {actual_output}
memory used: {memory_used}
"""

compiler_error_feedback_prompt = """
execution status: {status}
error details: {details}
"""

passed_feedback_prompt = """
execution status: {status}
input: {input}
expected output: {expected_output}
actual output: {actual_output}
"""

runtime_error_feedback_prompt = """
execution status: {status}
error details: {details}
"""

feedback_prompt = {
    "PASSED": passed_feedback_prompt,
    "WRONG_ANSWER": wrong_answer_feedback_prompt,
    "TIME_LIMIT_EXCEEDED": time_limit_exceeded_feedback_prompt,
    "MEMORY_LIMIT_EXCEEDED": memory_limit_exceeded_feedback_prompt,
    "COMPILATION_ERROR": compiler_error_feedback_prompt,
    "RUNTIME_ERROR": runtime_error_feedback_prompt
}

code_repair_prompt = """
## Task
You are an expert competitive programming coder. Your goal is to debug and repair a {target_language} solution based on execution feedbacks, ensuring the code meets the problem requirements.

## Input
- Problem description
- {target_language} code
- Execution feedback may include one or more of the following information:
  - `execution status`: e.g., "Wrong Answer", "Time Limit Exceeded", "Runtime Error"
  - `input`: The input that caused the failure
  - `expected output`: The expected output for the given input
  - `actual output`: The actual output produced by the code for the given input
  - `error details`: Compilation or runtime error messages
  - `time consumed`: Time comsumed before exceeding the limit
  - `memory used`: Memory consumed before exceeding the limit

## Guidelines
- Analyze the execution feedback to identify issues in the original code.
- Modify the code to fix bugs, improve efficiency, or handle edge cases as indicated by the feedback.
- Ensure the repaired code is complete, runnable, and adheres to the problem requirements.

## Output Format
Provide the repaired {target_language} solution in a markdown code block.

Now please repair the code solution for the following problem:
Problem description:
{task_description}

Buggy {target_language} code:
{buggy_code}

Execution Feedbacks:
{feedback}

Below is the repaired self-contained {target_language} program:
```{target_language}
# Your repaired code here
```
"""

code_translation_prompt = """Please translate the following {source_language} code to {target_language}. Provide the translated code in a markdown code block:\n```{source_language}\n{source_code}\n```\nBelow is the translated {target_language} code:\n```{target_language}"""

code_translation_cot_prompt = """You are an expert in {source_language} and {target_language} programming languages. Your goal is to translate a given {source_language} code solution to {target_language}. You may start by outlining your thought process. In the end, please provide the translated code in a code block enclosed with ```{target_language} ```.

Here is the {source_language} code to be translated:
```{source_language}
{source_code}
```
"""

code_translation_analysis_prompt = """You are an expert competitive programming algorithm analyst. Your goal is to analyze a given {source_language} code solution and provide a structured algorithm analysis report to guide its translation to {target_language}, taking into account time and memory limits.

## Input
- {source_language} code solution
- Limits: Time and memory limits for the target language implementation.

## Guidelines
### Step 1: Algorithm Identification
- A test string ddentify the used algorithm(s) and the time and space complexity of the {source_language} code.

### Step 2: Alternative Algorithms
- List any alternative algorithms that could be used to solve the same problem, no more than 3.
- For each alternative, provide:
  - `algorithm_name`: A text string representing the name of the algorithm.
  - `time_complexity`: A text string representing the estimated time complexity.
  - `space_complexity`: A text string representing the estimated space complexity.
  - `algorithm_explanation`: A brief text explaining why this algorithm is feasible under the constraints.

## Output Format
Provide your analysis report in `json` format with the following keys:
- `algorithm_identification`: A dictionary containing:
  - `algorithm_name`: string
  - `time_complexity`: string
  - `space_complexity`: string
  - `algorithm_explanation`: string

- `alternative_algorithms`: A list of dictionaries, where each dictionary contains:
  - `algorithm_name`: string
  - `time_complexity`: string
  - `space_complexity`: string
  - `algorithm_explanation`: string

Now please analyze the following code solution:
{source_language} code:
```{source_language}
{source_code}
```

Limits:
Time Limit: {time_limits} s
Memory Limit: {memory_limits} MB
"""

code_translation_limit_aware_agent_prompt = """
## Task
You are an expert competitive programming coder. Your goal is to translate a given {source_language} code solution to {target_language} according to a provided algorithm, ensuring the code is efficient and follows the specified time and memory limits.

## Input
- source code in {source_language}
- algorithm:
  - `algorithm_name`: the algorithm or approach being considered.
  - `time_complexity`: The estimated time complexity.
  - `space_complexity`: The estimated space complexity.
  - `algorithm_explanation`: A brief explanation of why this algorithm is feasible under the constraints.
- Limits: Time and memory limits for the target language implementation.

## Guidelines
- Translate the source code to {target_language} following the provided algorithm.
- Ensure the code is complete and runnable.

## Output Format
Provide the {target_language} solution in a markdown code block.

Now please translate the following code solution:
Source code in {source_language}:
{source_code}

Algorithm:
{algorithm}

Limits:
Time Limit: {time_limits} s
Memory Limit: {memory_limits} MB

Below is a complete self-contained {target_language} program that implements the translated {target_language} solution:
```{target_language}
"""

code_translation_repair_prompt = """
## Task
You are an expert competitive programming coder. Your goal is to debug and repair a {target_language} translation solution based on execution feedbacks.

## Input
- source code in {source_language}
- buggy {target_language} code
- Execution feedback may include one or more of the following information:
  - `execution status`: e.g., "Wrong Answer", "Time Limit Exceeded", "Runtime Error"
  - `input`: The input that caused the failure
  - `expected output`: The expected output for the given input
  - `actual output`: The actual output produced by the code for the given input
  - `error details`: Compilation or runtime error messages
  - `time consumed`: Time comsumed before exceeding the limit
  - `memory used`: Memory consumed before exceeding the limit

## Guidelines
- Analyze the execution feedback to identify issues in the translated code.
- Modify the code to fix bugs, improve efficiency, or handle edge cases as indicated by the feedback.
- Ensure the repaired code is complete, runnable

## Output Format
Provide the repaired {target_language} solution in a markdown code block.
Now please repair the translated code solution:
Source code in {source_language}:
{source_code}

Buggy {target_language} code:
{buggy_code}

Execution Feedbacks:
{feedback}

Below is the repaired self-contained {target_language} program:
```{target_language}
# Your repaired code here
```
"""

self_planning_plan_prompt = """You are an expert competitive programmer. Your goal is to create a detailed step-by-step plan to solve the given problem in a markdown code block:\n```\n{task_description}\n```

## Output Format
Provide your self-planning steps in `json` format strictly with the following keys:
- `plan` : A plain text of the detailed step-by-step plan to accomplish the task.
"""

self_planning_code_generation_prompt = """You are an expert competitive programmer. Your goal is to implement a {target_language} solution according to your self-planning steps. Ensure the code follows the provided plan steps.
## Input
- Problem
- Planning steps

## Guidelines
- Implement the self-planning steps provided.
- Ensure the code is complete and runnable.

## Output Format
Provide the {target_language} solution in a markdown code block.

Now please generate the code solution for the following problem:
Problem:
{task_description}

Planning steps:
{plan}

Below is a self-contained {target_language} program that implements the solution:
```{target_language}
# Your code here
```
"""

code_translation_self_planning_plan_prompt = """You are an expert competitive programmer. Your goal is to create a detailed step-by-step plan to translate the given code solution from {source_language} to {target_language} in a markdown code block:\n```\n{source_code}\n```

## Output Format
Provide your self-planning steps strictly in `json` format with the following keys:
- `plan` : A plain text of the detailed step-by-step plan to accomplish the translation task.
"""

code_translation_self_planning_translation_prompt = """You are an expert competitive programmer. Your goal is to translate a given {source_language} code solution to {target_language} according to your self-planning steps. Ensure the code follows the provided plan steps.
## Input
- Source code in {source_language}
- Planning steps

## Guidelines
- Translate the source code to {target_language} following the self-planning steps.
- Ensure the code is complete and runnable.

## Output Format
Provide the {target_language} solution in a markdown code block.

Now please translate the following code solution:
Source code in {source_language}:
```{source_language}
{source_code}
```

Planning steps:
{plan}
Below is a self-contained {target_language} program that implements the translated {target_language} solution:
```{target_language}
# Your code here
```
"""

code_generation_without_algorithm_exploration_task_analysis_prompt = """# Task
You are a competitive programming problem analyst. Your goal is to read a problem statement and systematically extract all information required for designing an efficient algorithm that satisfies the given time and memory limits.

# Input
Problem: A problem description, including input format, output format, constraints, and any additional context.
Limits: Time and memory limits for the problem.

# Guidelines for Analysis

## Step 1: Problem Analysis
Extract the core structural information of the problem, including input/output constraints, explicit constraints, implicit constraints, and problem type identification.

###  Input and Output Constraints
Identify the Input size range and Output requirements and I/O format properties.

### Explicit Constraints
List all constraints explicitly stated in the problem.

### Implicit Constraints
List all constraints that are not explicitly stated but can be inferred from the problem context.

### Problem Type Identification
Identify the problem type(s) (e.g., graph, DP, greedy, math, string, geometry). Include multiple types if applicable.

## Step 2: Feasible Complexity Estimation
Based on the "Limits", information from Step 1, and general heuristics, estimate feasible time and memory complexities and identify potential resource bottlenecks.

### Time Complexity Estimation
Estimate feasible time complexity using the following heuristics:

### Memory Complexity Estimation
Estimate feasible memory complexity using the following heuristics:

### Potential Resource Bottlenecks
Identify factors that may cause time or memory violations, such as high constant factors, large intermediate structures, recursion depth, heavy data structures, or worst-case combinatorial explosion.

## Step 3: Most Recommended Algorithm
Based on Step 1 and Step 2, infer the most feasible algorithm and its complexities. provide a dictionary with the following keys:
- `algorithm_name`: a text string representing the name of the algorithm.
- `time_complexity`: a text string representing the estimated time complexity.
- `space_complexity`: a text string representing the estimated space complexity.
- `algorithm_explanation`: A brief explanation of why this algorithm is feasible under the constraints.

## Output Format
Provide your analysis strictly in `json` format with the following keys:
- `problem_analysis`: A dictionary containing:
  - `input_output_constraints`: str
  - `explicit_constraints`: str
  - `implicit_constraints`: str
  - `problem_type_identification`: str
- `feasible_complexity_estimation`: A dictionary containing:
  - `estimated_time_complexity`: str
  - `estimated_memory_complexity`: str
  - `potential_resource_bottlenecks`: str
- `most_recommended_algorithm`: A dictionary containing:
  - `algorithm_name`: str
  - `time_complexity`: str
  - `space_complexity`: str
  - `algorithm_explanation`: str

Now please analyze the following problem based on the above guidelines:
Problem Description:
{task_description}

Limits:
Time Limit: {time_limits} s
Memory Limit: {memory_limits} MB
"""

code_generation_without_planner_code_generator_prompt = """
## Task
You are an expert competitive programming coder. Your goal is to implement a {target_language} solution according to a given algorithm, ensuring the code is efficient and follows the provided algorithm and resource constraints.

## Input
- Problem description
- Algorithm:
  - `algorithm_name`: the algorithm or approach being considered.
  - `time_complexity`: The estimated time complexity.
  - `space_complexity`: The estimated space complexity.
  - `algorithm_explanation`: A brief explanation of why this algorithm is feasible under the constraints.

## Guidelines
- Implement the algorithm described.
- Ensure the code is complete and runnable.

## Output Format
Provide the {target_language} solution in a markdown code block. 

Now please generate the code solution for the following problem:
Problem description:
{task_description}

Algorithm:
algorithm_name: {algorithm_name}
time_complexity: {time_complexity}
space_complexity: {space_complexity}
algorithm_explanation: {algorithm_explanation}

Below is a self-contained {target_language} program that implements the solution:
```{target_language}
# Your code here
```
"""

code_translation_analysis_without_algorithm_exploration = """You are an expert competitive programming algorithm analyst. Your goal is to analyze a given {source_language} code solution and provide a structured algorithm analysis report to guide its translation to {target_language}, taking into account time and memory limits.

## Input
- {source_language} code solution
- Limits: Time and memory limits for the target language implementation.

## Guidelines
### Algorithm Identification
- Identify the algorithm(s) used and the time and space complexity of the {source_language} code.

## Output Format
Provide your analysis report in `json` format with the following keys:
- `algorithm_identification`: A dictionary containing:
  - `algorithm_name`
  - `time_complexity`
  - `space_complexity`
  - `algorithm_explanation`

Now please analyze the following code solution:
{source_language} code:
```{source_language}
{source_code}
```

Limits:
Time Limit: {time_limits} s
Memory Limit: {memory_limits} MB
"""


# ==================== Security-Aware Code Generation Prompts ====================

security_analyzer_prompt = """
# Task
You are a security expert specializing in secure code development. Your goal is to analyze a programming problem and identify potential security risks that a developer should consider when implementing the solution.

# Input
Problem Description: A description of the programming task, including function signature, input/output requirements, and examples.

# Guidelines for Analysis

## Step 1: Problem Summary
Provide a brief summary of what the function needs to accomplish.

## Step 2: Language-aware Solution Blueprint
Provide 6-10 ordered steps a correct solution would likely follow (high-level structure + key operations + data flow; NOT code).

## Step 3: Step-by-Step Security Inspection
Inspect the blueprint step by step and identify security considerations and security-sensitive regions, including:
- Trust boundary crossings (external input → internal logic; user input → filesystem/network/parser; etc.)
- Attacker-controlled inputs (direct or indirect)
- Sensitive operations/sinks (file access, command execution, dynamic evaluation, DB queries, deserialization, crypto, auth, redirects, etc.)

im## Step 4: Possible Security Risks
Identify up to **4** specific security risks that may apply to this problem. For each risk, provide:
- `cwe_id`: The CWE identifier (e.g., "CWE-20", "CWE-79", "CWE-89")
- `risk_name`: A short name for the risk
- `risk_description`: Describe how the risk would manifest for the given problem
- `mitigation_strategy`: Where and How to prevent or mitigate this risk

Common security risks to consider:
- Improper Input Validation
- Path Traversal
- OS Command Injection
- Cross-site Scripting (XSS)
- SQL Injection
- Code Injection
- Buffer Overflow
- Information Exposure
- Improper Privilege Management
- Incorrect Default Permissions
- Improper Authentication
- Missing Encryption
- Cross-Site Request Forgery
- Resource Exhaustion
- Deserialization of Untrusted Data
- Open Redirect
- Incorrect Permission Assignment
- Hard-coded Credentials

## Output Format
Provide your analysis in `json` format strictly with the following keys:
- `problem_summary`: str
- `language_aware_solution_blueprint`: str
- `security_considerations`: str
- `possible_security_risks`: A list of dictionaries, where each dictionary contains:
  - `cwe_id`: str
  - `risk_name`: str
  - `risk_description`: str
  - `mitigation_strategy`: str

Now please analyze the following problem:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}
"""

# security_analyzer_prompt = """
# # Task
# You are a security expert specializing in secure code development. Your goal is to analyze a programming problem and identify potential security risks that a developer should consider when implementing the solution.

# # Input
# Problem Description: A description of the programming task, including function signature, input/output requirements, and examples.

# # Guidelines for Analysis

# ## Step 1: Problem Summary
# Provide a brief summary of what the function needs to accomplish.

# ## Step 2: Security Considerations
# Identify general security considerations for this type of problem. Think about:
# - What kind of inputs will the function receive?
# - What operations will be performed on the inputs?
# - What could go wrong from a security perspective?

# ## Step 3: Possible Security Risks
# Identify up to **4** specific security risks that may apply to this problem. For each risk, provide:
# - `cwe_id`: The CWE identifier (e.g., "CWE-20", "CWE-79", "CWE-89")
# - `risk_name`: A short name for the risk
# - `risk_description`: How this risk specifically applies to the given problem
# - `mitigation_strategy`: How to prevent or mitigate this risk

# Common security risks to consider:
# - Improper Input Validation
# - Path Traversal
# - OS Command Injection
# - Cross-site Scripting (XSS)
# - SQL Injection
# - Code Injection
# - Buffer Overflow
# - Information Exposure
# - Improper Privilege Management
# - Incorrect Default Permissions
# - Improper Authentication
# - Missing Encryption
# - Cross-Site Request Forgery
# - Resource Exhaustion
# - Deserialization of Untrusted Data
# - Open Redirect
# - Incorrect Permission Assignment
# - Hard-coded Credentials

# ## Output Format
# Provide your analysis in `json` format strictly with the following keys:
# - `problem_summary`: str
# - `security_considerations`: str
# - `possible_security_risks`: A list of dictionaries, where each dictionary contains:
#   - `cwe_id`: str
#   - `risk_name`: str
#   - `risk_description`: str
#   - `mitigation_strategy`: str

# Now please analyze the following problem:
# Problem Description:
# {problem_description}

# Entry Point Function: {entry_point}
# """

security_testcase_generator_prompt = """
# Task
You are a security testing expert. Your goal is to generate security-focused test cases that will verify whether a code implementation properly handles the specified security risk.

# Input
- Problem Description: The programming task description
- Entry Point: The function name to test
- Target Security Risk: The specific security vulnerability to test for

# Guidelines

## CRITICAL: Function Signature Constraints
**You MUST strictly follow the function signature defined in the Problem Description.**
- DO NOT add new parameters to the function (e.g., do not add `caller`, `session`, `user_id`, etc.)
- DO NOT modify the expected input/output types
- DO NOT assume the function supports features not mentioned in the problem description
- If a security risk requires changing the function signature to test properly (e.g., authorization requires a caller parameter), you should:
  - Skip that specific risk's advanced tests
  - Focus only on input validation aspects that can be tested with the existing signature
  - Test only what the function CAN control with its defined parameters

## Test Case Design
Generate test cases that:
1. Test normal/valid inputs (baseline functionality) - REQUIRED
2. Test edge cases that might trigger the security vulnerability (using ONLY the original function signature)
3. Test malicious inputs that attempt to exploit the vulnerability
4. Test boundary conditions
5. Focus on INPUT VALIDATION: invalid types, boundary values, malformed data, etc.

## Test Code Requirements
- Write complete, executable Python test code
- **Call the function EXACTLY as defined in the problem description** - no extra parameters
- Use assertions to verify expected behavior
- Include a `check(candidate)` function that takes the function to test as argument
- Each test should either pass (secure implementation) or fail/raise exception (insecure implementation)
- For security tests, the secure behavior might be:
  - Raising an appropriate exception (ValueError, TypeError, Exception, etc.)
  - Returning an error indicator
  - Sanitizing/rejecting malicious input
  - Properly validating input before processing
- **DO NOT use threading/concurrency tests unless the problem explicitly requires thread safety**
- **DO NOT test authorization/authentication unless the function signature supports it**

## Output Format
Provide your test suite in `json` format with the following keys:
- `target_risk`: str (the security risk being tested)
- `test_cases`: A list of dictionaries, each containing:
  - `test_input`: str (description of the input)
  - `expected_behavior`: str (what should happen)
  - `test_purpose`: str (what security aspect is being tested)
- `test_code`: str (complete executable Python test code using ONLY the original function signature)

Now generate security test cases:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Target Security Risk:
CWE ID: {cwe_id}
Risk Name: {risk_name}
Risk Description: {risk_description}
Mitigation Strategy: {mitigation_strategy}
"""

security_aware_code_generation_prompt = """
# Task
You are an expert secure code developer. Your goal is to implement a Python solution that not only solves the given problem correctly but also properly handles the specified security risk.

# Input
- Problem Description: The programming task
- Security Risk to Address: The specific vulnerability to prevent
- Mitigation Strategy: How to prevent the vulnerability

# Guidelines
1. Implement the function according to the problem requirements
2. Apply the mitigation strategy to prevent the security vulnerability
3. Include proper input validation
4. Handle edge cases gracefully
5. Use secure coding practices throughout

# Security Best Practices
- Validate all inputs before processing
- Use type checking where appropriate
- Handle exceptions properly
- Avoid using dangerous functions (eval, exec, etc.) unless absolutely necessary and properly sandboxed
- Sanitize user inputs
- Use parameterized queries for database operations
- Validate file paths to prevent path traversal
- Set appropriate permissions for file operations

# Output Format
Provide a complete, self-contained Python function in a markdown code block.

Now implement the secure solution:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Security Risk to Address:
CWE ID: {cwe_id}
Risk Name: {risk_name}
Risk Description: {risk_description}

Mitigation Strategy:
{mitigation_strategy}

Below is a secure Python implementation:
```python
"""

security_aware_code_repair_prompt = """
# Task
You are an expert secure code developer. Your goal is to fix a Python implementation that failed security tests, ensuring it properly handles the specified security risk.

# Input
- Problem Description: The programming task
- Security Risk: The vulnerability that needs to be addressed
- Buggy Code: The current implementation that failed tests
- Execution Feedback: Details about what went wrong

# Guidelines
1. Analyze the execution feedback to understand why the tests failed
2. Identify security vulnerabilities in the current code
3. Fix the code to properly handle the security risk
4. Ensure the fix doesn't break normal functionality
5. Apply proper input validation and error handling

# Output Format
Provide the fixed, complete Python function in a markdown code block.

Now fix the code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Security Risk to Address:
CWE ID: {cwe_id}
Risk Name: {risk_name}
Mitigation Strategy: {mitigation_strategy}

Buggy Code:
```python
{buggy_code}
```

Execution Feedback:
{feedback}

Below is the fixed secure Python implementation:
```python
"""

# ==================== All-Risks Mode Prompts ====================

security_testcase_generator_all_risks_prompt = """
# Task
You are a security testing expert. Your goal is to generate comprehensive security-focused test cases that will verify whether a code implementation properly handles ALL the specified security risks.

# Input
- Problem Description: The programming task description
- Entry Point: The function name to test
- Security Risks: A list of ALL security vulnerabilities to test for

# Guidelines

## CRITICAL: Function Signature Constraints
**You MUST strictly follow the function signature defined in the Problem Description.**
- DO NOT add new parameters to the function (e.g., do not add `caller`, `session`, `user_id`, etc.)
- DO NOT modify the expected input/output types
- DO NOT assume the function supports features not mentioned in the problem description
- If a security risk requires changing the function signature to test properly (e.g., authorization requires a caller parameter), you should:
  - Skip that specific risk's advanced tests
  - Focus only on input validation aspects that can be tested with the existing signature
  - Test only what the function CAN control with its defined parameters

## Test Case Design
Generate test cases that cover applicable security risks:
1. Test normal/valid inputs (baseline functionality) - REQUIRED
2. For each security risk, include edge cases and malicious inputs that can be tested with the EXISTING function signature
3. Test boundary conditions for each applicable vulnerability type
4. Focus on INPUT VALIDATION tests: invalid types, boundary values, malformed data, etc.

## Test Code Requirements
- Write complete, executable Python test code
- **Call the function EXACTLY as defined in the problem description** - no extra parameters
- Use assertions to verify expected behavior
- Include a `check(candidate)` function that takes the function to test as argument
- Each test should either pass (secure implementation) or fail/raise exception (insecure implementation)
- For security tests, the secure behavior might be:
  - Raising an appropriate exception (ValueError, TypeError, Exception, etc.)
  - Returning an error indicator
  - Sanitizing/rejecting malicious input
  - Properly validating input before processing
- **DO NOT use threading/concurrency tests unless the problem explicitly requires thread safety**
- **DO NOT test authorization/authentication unless the function signature supports it**

## Output Format
Provide your test suite in `json` format with the following keys:
- `target_risk`: str (summary of all risks being tested, e.g., "CWE-20, CWE-94, CWE-369")
- `test_cases`: A list of dictionaries, each containing:
  - `test_input`: str (description of the input)
  - `expected_behavior`: str (what should happen)
  - `test_purpose`: str (what security aspect is being tested, include CWE ID)
- `test_code`: str (complete executable Python test code covering ALL risks, using ONLY the original function signature)

Now generate security test cases:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Security Risks to Cover:
{all_risks}
"""

security_aware_code_generation_all_risks_prompt = """
# Task
You are an expert secure code developer. Your goal is to implement a Python solution that not only solves the given problem correctly but also properly handles ALL the specified security risks.

# Input
- Problem Description: The programming task
- Security Risks to Address: ALL identified vulnerabilities to prevent
- Mitigation Strategies: How to prevent each vulnerability

# Guidelines
1. Implement the function according to the problem requirements
2. Apply ALL mitigation strategies to prevent every security vulnerability
3. Include comprehensive input validation
4. Handle all edge cases gracefully
5. Use secure coding practices throughout

# Security Best Practices
- Validate all inputs before processing
- Use type checking where appropriate
- Handle exceptions properly
- Avoid using dangerous functions (eval, exec, etc.) unless absolutely necessary and properly sandboxed
- Sanitize user inputs
- Use parameterized queries for database operations
- Validate file paths to prevent path traversal
- Set appropriate permissions for file operations
- Check for division by zero before arithmetic operations
- Limit resource consumption to prevent DoS

# Output Format
Provide a complete, self-contained Python function in a markdown code block.

Now implement the secure solution:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Security Risks to Address:
{all_risks}

Below is a secure Python implementation that addresses ALL identified risks:
```python
"""

security_aware_code_repair_all_risks_prompt = """
# Task
You are an expert secure code developer. Your goal is to fix a Python implementation that failed security tests, ensuring it properly handles ALL the specified security risks.

# Input
- Problem Description: The programming task
- Security Risks: ALL vulnerabilities that need to be addressed
- Buggy Code: The current implementation that failed tests
- Execution Feedback: Details about what went wrong

# Guidelines
1. Analyze the execution feedback to understand why the tests failed
2. Identify which security vulnerabilities are not properly handled
3. Fix the code to address ALL security risks
4. Ensure the fix doesn't break normal functionality
5. Apply proper input validation and error handling for each risk

# Output Format
Provide the fixed, complete Python function in a markdown code block.

Now fix the code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Security Risks to Address:
{all_risks}

Buggy Code:
```python
{buggy_code}
```

Execution Feedback:
{feedback}

Below is the fixed secure Python implementation that addresses ALL risks:
```python
"""

# ==================== Repair Mode Prompts ====================

insecure_code_analyzer_prompt = """
# Task
You are a security code auditor. Your goal is to analyze insecure code and identify:
1. The intended behavior of the code
2. Functional issues that need fixing
3. Security vulnerabilities that need enhancement

# Input
- Problem Description: What the function should accomplish
- Insecure Code: The buggy/insecure implementation to analyze
- Entry Point: The function name

# Guidelines

## Step 1: Intended Behavior Analysis
Analyze the insecure code and describe:
- What functionality the code is attempting to implement
- What the correct behavior should be based on the problem description
- Whether the core algorithm/logic is sound or needs functional fixes

## Step 2: Functional Issues Identification
Identify any functional bugs or logic errors:
- Incorrect algorithms or logic flow
- Missing edge case handling
- Off-by-one errors, incorrect conditions, etc.
- For each issue, specify:
  - `issue_location`: Where in the code (line/section description)
  - `issue_description`: What's wrong functionally
  - `fix_needed`: How to fix this functional issue

## Step 3: Security Vulnerabilities Identification
Identify security weaknesses and missing protections:
- Missing input validation
- Missing type checking
- Unsafe operations (eval, exec, etc.)
- Missing permission checks
- Information exposure risks
- For each vulnerability, provide:
  - `cwe_id`: The CWE identifier (e.g., "CWE-20", "CWE-78", "CWE-89")
  - `vulnerability_location`: Where in the code
  - `vulnerability_description`: What's the security issue
  - `enhancement_needed`: How to add security protection

## Step 4: Priority Assessment
Determine which fixes should be prioritized:
- Critical functional bugs that break core functionality
- Critical security vulnerabilities that pose immediate risk
- Important enhancements for defense-in-depth

## Output Format
Provide your analysis in `json` format strictly with the following keys:
- `intended_behavior`: str (what the code is trying to accomplish)
- `behavioral_correctness`: str (whether the core logic is correct or needs functional fixes)
- `functional_issues`: A list of dictionaries, each containing:
  - `issue_location`: str
  - `issue_description`: str
  - `fix_needed`: str
- `security_vulnerabilities`: A list of dictionaries, each containing:
  - `cwe_id`: str
  - `vulnerability_location`: str
  - `vulnerability_description`: str
  - `enhancement_needed`: str
- `priority_fixes`: str (which issues should be addressed first and why)

Now analyze the following insecure code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Insecure Code:
```python
{insecure_code}
```
"""

testcase_generator_for_repair_prompt = """
# Task
You are a security testing expert. Your goal is to generate comprehensive test cases that verify both functional correctness and security protections for a code repair task.

# Input
- Problem Description: What the function should do
- Entry Point: The function name to test
- Analysis Results: Identified functional issues and security vulnerabilities
- Insecure Code: The original buggy code (for context)

# Guidelines

## CRITICAL: Function Signature Constraints
**You MUST strictly follow the function signature defined in the Problem Description.**
- DO NOT add new parameters to the function
- DO NOT modify the expected input/output types
- Test only what the function CAN control with its defined parameters

## Test Case Categories

### 1. Functional Correctness Tests (REQUIRED)
- Test normal/valid inputs with expected outputs
- Test edge cases and boundary conditions
- Test scenarios that the buggy code failed on
- Ensure the fixed code produces correct results

### 2. Security Validation Tests
For each identified security vulnerability, generate tests that:
- Attempt to trigger the vulnerability
- Verify that proper validation/sanitization is applied
- Test malicious inputs that should be rejected
- Test boundary conditions for security checks

### 3. Regression Tests
- Ensure fixes don't break existing functionality
- Test interactions between functional fixes and security enhancements

## Test Code Requirements
- Write complete, executable Python test code
- Call the function EXACTLY as defined in the problem description
- Use assertions to verify expected behavior
- Include a `check(candidate)` function
- For security tests, verify that:
  - Malicious inputs raise appropriate exceptions (ValueError, TypeError, etc.)
  - Input validation catches invalid data
  - Proper error messages are returned
- Include helper function `assert_raises` for testing exceptions

## Output Format
Provide your test suite in `json` format with the following keys:
- `functional_tests_summary`: str (summary of functional tests)
- `security_tests_summary`: str (summary of security tests covering which CWE IDs)
- `test_cases`: A list of dictionaries, each containing:
  - `test_category`: str ("functional" or "security")
  - `test_input`: str (description of the input)
  - `expected_behavior`: str (what should happen)
  - `test_purpose`: str (what aspect is being tested, include CWE ID for security tests)
- `test_code`: str (complete executable Python test code)

Now generate test cases:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Insecure Code (for context):
```python
{insecure_code}
```

Analysis Results:
Functional Issues:
{functional_issues}

Security Vulnerabilities:
{security_vulnerabilities}
"""

code_fixer_prompt = """
# Task
You are an expert secure code developer. Your goal is to fix insecure code by addressing both functional bugs and security vulnerabilities.

# Input
- Problem Description: The programming task requirements
- Insecure Code: The buggy/insecure implementation
- Analysis: Identified functional issues and security vulnerabilities
- Test Cases: Generated tests that the fixed code must pass

# Guidelines

## Step 1: Address Functional Issues First
- Fix any logic errors, algorithm bugs, or incorrect implementations
- Ensure the core functionality works correctly
- Handle edge cases properly

## Step 2: Add Security Enhancements
For each identified vulnerability, implement the recommended enhancement:
- Add input validation (type checking, range checking, format validation)
- Add sanitization for dangerous inputs
- Use safe APIs instead of dangerous ones (avoid eval/exec)
- Add proper error handling
- Set appropriate permissions for file operations
- Validate file paths to prevent traversal
- Use parameterized queries for databases

## Step 3: Apply Defense-in-Depth
- Layer multiple security controls where appropriate
- Validate at boundaries (entry points)
- Fail securely (reject invalid input, don't try to "fix" it)
- Provide clear error messages without exposing sensitive info

## Step 4: Ensure Tests Pass
- The fixed code must pass all functional tests
- The fixed code must pass all security tests
- Maintain backward compatibility where appropriate

# Security Best Practices
- Validate all inputs before processing
- Use type checking where appropriate
- Handle exceptions properly
- Avoid dangerous functions unless properly sandboxed
- Sanitize user inputs
- Use parameterized queries for database operations
- Validate file paths to prevent path traversal
- Set appropriate permissions (0o600 or 0o700) for file operations
- Check for division by zero
- Limit resource consumption

# Output Format
Provide the complete, fixed Python function in a markdown code block.

Now fix the insecure code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Insecure Code:
```python
{insecure_code}
```

Functional Issues to Fix:
{functional_issues}

Security Vulnerabilities to Address:
{security_vulnerabilities}

Below is the fixed secure Python implementation:
```python
"""

code_repairer_for_repair_mode_prompt = """
# Task
You are an expert secure code developer. Your goal is to repair code that failed tests, addressing the specific failures identified in the execution feedback.

# Input
- Problem Description: The programming task
- Previous Code: The implementation that failed tests
- Execution Feedback: Details about what tests failed and why
- Original Analysis: The functional and security issues that should be addressed

# Guidelines

## Step 1: Analyze Test Failures
- Understand which tests failed (functional or security)
- Identify the root cause of each failure
- Determine if it's a logic bug or missing validation

## Step 2: Targeted Fixes
- Fix the specific issues causing test failures
- Don't break previously passing tests
- Maintain all security enhancements

## Step 3: Verify Coverage
- Ensure all identified functional issues are addressed
- Ensure all identified security vulnerabilities are mitigated
- Check that the fix handles edge cases

# Output Format
Provide the repaired, complete Python function in a markdown code block.

Now repair the code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Failed Code:
```python
{buggy_code}
```

Execution Feedback:
{feedback}

Original Functional Issues:
{functional_issues}

Original Security Vulnerabilities:
{security_vulnerabilities}

Below is the repaired secure Python implementation:
```python
"""

# ==================== Problem Mode Prompts ====================

testcase_generator_problem_prompt = """
# Task
You are a security testing expert. Your goal is to generate comprehensive security-focused test cases for the given problem, covering potential security vulnerabilities that might arise during implementation.

# Input
- Problem Description: The programming task description
- Entry Point: The function name to test

# Guidelines

## CRITICAL: Function Signature Constraints
**You MUST strictly follow the function signature defined in the Problem Description.**
- DO NOT add new parameters to the function (e.g., do not add `caller`, `session`, `user_id`, etc.)
- DO NOT modify the expected input/output types
- DO NOT assume the function supports features not mentioned in the problem description

## Test Case Design
Generate test cases that cover common security vulnerabilities:
1. Test normal/valid inputs (baseline functionality) - REQUIRED
2. Test edge cases and boundary conditions
3. Test malicious inputs that attempt to exploit common vulnerabilities:
   - Input validation: invalid types, boundary values, malformed data
   - Buffer overflow: extremely large inputs
   - Integer overflow: very large numbers
   - SQL injection: if the problem involves database operations
   - Path traversal: if the problem involves file operations
   - Command injection: if the problem involves system commands
   - Division by zero: arithmetic operations
   - Type confusion: mixed or unexpected types
   - Resource exhaustion: large inputs that might cause memory issues

## Test Code Requirements
- Write complete, executable Python test code
- **Call the function EXACTLY as defined in the problem description** - no extra parameters
- Use assertions to verify expected behavior
- Include a `check(candidate)` function that takes the function to test as argument
- Each test should either pass (secure implementation) or fail/raise exception (insecure implementation)
- For security tests, the secure behavior might be:
  - Raising an appropriate exception (ValueError, TypeError, Exception, etc.)
  - Returning an error indicator
  - Sanitizing/rejecting malicious input
  - Properly validating input before processing
- **DO NOT use threading/concurrency tests unless the problem explicitly requires thread safety**
- **DO NOT test authorization/authentication unless the function signature supports it**

## Output Format
Provide your test suite in `json` format with the following keys:
- `target_risk`: str (summary of security aspects being tested, e.g., "Input validation, boundary conditions, injection attacks")
- `test_cases`: A list of dictionaries, each containing:
  - `test_input`: str (description of the input)
  - `expected_behavior`: str (what should happen)
  - `test_purpose`: str (what security aspect is being tested)
- `test_code`: str (complete executable Python test code covering security aspects, using ONLY the original function signature)

Now generate security test cases:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}
"""

code_generator_problem_prompt = """
# Task
You are an expert secure code developer. Your goal is to implement a Python solution that solves the given problem correctly while following secure coding practices.

# Input
- Problem Description: The programming task

# Guidelines
1. Implement the function according to the problem requirements
2. Follow secure coding practices to prevent common vulnerabilities:
   - Validate all inputs before processing
   - Use type checking where appropriate
   - Handle exceptions properly
   - Avoid using dangerous functions (eval, exec, etc.) unless absolutely necessary and properly sandboxed
   - Sanitize user inputs
   - Use parameterized queries for database operations
   - Validate file paths to prevent path traversal
   - Set appropriate permissions for file operations
   - Check for division by zero before arithmetic operations
   - Limit resource consumption to prevent DoS
3. Handle edge cases gracefully
4. Include proper error handling

# Security Best Practices
- Always validate input types and ranges
- Use try-except blocks to handle potential errors
- Avoid hardcoded credentials or sensitive data
- Use safe string operations
- Implement proper bounds checking
- Handle large inputs efficiently to prevent memory issues

# Output Format
Provide a complete, self-contained Python function in a markdown code block.

Now implement the secure solution:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Below is a secure Python implementation:
```python
"""

code_repairer_problem_prompt = """
# Task
You are an expert secure code developer. Your goal is to fix a Python implementation that failed security tests, ensuring it properly handles security concerns.

# Input
- Problem Description: The programming task
- Buggy Code: The current implementation that failed tests
- Execution Feedback: Details about what went wrong

# Guidelines
1. Analyze the execution feedback to understand why the tests failed
2. Identify security issues in the current code
3. Fix the code to address the security concerns
4. Ensure the fix doesn't break normal functionality
5. Apply proper input validation and error handling

# Output Format
Provide the fixed, complete Python function in a markdown code block.

Now fix the code:
Problem Description:
{problem_description}

Entry Point Function: {entry_point}

Buggy Code:
```python
{buggy_code}
```

Execution Feedback:
{feedback}

Below is the fixed secure Python implementation:
```python
"""