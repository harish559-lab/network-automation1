#!/usr/bin/env python3
"""
switch_cmd.py  —  Send commands to HFCL switch over SSH using Paramiko.
Usage:
  python3 switch_cmd.py <ip> <user> <password> "cmd1" "cmd2" ...
"""
import sys, time, paramiko

ip       = sys.argv[1]
user     = sys.argv[2]
password = sys.argv[3]
commands = sys.argv[4:]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=user, password=password,
                   timeout=15, look_for_keys=False)
except Exception as e:
    print(f"[ERROR] SSH connection failed: {e}")
    sys.exit(1)

shell = client.invoke_shell(width=200, height=50)
time.sleep(1)
shell.recv(65535)   # flush banner

output = ""

# Disable pagination — prevents '-- more --' from blocking output
shell.send("terminal length 0\n")
time.sleep(1)
shell.recv(65535)

for cmd in commands:
    shell.send(cmd + "\n")
    time.sleep(2)       # 2s wait for slower config commands
    chunk = shell.recv(65535).decode("utf-8", errors="ignore")
    output += chunk
    print(f"[CMD] {cmd}", flush=True)
    print(chunk, flush=True)

client.close()
print(output)
