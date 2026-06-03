#!/usr/bin/env python3

import sys
import time
import paramiko

# Arguments
ip = sys.argv[1]
user = sys.argv[2]
password = sys.argv[3]
commands = sys.argv[4:]

# Create SSH client
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(
        ip,
        username=user,
        password=password,
        timeout=15,
        look_for_keys=False,
        disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]},
    )
except Exception as e:
    print(f"[ERROR] SSH connection failed: {e}")
    sys.exit(1)

try:
    # Open interactive shell
    shell = client.invoke_shell(width=200, height=50)

    time.sleep(1)

    if shell.recv_ready():
        shell.recv(65535)

    # Disable paging
    shell.send("terminal length 0\n")
    time.sleep(1)

    if shell.recv_ready():
        shell.recv(65535)

    output = ""

    # Execute commands
    for cmd in commands:
        shell.send(cmd + "\n")
        time.sleep(2)

        cmd_output = ""

        while shell.recv_ready():
            cmd_output += shell.recv(65535).decode("utf-8", errors="ignore")
            time.sleep(0.2)

        output += f"\n{'=' * 80}\n"
        output += f"COMMAND: {cmd}\n"
        output += f"{'=' * 80}\n"
        output += cmd_output

    print(output)

finally:
    client.close()
