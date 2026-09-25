"""
common.py
=========
Shared utilities for all test scripts.

Combines:
  - Your original switch_cmd.py (Paramiko interactive shell, terminal length 0,
    disabled rsa-sha2 algorithms — all preserved exactly)
  - pyATS device wrappers (connect, execute, configure)
  - Assertion helpers (assert_output, assert_not_in_output)
  - Port / VLAN / MAC helpers
  - Wait / convergence helpers
  - Cleanup helpers

Import in any test script:
    from lib.common import (
        connect_devices, send_cmd, send_config,
        assert_output, assert_not_in_output,
        port_up, port_down, create_vlan, delete_vlan,
        get_mac_table, clear_mac_table, wait, wait_for_convergence
    )
"""

import re
import time
import logging
import paramiko

from lib.config_loader import cfg, timer

log = logging.getLogger(__name__)


# =============================================================================
# PARAMIKO SSH — from your switch_cmd.py, preserved exactly
# =============================================================================

def ssh_run(ip: str, user: str, password: str, *commands: str) -> str:
    """
    Open an interactive SSH shell to the switch, send commands,
    collect output, close.

    Preserved from your switch_cmd.py:
      - terminal length 0 (disable paging)
      - disabled rsa-sha2-256 / rsa-sha2-512 (HFCL SSH quirk)
      - shell width=200 so long lines don't wrap

    Returns
    -------
    str
        Combined CLI output for all commands.
    """
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
        log.error(f"[SSH] Connection to {ip} failed: {e}")
        raise

    try:
        shell = client.invoke_shell(width=200, height=50)
        time.sleep(1)
        if shell.recv_ready():
            shell.recv(65535)

        # Disable paging — critical for HFCL
        shell.send("terminal length 0\n")
        time.sleep(1)
        if shell.recv_ready():
            shell.recv(65535)

        output = ""
        for cmd in commands:
            shell.send(cmd + "\n")
            time.sleep(2)
            cmd_output = ""
            while shell.recv_ready():
                cmd_output += shell.recv(65535).decode("utf-8", errors="ignore")
                time.sleep(0.2)
            output += f"\n{'=' * 80}\nCOMMAND: {cmd}\n{'=' * 80}\n{cmd_output}"
            log.debug(f"[SSH:{ip}] {cmd}\n{cmd_output}")

        return output

    finally:
        client.close()


def ssh_run_from_cfg(device_name: str, *commands: str) -> str:
    """
    Convenience wrapper: reads IP/user/password from lab_config.yaml.

    ssh_run_from_cfg('HFCL', 'show vlan brief', 'show interface status')
    """
    d = cfg['devices'][device_name]
    return ssh_run(d['host'], d['username'], d['password'], *commands)


# =============================================================================
# PYATS DEVICE HELPERS
# =============================================================================

def connect_devices(testbed, *device_names):
    """
    Connect to one or more devices.
    Returns single device object or dict {name: device}.

    Single:  sw = connect_devices(testbed, 'HFCL')
    Multi:   devs = connect_devices(testbed, 'HFCL', 'SW2')
    """
    if len(device_names) == 1:
        dev = testbed.devices[device_names[0]]
        dev.connect(log_stdout=False)
        log.info(f"Connected: {device_names[0]}")
        return dev
    else:
        result = {}
        for name in device_names:
            dev = testbed.devices[name]
            dev.connect(log_stdout=False)
            log.info(f"Connected: {name}")
            result[name] = dev
        return result


def disconnect_all(testbed):
    """Disconnect all devices in testbed."""
    for name, dev in testbed.devices.items():
        try:
            if dev.is_connected():
                dev.disconnect()
                log.info(f"Disconnected: {name}")
        except Exception as e:
            log.warning(f"Error disconnecting {name}: {e}")


def send_cmd(device, command: str, timeout: int = 60) -> str:
    """
    Send a show/exec command, return output string.
    Uses pyATS device.execute() which handles prompt matching.
    """
    try:
        output = device.execute(command, timeout=timeout)
        log.info(f"[{device.name}] >> {command}")
        log.info(output)
        return output
    except Exception as e:
        log.error(f"[{device.name}] Command failed: '{command}' — {e}")
        raise


def send_config(device, config_lines: list, timeout: int = 60):
    """
    Push config lines. Accepts a list.
    send_config(sw, ['vlan 10', 'name TEST', 'exit'])
    """
    try:
        device.configure(config_lines, timeout=timeout)
        log.info(f"[{device.name}] Config: {config_lines}")
    except Exception as e:
        log.error(f"[{device.name}] Config failed: {e}")
        raise


# =============================================================================
# ASSERTION HELPERS  (same logic as your verify_output_contains)
# =============================================================================

