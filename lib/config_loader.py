"""
config_loader.py
================
Single import that gives every test script access to lab_config.yaml.
Nothing is hardcoded in test scripts — all values come from here.

Usage:
    from lib.config_loader import dev, intf, vlan, timer, traffic_cfg

    host        = dev('HFCL', 'host')           # '192.168.89.61'
    port1       = intf('HFCL', 'access_port_1') # 'Gigabitethernet 1/1'
    vlan_id     = vlan('test_vlan_1')            # 1
    wait        = timer('convergence_wait')       # 30
    sender_ip   = traffic_cfg('sender', 'host')  # '192.168.89.62'
"""

import os
import yaml

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config', 'lab_config.yaml'
)

def _load():
    with open(_CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

# Full raw config — use when you need a whole sub-section
cfg = _load()


def dev(device_name: str, key: str = None):
    """dev('HFCL', 'host') → '192.168.89.61'"""
    d = cfg['devices'][device_name]
    return d if key is None else d[key]


def intf(device_name: str, port_alias: str) -> str:
    """intf('HFCL', 'access_port_1') → 'Gigabitethernet 1/1'"""
    return cfg['interfaces'][device_name][port_alias]


def vlan(vlan_alias: str) -> int:
    """vlan('test_vlan_1') → 1"""
    return cfg['vlans'][vlan_alias]


def timer(timer_name: str) -> int:
    """timer('convergence_wait') → 30"""
    return cfg['timers'][timer_name]


def traffic_cfg(side: str = None, key: str = None):
    """
    traffic_cfg()                   → full traffic dict
    traffic_cfg('sender')           → sender dict
    traffic_cfg('sender', 'host')   → '192.168.89.62'
    traffic_cfg('packet_count')     → 1000
    """
    t = cfg['traffic']
    if side is None:
        return t
    if key is None:
        return t[side]
    # Allow top-level keys like 'packet_count' directly
    if side in t and isinstance(t[side], dict):
        return t[side][key]
    return t[side]


def report_path(key: str) -> str:
    """report_path('sender_json') → '/tmp/sender_report.json'"""
    return cfg['reports'][key]


def all_devices() -> list:
    return list(cfg['devices'].keys())


def get_stp_config() -> dict:
    return cfg.get('stp', {})


def get_lag_config() -> dict:
    return cfg.get('lag', {})


def get_erps_config() -> dict:
    return cfg.get('erps', {})


def get_oam_config() -> dict:
    return cfg.get('oam', {})


def get_vlan_range() -> tuple:
    """Returns (start_vlan, count) for scalability tests."""
    v = cfg['vlans']
    return v['scale_start_vlan'], v['scale_count']


if __name__ == '__main__':
    print("=== Config Loader Sanity Check ===")
    print(f"Switch IP       : {dev('HFCL', 'host')}")
    print(f"access_port_1   : {intf('HFCL', 'access_port_1')}")
    print(f"access_port_2   : {intf('HFCL', 'access_port_2')}")
    print(f"test_vlan_1     : {vlan('test_vlan_1')}")
    print(f"conv. wait      : {timer('convergence_wait')}s")
    print(f"sender host     : {traffic_cfg('sender', 'host')}")
    print(f"packet count    : {traffic_cfg('packet_count')}")
    print(f"sender_json     : {report_path('sender_json')}")
    print("All OK!")
