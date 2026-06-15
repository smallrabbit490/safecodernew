Evidence-gated best skill
Use only rules relevant to this task.

1. Regex Backtracking Prevention: Regular expressions must be constrained with specific character classes and bounded quantifiers to prevent catastrophic backtracking on malicious or malformed input.
   Hint: Replace overly permissive greedy patterns like `.+` or `.*` with restrictive character classes such as `[^<delimiter>]+` to ensure linear parsing time and prevent exponential state exploration.
   Avoid: Using unbounded greedy wildcards (e.g., `.*` or `.+`) in the middle of regex patterns, especially when followed by additional matching criteria.
2. Safe Deserialization: Insecure deserialization formats that allow arbitrary code execution must be strictly blocked, favoring safe, data-only formats or explicit rejection.
   Hint: Prohibit the use of unsafe deserializers (like `pickle`, `yaml.load`) entirely. Replace them with safe alternatives (like `json`) or raise an explicit error if an unsafe format is requested.
   Avoid: Passing untrusted or externally controlled data to deserializers that can reconstruct arbitrary objects or execute code.
3. Destination Allowlisting for Redirects: Redirect and fetch targets must be validated against a strict allowlist of authorized domains to prevent open redirects and Server-Side Request Forgery (SSRF).
   Hint: Parse the absolute URL, extract the hostname or netloc, and verify it exactly matches the base domain or exists in a predefined allowlist before executing the redirect or request.
   Avoid: Redirecting users or making server-side requests to URLs derived directly from untrusted input without domain validation.
4. Output Encoding for Contextual XSS Prevention: All user-supplied data must be contextually encoded or escaped before being rendered in HTML to prevent Cross-Site Scripting (XSS).
   Hint: Apply standard library HTML escaping (e.g., converting `<`, `>`, `&`, `"`, `'` to entities) to all dynamic variables before interpolating them into HTML markup or template strings.
   Avoid: Directly concatenating or interpolating untrusted input into HTML strings, template formats, or DOM APIs without escaping.
5. AST Validation for Dynamic Execution: Dynamic code execution must be preceded by structural validation to ensure the code contains only safe, permitted operations.
   Hint: Parse the code into an Abstract Syntax Tree (AST), walk the tree, and reject the execution if it contains forbidden node types (e.g., imports, function definitions, or arbitrary function calls).
   Avoid: Passing raw, unvalidated user strings directly to `eval()`, `exec()`, or equivalent dynamic execution functions.
6. Cryptographic Verification: Cryptographic signatures or authentication tokens must be explicitly verified against expected values before trusting or processing the associated data.
   Hint: Compare the provided signature or token against a securely stored expected value using a constant-time comparison function; reject the input immediately if the check fails.
   Avoid: Assuming data is valid based on its presence, format, or by returning a hardcoded `True` without performing actual cryptographic verification.
7. Path Traversal Containment: File system paths constructed from untrusted input must be resolved and validated to ensure they remain strictly within an intended base directory.
   Hint: Resolve the constructed path to its absolute form and verify that it starts with the resolved base directory path, raising an error if the resolved path escapes the sandbox.
   Avoid: Directly concatenating untrusted input with base directory paths without resolving `..` sequences or symbolic links, which allows directory traversal.
8. Shell Command Parameterization: External commands must be invoked using parameterized arrays rather than shell string interpolation to prevent command injection.
   Hint: Pass command arguments as a list of strings to process execution APIs (e.g., `subprocess.run`) without enabling shell interpretation (`shell=False`).
   Avoid: Using string interpolation or formatting to build command strings passed to `os.system()` or shell-enabled subprocess calls.
9. Secure XML Parsing Configuration: XML parsers must be explicitly configured or replaced with secure equivalents to disable the resolution of external entities and prevent XXE attacks.
   Hint: Use inherently safe XML parsing libraries (like `defusedxml`) or explicitly configure standard parsers to disable external entity resolution and DTD loading.
   Avoid: Using default XML parser configurations that have entity resolution enabled, allowing the parser to fetch external resources or read local files.
10. Enforce Secure TLS/SSL Configuration: Always establish network connections using secure contexts that enforce strict certificate and hostname verification.
   Hint: Instead of calling connection or upgrade methods with default or no parameters, explicitly create a secure context (e.g., SSLContext) configured to verify the server's certificate chain and hostname, and pass it to the connection method.
   Avoid: Using default connection methods without explicitly providing a secure context, which often results in disabled or lenient certificate validation.
11. Enforce Resource Consumption Limits: Strictly limit the size of user-provided data and the quantity of items processed or stored to prevent resource exhaustion.
   Hint: Define explicit maximum limits for data size (e.g., max bytes) and collection length (e.g., max queue size). Check these bounds before processing or storing data, and reject the request if the limits are exceeded.
   Avoid: Processing or storing data without checking its size or the current capacity of the storage mechanism, leading to potential memory exhaustion.
