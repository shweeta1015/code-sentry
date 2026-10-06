import subprocess

def ping_server(target_host):
    # Vulnerable to Command Injection
    cmd = f"ping -c 2 {target_host}"
    return subprocess.run(cmd, shell=True, capture_output=True)
