def fibonacci(n: int) -> int:
    """Calculates the n-th Fibonacci number safely."""
    if n < 0:
        raise ValueError("n must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

def build_welcome_message(first_name: str, last_name: str) -> str:
    return f"Welcome to the portal, {first_name.strip()} {last_name.strip()}!"