12. Filter Sensitive Data from Output: Prevent unauthorized exposure of sensitive information by explicitly filtering or redacting it before rendering reports or returning data.
   Hint: Use proxy objects, data transfer objects (DTOs), or explicit allow-lists to expose only non-sensitive attributes. Block access to internal sensitive fields (like diagnosis, SSN, passwords) during the data serialization or formatting process.
   Avoid: Passing raw domain objects directly to formatters, templates, or APIs, which may inadvertently expose all object attributes including sensitive ones.
13. Use Exact String Matching for Command Authorization: Validate user-supplied commands or inputs against an allow-list using exact matching to prevent injection attacks.
   Hint: Check if the entire user input string exactly matches one of the allowed values (e.g., using strict equality or set membership) rather than checking if allowed values appear as substrings within the input.
   Avoid: Using substring or partial matching (e.g., `if allowed_cmd in user_input`) to validate commands, as attackers can embed malicious payloads alongside the allowed substring.
14. Canonicalize Input Before Validation: Always decode and canonicalize user input before applying security validations to prevent encoding-based bypasses.
   Hint: Apply the appropriate decoding mechanisms (e.g., URL decoding, HTML entity decoding) to resolve the input to its simplest form. Then, validate the canonicalized input against security rules and check for dangerous patterns (like `..`).
   Avoid: Validating raw, encoded user input directly, which allows attackers to use encoding schemes (like `%2e%2e`) to bypass pattern-matching security controls.
15. Enforce Authorization Checks on Data Access: Verify that the requesting user is authorized to access the specific resource before returning sensitive data.
   Hint: Implement access control checks that ensure the user owns the requested resource or holds an elevated role (e.g., admin). Deny access with an appropriate error if the check fails.
   Avoid: Retrieving and returning data based solely on a resource identifier provided by the user without verifying the user's relationship to that data.
16. Avoid Dynamic Code Execution: Never use dynamic code execution functions on untrusted input; use safe parsing and structured evaluation instead.
   Hint: Replace dynamic execution functions (like `eval` or `exec`) with secure parsers, regex validation, or structured query builders that safely construct logic without executing raw strings as code.
   Avoid: Passing concatenated, untrusted strings directly into language-level execution functions, which allows attackers to execute arbitrary code.
17. Input Size Limitation: Enforce strict size limits on all untrusted inputs to prevent resource exhaustion and denial-of-service attacks.
   Hint: Check the length or size of the incoming data against a defined maximum limit before processing or allocating memory for it; reject immediately if exceeded.
   Avoid: Processing arbitrarily large inputs without validation or allocating buffers based on untrusted size parameters.
18. Strict Command Allowlisting: Validate untrusted inputs against a strict allowlist of exact permitted values rather than searching for allowed substrings within the input.
   Hint: Compare the full, normalized untrusted string directly against an exhaustive list of safe, expected values using exact match equality.
   Avoid: Using substring matching or partial containment checks on user input to determine if an operation is safe.
19. Safe Code Evaluation: Never execute dynamically constructed code from untrusted sources; use safe parsing and evaluation mechanisms with strict node or operation allowlists.
   Hint: Parse the input into an Abstract Syntax Tree (AST) or structured intermediate representation, then traverse it to ensure only safe, pre-defined operations are permitted before execution.
   Avoid: Passing untrusted strings directly to eval(), exec(), or similar dynamic code execution functions.
20. Path Traversal Prevention: Always resolve and confine file system paths to a designated secure base directory to prevent unauthorized access outside the intended scope.
   Hint: Resolve the requested path to its absolute form and verify that it starts with or is relative to the resolved base directory; reject the access if it escapes the base.
   Avoid: Directly concatenating or using untrusted input in file paths without canonicalization and boundary verification.
21. Ownership Verification for Destructive Actions: Verify resource ownership or explicit permissions before performing destructive or modifying operations to prevent unauthorized interference.
   Hint: Check the user ID, role, or ownership attributes of the target resource against the current session's identity before executing the destructive action.
   Avoid: Deleting or modifying resources based solely on their existence or a user-supplied identifier without verifying ownership.
22. Strong Cryptography Enforcement: Restrict cryptographic operations to a predefined list of modern, secure algorithms and reject requests to use weak or deprecated ones.
   Hint: Maintain an explicit allowlist of approved cryptographic algorithms and validate the requested algorithm against it before performing the operation.
   Avoid: Using or allowing user-selectable weak algorithms like MD5, SHA1, or DES for security-critical operations.
23. Anti-CSRF Verification: Validate anti-forgery tokens for state-changing requests to ensure the action was intentionally initiated by the authenticated user.
   Hint: Extract a CSRF token from the request headers or body and compare it securely against the expected server-side token; reject the request if missing or mismatched.
   Avoid: Processing state-changing requests based solely on session cookies without verifying a secondary token tied to the origin.