def verify_output_contains(output: str, expected: str) -> bool:
    """Direct port of your original helper. Case-sensitive."""
    return expected in output


def assert_output(output: str, expected: str, message: str = ""):
    """Raise AssertionError if expected not in output."""
    if expected not in output:
        raise AssertionError(
            f"{message}\nExpected : '{expected}'\nNot found in:\n{output}"
        )


def assert_not_in_output(output: str, unexpected: str, message: str = ""):
    """Raise AssertionError if unexpected IS in output."""
    if unexpected in output:
        raise AssertionError(
            f"{message}\nUnexpected string found: '{unexpected}'\nIn:\n{output}"
        )


def assert_regex(output: str, pattern: str, message: str = ""):
    """Raise AssertionError if regex pattern not matched."""
    if not re.search(pattern, output, re.IGNORECASE):
        raise AssertionError(
            f"{message}\nPattern '{pattern}' not found in:\n{output}"
        )


# =============================================================================
# PORT HELPERS
# =============================================================================

def port_up(device, interface: str, wait: bool = True):
    send_config(device, [f'interface {interface}', 'no shutdown', 'exit'])
    if wait:
        time.sleep(timer('port_up_wait'))
    log.info(f"[{device.name}] Port UP: {interface}")


def port_down(device, interface: str):
    send_config(device, [f'interface {interface}', 'shutdown', 'exit'])
    log.info(f"[{device.name}] Port DOWN: {interface}")


def set_port_vlan(device, interface: str, vlan_id: int, mode: str = 'access'):
    if mode == 'access':
        send_config(device, [
            f'interface {interface}',
            'switchport mode access',
            f'switchport access vlan {vlan_id}',
            'exit'
        ])
    elif mode == 'trunk':
        send_config(device, [
            f'interface {interface}',
            'switchport mode trunk',
            f'switchport trunk allowed vlan {vlan_id}',
            'exit'
        ])
    log.info(f"[{device.name}] {interface} → {mode} VLAN {vlan_id}")


# =============================================================================
# VLAN HELPERS
# =============================================================================

def create_vlan(device, vlan_id: int, name: str = ""):
    cmds = [f'vlan {vlan_id}']
    if name:
        cmds.append(f'name {name}')
    cmds.append('exit')
    send_config(device, cmds)
    log.info(f"[{device.name}] Created VLAN {vlan_id}")


def delete_vlan(device, vlan_id: int):
    send_config(device, [f'no vlan {vlan_id}'])
    log.info(f"[{device.name}] Deleted VLAN {vlan_id}")


def verify_vlan_exists(device, vlan_id: int) -> bool:
    output = send_cmd(device, 'show vlan brief')
    return str(vlan_id) in output


# =============================================================================
# MAC HELPERS
# =============================================================================

def get_mac_table(device, vlan_id: int = None) -> str:
    if vlan_id:
        return send_cmd(device, f'show mac address-table vlan {vlan_id}')
    return send_cmd(device, 'show mac address-table')


def clear_mac_table(device):
    send_cmd(device, 'clear mac address-table dynamic')
    log.info(f"[{device.name}] MAC table cleared")


# =============================================================================
# WAIT / CONVERGENCE
# =============================================================================

def wait(seconds: int, reason: str = ""):
    log.info(f"Waiting {seconds}s — {reason}")
    time.sleep(seconds)


def wait_for_convergence(label: str = ""):
    secs = timer('convergence_wait')
    log.info(f"Waiting {secs}s for convergence — {label}")
    time.sleep(secs)


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup_device(device, vlans_to_delete: list = None,
                   interfaces_to_reset: list = None):
    if vlans_to_delete:
        for v in vlans_to_delete:
            try:
                delete_vlan(device, v)
            except Exception:
                pass
    if interfaces_to_reset:
        for iface in interfaces_to_reset:
            try:
                send_config(device, [f'default interface {iface}'])
            except Exception:
                pass
    log.info(f"[{device.name}] Cleanup done")


# =============================================================================
# BANNER — from your original log_banner()
# =============================================================================

def log_banner(message: str):
    log.info("")
    log.info("=" * 70)
    log.info(message)
    log.info("=" * 70)


# =============================================================================
# SHOW SHORTCUTS
# =============================================================================

def show_interfaces_status(device) -> str:
    return send_cmd(device, 'show interface status')


def show_stp(device, vlan_id: int = None) -> str:
    if vlan_id:
        return send_cmd(device, f'show spanning-tree vlan {vlan_id}')
    return send_cmd(device, 'show spanning-tree')


def show_lacp(device) -> str:
    return send_cmd(device, 'show lacp neighbor')


def show_erps(device, ring_id: int = 1) -> str:
    return send_cmd(device, f'show erps ring {ring_id}')
