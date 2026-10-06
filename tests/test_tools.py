"""tests/test_tools.py: Unit tests for Code Sentry vulnerability scanner tool.

Verifies detection rules for:
1. Hardcoded secrets / API keys
2. Dangerous code execution (eval / exec)
3. SQL Injection (f-strings / string concatenation)
4. Command Injection (subprocess shell=True, os.system)
5. Insecure Deserialization (pickle, unsafe yaml)
6. Weak Cryptographic Hashing (MD5, SHA-1)
7. Path Traversal & Missing Input Validation
8. Clean code scenarios (no false positives)
9. Edge cases (empty string, comments, whitespace)
"""

import pytest
from tools import scan_vulnerabilities


class TestScanVulnerabilities:
    """Test suite for the pure scan_vulnerabilities tool."""

    # 1. Hardcoded secrets / API keys
    def test_detects_aws_key(self):
        snippet = """
def init_aws():
    aws_key = "AKIA1234567890ABCDEF"
    return aws_key
"""
        result = scan_vulnerabilities(snippet)
        assert result["scanned"] is True
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-SECRET-001")
        assert finding["severity"] == "CRITICAL"
        assert finding["line_number"] == 3

    def test_detects_hardcoded_api_key(self):
        snippet = """api_key = "live_sk_abcdef1234567890123" """
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-SECRET-002")
        assert finding["severity"] == "HIGH"

    def test_detects_hardcoded_password(self):
        snippet = """db_password = "supersecretpassword123" """
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-SECRET-003")
        assert finding["severity"] == "HIGH"

    # 2. Dangerous code execution (eval / exec)
    def test_detects_eval_execution(self):
        snippet = """
def calculate(user_expr):
    return eval(user_expr)
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-RCE-001")
        assert finding["severity"] == "CRITICAL"
        assert finding["line_number"] == 3

    def test_detects_exec_execution(self):
        snippet = """exec(user_code_str)"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        assert any(f["rule_id"] == "SEC-RCE-001" for f in result["findings"])

    # 3. SQL Injection
    def test_detects_sql_injection_fstring(self):
        snippet = """
def get_user(uid):
    cursor.execute(f"SELECT * FROM users WHERE id = '{uid}'")
    return cursor.fetchone()
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-SQL-001")
        assert finding["severity"] == "CRITICAL"
        assert finding["line_number"] == 3

    def test_detects_sql_injection_concatenation(self):
        snippet = """query = "SELECT * FROM accounts WHERE name = '" + username + "'" """
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-SQL-002")
        assert finding["severity"] == "HIGH"

    # 4. Command Injection
    def test_detects_subprocess_shell_true(self):
        snippet = """
import subprocess
def ping_host(host):
    subprocess.run(f"ping {host}", shell=True)
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-CMD-001")
        assert finding["severity"] == "CRITICAL"
        assert finding["line_number"] == 4

    def test_detects_os_system(self):
        snippet = """os.system("ls " + folder)"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-CMD-002")
        assert finding["severity"] == "HIGH"

    # 5. Insecure Deserialization
    def test_detects_pickle_loads(self):
        snippet = """
import pickle
def load_session(data):
    return pickle.loads(data)
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-DESER-001")
        assert finding["severity"] == "CRITICAL"
        assert finding["line_number"] == 4

    def test_detects_unsafe_yaml_load(self):
        snippet = """
import yaml
config = yaml.load(raw_yaml_string)
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-DESER-002")
        assert finding["severity"] == "HIGH"

    def test_ignores_safe_yaml_load(self):
        snippet = """
import yaml
config = yaml.load(raw_yaml_string, Loader=yaml.SafeLoader)
"""
        result = scan_vulnerabilities(snippet)
        assert not any(f["rule_id"] == "SEC-DESER-002" for f in result["findings"])

    # 6. Weak Hashing
    def test_detects_md5_hash(self):
        snippet = """
import hashlib
def hash_pass(pwd):
    return hashlib.md5(pwd.encode()).hexdigest()
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-HASH-001")
        assert finding["severity"] == "MEDIUM"

    def test_detects_sha1_hash(self):
        snippet = """token = hashlib.sha1(secret.encode()).hexdigest()"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        assert any(f["rule_id"] == "SEC-HASH-001" for f in result["findings"])

    # 7. Path Traversal & Missing Validation
    def test_detects_unvalidated_file_open(self):
        snippet = """
def read_log():
    with open(request.args.get("file"), "r") as f:
        return f.read()
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] >= 1
        finding = next(f for f in result["findings"] if f["rule_id"] == "SEC-PATH-001")
        assert finding["severity"] == "HIGH"

    # 8. Clean Code (No false findings)
    def test_clean_code_yields_zero_findings(self):
        snippet = """
def add_numbers(a: int, b: int) -> int:
    \"\"\"Calculates sum of two integers safely.\"\"\"
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] == 0
        assert result["verdict_suggestion"] == "SAFE"
        assert len(result["findings"]) == 0

    def test_clean_parameterized_sql_no_false_positive(self):
        snippet = """
def get_user_secure(user_id: int):
    query = "SELECT id, username, email FROM users WHERE id = %s"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] == 0
        assert result["verdict_suggestion"] == "SAFE"

    # 9. Edge Cases
    def test_empty_snippet(self):
        result = scan_vulnerabilities("")
        assert result["scanned"] is True
        assert result["total_findings"] == 0
        assert result["findings"] == []

    def test_whitespace_only_snippet(self):
        result = scan_vulnerabilities("   \n\t  \n  ")
        assert result["scanned"] is True
        assert result["total_findings"] == 0

    def test_comments_not_flagged(self):
        snippet = """
# In this function, do not use eval(user_input)
# Also avoid SELECT * FROM users WHERE id = ' + uid
# Never run subprocess.run(cmd, shell=True)
def safe_calculator(x, y):
    return x * y
"""
        result = scan_vulnerabilities(snippet)
        assert result["total_findings"] == 0
        assert result["verdict_suggestion"] == "SAFE"
