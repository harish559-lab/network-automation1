#!/usr/bin/env python3
import sys, time, paramiko

ip       = sys.argv[1]
user     = sys.argv[2]
password = sys.argv[3]
commands = sys.argv[4:]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=user, password=password, timeout=15, look_for_keys=False)
except Exception as e:
    print(f"[ERROR] SSH connection failed: {e}")
    sys.exit(1)

shell = client.invoke_shell(width=200, height=50)
time.sleep(1)
shell.recv(65535)

output = ""

shell.send("terminal length 0
")
time.sleep(1)
shell.recv(65535)

for cmd in commands:
    shell.send(cmd + "
")
    time.sleep(2)
    chunk = shell.recv(65535).decode("utf-8", errors="ignore")
    output += chunk
    print(f"[CMD] {cmd}", flush=True)
    print(chunk, flush=True)

client.close()
print(output)
