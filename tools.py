"""tools.py: Vulnerability scanning tool for Code Sentry.

This module defines `scan_vulnerabilities`, a pure and testable static/heuristic
vulnerability scanner for code snippets. It is designed to be exposed directly to
the Google GenAI SDK as a callable tool.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class VulnerabilityRule:
    """Represents a security rule evaluated against code lines."""

    def __init__(
        self,
        rule_id: str,
        category: str,
        severity: str,
        pattern: str,
        description: str,
        recommendation: str,
        flags: int = re.IGNORECASE,
        negative_pattern: Optional[str] = None,
    ):
        self.rule_id = rule_id
        self.category = category
        self.severity = severity.upper()
        self.regex = re.compile(pattern, flags)
        self.negative_regex = (
            re.compile(negative_pattern, flags) if negative_pattern else None
        )
        self.description = description
        self.recommendation = recommendation

    def matches(self, line: str) -> bool:
        """Returns True if the line triggers this rule and doesn't match negative pattern."""
        if not self.regex.search(line):
            return False
        if self.negative_regex and self.negative_regex.search(line):
            return False
        return True


# Rule set covering the required security risk patterns:
# 1. Hardcoded secrets / credentials / API keys
# 2. Use of eval() / exec() on untrusted input
# 3. SQL queries built via string concatenation or f-strings (SQL injection)
# 4. subprocess calls with shell=True or os.system
# 5. Insecure deserialization (pickle, unsafe yaml)
# 6. Weak or deprecated hashing (md5, sha1)
# 7. Missing input validation on user-controlled data (path traversal, unvalidated file operations)
VULNERABILITY_RULES: List[VulnerabilityRule] = [
    # 1. Hardcoded secrets & credentials
    VulnerabilityRule(
        rule_id="SEC-SECRET-001",
        category="Hardcoded Secret / API Key",
        severity="CRITICAL",
        pattern=r"(?:AKIA[0-9A-Z]{16}|ghp_[0-9a-zA-Z]{36}|xox[baprs]-[0-9a-zA-Z\-]{10,})",
        description="Found a recognized API token or AWS access key format hardcoded in source code.",
        recommendation="Extract credentials into environment variables (os.environ) or a secrets manager (Vault, AWS Secrets Manager).",
    ),
    VulnerabilityRule(
        rule_id="SEC-SECRET-002",
        category="Hardcoded Secret / API Key",
        severity="HIGH",
        pattern=r"""(?i)(?:api_key|apikey|secret_key|private_key|access_token|auth_token)\s*=\s*['"][a-zA-Z0-9_\-\.]{12,}['"]""",
        negative_pattern=r"""(?i)(?:YOUR_API_KEY|REPLACE_ME|CHANGEME|TODO|TEST_KEY|DUMMY|ENV|os\.getenv|os\.environ)""",
        description="Possible hardcoded API key or private secret assigned directly as a string literal.",
        recommendation="Store sensitive tokens outside the codebase using environment variables (.env with python-dotenv) or secure key vaults.",
    ),
    VulnerabilityRule(
        rule_id="SEC-SECRET-003",
        category="Hardcoded Secret / API Key",
        severity="HIGH",
        pattern=r"""(?i)(?:password|passwd|pwd)\s*=\s*['"][^'"]{5,}['"]""",
        negative_pattern=r"""(?i)(?:your_password|replace_me|todo|placeholder|getenv|os\.environ|test_pwd)""",
        description="Plaintext password assigned as a string literal in source code.",
        recommendation="Never store plaintext passwords in source control. Load passwords dynamically at runtime from environment variables.",
    ),
    VulnerabilityRule(
        rule_id="SEC-SECRET-004",
        category="Hardcoded Secret / API Key",
        severity="CRITICAL",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        description="Cryptographic private key block found embedded directly in source code.",
        recommendation="Store private keys in a secure file location with restricted permissions (e.g., chmod 600) or a hardware security module (HSM).",
    ),
    # 2. Use of eval() / exec()
    VulnerabilityRule(
        rule_id="SEC-RCE-001",
        category="Arbitrary Code Execution (eval/exec)",
        severity="CRITICAL",
        pattern=r"""\b(?:eval|exec)\s*\([^)]*[\w\.\(\)\[\]]""",
        description="Use of eval() or exec() allows dynamic execution of arbitrary code, enabling Remote Code Execution (RCE) if input is user-influenced.",
        recommendation="Avoid eval() and exec(). Use ast.literal_eval() for safe literal evaluation or explicitly parse structured inputs (e.g. JSON/dataclasses).",
    ),
    # 3. SQL injection via string concatenation or f-strings
    VulnerabilityRule(
        rule_id="SEC-SQL-001",
        category="SQL Injection",
        severity="CRITICAL",
        pattern=r"""(?i)(?:execute|raw|cursor\.execute)\s*\(\s*f["'].*(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|DROP|ALTER)""",
        description="SQL query dynamically formatted using an f-string. This exposes the database to severe SQL injection vulnerabilities.",
        recommendation="Use parameterized queries with placeholder syntax (e.g., cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))).",
    ),
    VulnerabilityRule(
        rule_id="SEC-SQL-002",
        category="SQL Injection",
        severity="HIGH",
        pattern=r"""(?i)["'].*(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\s+.*["']\s*(?:\+|\%|\.format\()""",
        description="SQL query constructed via string concatenation ('+') or legacy formatting (%), creating SQL injection risks.",
        recommendation="Switch to parameterized queries or an ORM that safely escapes input values automatically.",
    ),
    # 4. subprocess calls with shell=True / os.system
    VulnerabilityRule(
        rule_id="SEC-CMD-001",
        category="Command Injection",
        severity="CRITICAL",
        pattern=r"""subprocess\.(?:Popen|run|call|check_call|check_output)\s*\(.*shell\s*=\s*True""",
        description="Subprocess invocation with shell=True passes strings directly through the shell interpreter, enabling command injection.",
        recommendation="Set shell=False and pass arguments as an explicit sequence of strings (e.g., subprocess.run(['cmd', arg1, arg2])). Use shlex.quote if shell is required.",
    ),
    VulnerabilityRule(
        rule_id="SEC-CMD-002",
        category="Command Injection",
        severity="HIGH",
        pattern=r"""\bos\.(?:system|popen)\s*\(""",
        description="os.system() or os.popen() spawns an underlying shell command that is highly vulnerable to command injection.",
        recommendation="Replace os.system/os.popen with subprocess.run(..., shell=False) using arguments as a list.",
    ),
    # 5. Insecure deserialization
    VulnerabilityRule(
        rule_id="SEC-DESER-001",
        category="Insecure Deserialization",
        severity="CRITICAL",
        pattern=r"""\b(?:pickle|_pickle)\.loads?\s*\(""",
        description="Python pickle deserialization can execute arbitrary code during unpickling via __reduce__ payloads.",
        recommendation="Use safe data formats such as JSON, Protocol Buffers, or MessagePack instead of pickle for untrusted data.",
    ),
    VulnerabilityRule(
        rule_id="SEC-DESER-002",
        category="Insecure Deserialization",
        severity="HIGH",
        pattern=r"""\byaml\.(?:load|unsafe_load)\s*\([^)]*(?<!Loader=yaml\.SafeLoader)(?<!Loader=SafeLoader)\)?""",
        negative_pattern=r"""(?i)SafeLoader""",
        description="yaml.load() without SafeLoader can instantiate arbitrary Python objects and execute code.",
        recommendation="Use yaml.safe_load(data) or pass Loader=yaml.SafeLoader explicitly.",
    ),
    # 6. Weak or deprecated hashing (md5, sha1)
    VulnerabilityRule(
        rule_id="SEC-HASH-001",
        category="Weak Cryptographic Hashing",
        severity="MEDIUM",
        pattern=r"""\bhashlib\.(?:md5|sha1)\s*\(""",
        description="MD5 and SHA-1 are cryptographically broken algorithms susceptible to collision attacks, and must not be used for security or passwords.",
        recommendation="Use modern secure hash algorithms such as SHA-256 / SHA-512 for checksums, or bcrypt / argon2id / scrypt for password hashing.",
    ),
    # 7. Missing input validation on user-controlled data / Path traversal
    VulnerabilityRule(
        rule_id="SEC-PATH-001",
        category="Path Traversal / Missing Input Validation",
        severity="HIGH",
        pattern=r"""\bopen\s*\(\s*(?:request\.(?:args|form|values)|user_input|filename|filepath|path)\b""",
        description="File open operation directly consumes user-controlled input without path validation, enabling Path Traversal (Arbitrary File Read/Write).",
        recommendation="Sanitize file paths using os.path.basename(), resolve canonical paths with os.path.realpath(), and ensure the path is restricted within an allowed base directory.",
    ),
    VulnerabilityRule(
        rule_id="SEC-VAL-001",
        category="Missing Input Validation",
        severity="MEDIUM",
        pattern=r"""\b(?:redirect|send_file)\s*\(\s*request\.(?:args|form|values)""",
        description="Unvalidated user input passed directly to redirect or send_file, leading to Open Redirect or arbitrary file download.",
        recommendation="Validate against an allowlist of permitted destinations or ensure paths are strictly bounded.",
    ),
]