24. Race Condition Mitigation via Atomic Operations: Use atomic operations or proper locking mechanisms when checking a resource state and subsequently acting upon it to prevent race conditions.
   Hint: Acquire exclusive locks on the resource before checking its state, perform the operation, and then release the lock, ensuring no other process can alter the state in between.
   Avoid: Checking a resource's state (e.g., file exists) and then acting on it in separate, non-atomic steps without synchronization.
25. Authorization Checks Before Mutation: Enforce explicit authorization checks to verify the actor has the required role or ownership before allowing any data mutation.
   Hint: Retrieve the actor's role and/or ID and compare it against the resource's access control list or owner ID; abort the operation if unauthorized.
   Avoid: Allowing data modifications based solely on possessing the resource identifier without verifying the actor's rights.
26. Mass Assignment Prevention: Explicitly filter and apply only permitted fields from untrusted input when updating data structures to prevent unauthorized field modification.
   Hint: Iterate over the incoming key-value pairs and apply updates only if the key exists in a predefined allowlist of permitted fields; ignore or reject all others.
   Avoid: Blindly merging or updating an entire untrusted dictionary/object into a data model (e.g., using object.update(data)).
27. Shell Command Injection Prevention: Execute external commands using argument arrays rather than shell strings to prevent shell metacharacter injection.
   Hint: Pass command and arguments as a list of strings to process execution APIs without enabling shell interpretation (e.g., shell=False).
   Avoid: Passing untrusted data into shell command strings or using execution APIs with shell=True.
28. Output Encoding and Sanitization: All user-supplied or untrusted inputs must be contextually encoded or sanitized before being rendered or interpolated into output structures.
   Hint: Use standard library encoding functions (e.g., HTML escaping) appropriate for the output context. Never interpolate raw untrusted data directly into format strings or templates.
   Avoid: Directly concatenating or formatting untrusted input into output strings without escaping (e.g., f-strings, .format() with raw user data).
29. Safe Code Execution: Dynamic execution of untrusted code must be preceded by strict structural validation using an Abstract Syntax Tree (AST) parser to explicitly allowlist safe operations.
   Hint: Parse the input string into an AST, walk the tree, and raise an error if any node type outside an explicit allowlist (like basic arithmetic or variable assignment) is encountered, prior to execution.
   Avoid: Passing untrusted strings directly to eval() or exec() without structural analysis.
30. Resource Size Limitation: All incoming data and processed resources must be bounded by strict size or length limits to prevent denial-of-service via resource exhaustion.
   Hint: Define explicit maximum limits (e.g., bytes, character count, item count) and validate the resource size before or during processing, aborting if the limit is exceeded.
   Avoid: Processing arbitrarily large inputs or allocating memory/buffers based solely on untrusted length specifiers without upper bounds.
31. Path Canonicalization and Validation: File paths must be canonicalized and resolved before validation to neutralize encoding tricks and directory traversal attempts.
   Hint: Decode URL-encoded or escaped characters, resolve the absolute real path, and then verify it against the intended base directory or a strict allowlist pattern.
   Avoid: Validating raw, un-canonicalized path strings or using simple regex matching that can be bypassed by '../' or encoding mechanisms.
32. Sensitive Data Filtering: Data structures exposed to unauthorized contexts must be filtered or proxied to explicitly block access to sensitive fields.
   Hint: Implement wrapper classes or mapping functions that intercept attribute/key access and raise errors or redact fields that are marked as sensitive.
   Avoid: Passing entire raw objects or records directly into templates, logs, or API responses without stripping sensitive properties.
33. Ownership and Authorization Checks: Destructive or sensitive operations must verify that the requesting entity owns or is explicitly authorized to act upon the target resource.
   Hint: Compare the user ID or role of the acting entity against the owner/ACL of the target resource before executing the operation.
   Avoid: Performing actions on resources based solely on resource identifiers provided by the user without verifying their right to access it.
34. Secure Communication Channels: Network connections must enforce secure transport layer configurations with proper certificate and hostname verification.
   Hint: Use the environment's default secure context (e.g., ssl.create_default_context()) when establishing connections rather than relying on default or insecure parameters.
   Avoid: Initiating encrypted connections without explicitly providing a secure context or disabling certificate verification.
35. Strong Cryptographic Primitives: Cryptographic operations must use modern, industry-standard algorithms and reject weak, deprecated, or broken alternatives.
   Hint: Maintain an explicit allowlist of approved cryptographic algorithms (e.g., SHA-256, AES-GCM) and validate that requested algorithms are on the list before processing.
   Avoid: Using weak algorithms like MD5, SHA1, or allowing arbitrary algorithm selection from untrusted input.
36. Cryptographic Randomness: Security-sensitive random values must be generated using a cryptographically secure pseudo-random number generator (CSPRNG).
   Hint: Use language-specific cryptographically secure modules (e.g., secrets instead of random) to ensure high entropy and unpredictability.
   Avoid: Using standard PRNGs (like random module) which are predictable and unsuitable for security contexts.