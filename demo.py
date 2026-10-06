"""demo.py: Automated demonstration script for Code Sentry.

Runs multiple representative code review scenarios demonstrating:
1. Risky Snippet: SQL Injection via f-strings
2. Risky Snippet: Command Injection (subprocess shell=True) & Weak MD5 Hashing
3. Risky Snippet: Hardcoded AWS Credentials & Insecure Pickle Deserialization
4. Clean Snippet: Pure math & greeting functions (SAFE, no false positives)
5. Edge Case: Empty snippet handling

Usage:
    python demo.py [--mock] [--model MODEL]
"""

import argparse
import os
import sys

from main import review_code

# Ensure UTF-8 output encoding across Windows/Linux terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


DEMO_SCENARIOS = [
    {
        "title": "Scenario 1: SQL Injection via f-string",
        "query": "Is this authentication query safe to use in our production login endpoint?",
        "language": "python",
        "code": """def authenticate_user(username, password):
    # Retrieve user from PostgreSQL database
    query = f"SELECT * FROM users WHERE username = '{username}' AND password_hash = '{password}'"
    cursor.execute(query)
    return cursor.fetchone()
""",
    },
    {
        "title": "Scenario 2: Command Injection & Weak Hashing",
        "query": "Please review this diagnostic and password utility function for vulnerabilities.",
        "language": "python",
        "code": """import os
import subprocess
import hashlib

def run_diagnostic(user_host):
    subprocess.run(f"ping -c 4 {user_host}", shell=True)

def store_password(raw_password):
    return hashlib.md5(raw_password.encode()).hexdigest()
""",
    },
    {
        "title": "Scenario 3: Hardcoded Secrets & Insecure Pickle Deserialization",
        "query": "We built this cache loader and AWS sync script. Does it meet enterprise security standards?",
        "language": "python",
        "code": """import pickle

AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"
DATABASE_PWD = "ProductionPassword2026!#"

def restore_session(cached_bytes):
    # Deserializing session payload from untrusted client cookie
    session_data = pickle.loads(cached_bytes)
    return session_data
""",
    },
    {
        "title": "Scenario 4: Clean, Safe Code (No Security Sinks)",
        "query": "Is this calculation utility safe to deploy to our cloud microservice?",
        "language": "python",
        "code": """def calculate_compound_interest(principal: float, rate: float, periods: int) -> float:
    \"\"\"Calculates compound interest without external dependencies.\"\"\"
    if principal < 0 or rate < 0 or periods < 0:
        raise ValueError("Values must be non-negative")
    return principal * ((1 + rate) ** periods)

def format_greeting(user_name: str) -> str:
    return f"Welcome back, {user_name.strip()}!"
""",
    },
]


def run_demo(mock: bool = False, model: str = "gemini-2.5-flash") -> None:
    print("\n" + "#" * 80)
    print("  CODE SENTRY - COMPREHENSIVE SECURITY REVIEW DEMONSTRATION")
    print("#" * 80 + "\n")

    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    effective_mock = mock or not has_key

    if not has_key and not mock:
        print("[i] GEMINI_API_KEY is not set in environment.")
        print("[i] Automatically falling back to --mock mode to demonstrate full workflow.\n")

    for idx, scenario in enumerate(DEMO_SCENARIOS, 1):
        print(f"\n>>> [{idx}/{len(DEMO_SCENARIOS)}] {scenario['title']}")
        review_code(
            query=scenario["query"],
            code_snippet=scenario["code"],
            language=scenario["language"],
            model=model,
            mock=effective_mock,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Code Sentry demo scenarios.")
    parser.add_argument("--mock", action="store_true", help="Force mock execution.")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="Gemini model name.")
    args = parser.parse_args()
    run_demo(mock=args.mock, model=args.model)