def scan_vulnerabilities(
    code_snippet: str,
    language: str = "python",
) -> Dict[str, Any]:
    """Scans a code snippet for common security vulnerabilities and risky patterns.

    This function performs static heuristic and pattern-based security analysis
    against provided source code. It inspects code for hardcoded secrets,
    command injection (subprocess shell=True, os.system), arbitrary execution
    (eval/exec), SQL injection (string formatting/f-strings), insecure deserialization
    (pickle/unsafe yaml), weak hashing (MD5/SHA1), and path traversal / missing input validation.

    Args:
        code_snippet: Plain text source code to scan.
        language: Programming language hint (e.g. 'python', 'javascript', 'sql').
            Defaults to 'python'.

    Returns:
        A structured dictionary containing:
            - scanned: Boolean flag indicating if scan completed
            - total_findings: Total number of identified vulnerabilities
            - severity_counts: Dictionary tally of findings by severity level
            - findings: List of finding records, each with rule_id, category,
              severity, line_number, line_content, description, and recommendation
            - language: The language evaluated
            - message: Informational status summary
    """
    if not code_snippet or not code_snippet.strip():
        return {
            "scanned": True,
            "total_findings": 0,
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "findings": [],
            "language": language,
            "message": "Empty or whitespace-only code snippet provided; no vulnerabilities detected.",
        }

    lines = code_snippet.splitlines()
    findings: List[Dict[str, Any]] = []
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    # To avoid duplicate reports on the same line for the same rule
    seen_matches = set()

    for line_idx, line in enumerate(lines, start=1):
        stripped_line = line.strip()
        # Skip comment-only lines in Python / Shell / JS / C-style
        if stripped_line.startswith(("#", "//", "/*", "*")):
            continue

        for rule in VULNERABILITY_RULES:
            if rule.matches(line):
                match_key = (line_idx, rule.rule_id)
                if match_key in seen_matches:
                    continue
                seen_matches.add(match_key)

                finding_record = {
                    "rule_id": rule.rule_id,
                    "category": rule.category,
                    "severity": rule.severity,
                    "line_number": line_idx,
                    "line_content": line.strip()[:160],  # bounded length
                    "description": rule.description,
                    "recommendation": rule.recommendation,
                }
                findings.append(finding_record)
                if rule.severity in severity_counts:
                    severity_counts[rule.severity] += 1
                else:
                    severity_counts[rule.severity] = 1

    verdict_label = (
        "HIGH RISK"
        if (severity_counts["CRITICAL"] > 0 or severity_counts["HIGH"] > 0)
        else ("NEEDS ATTENTION" if severity_counts["MEDIUM"] > 0 else "SAFE")
    )

    return {
        "scanned": True,
        "total_findings": len(findings),
        "verdict_suggestion": verdict_label,
        "severity_counts": severity_counts,
        "findings": findings,
        "language": language,
        "message": (
            f"Scan completed. Found {len(findings)} potential security risk(s)."
            if findings
            else "Scan completed. No recognized security vulnerabilities found in snippet."
        ),
    }
