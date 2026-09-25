"""
testbed_generator.py
====================
Auto-generates pyATS testbed YAML files from lab_config.yaml.
Applies HFCL-specific unicon settings (os: linux, ssh_options, timeouts)
exactly as in your original testbed.yaml.

Run:
    python lib/testbed_generator.py           # all topologies
    python lib/testbed_generator.py --topology single

Outputs:
    testbeds/testbed_single.yaml   → 1 switch (MAC, VLAN, port tests)
    testbeds/testbed_dual.yaml     → 2 switches (RSTP, LACP, OAM)
    testbeds/testbed_ring.yaml     → 3 switches (ERPS, MSTP)
"""

import os
import sys
import yaml
import argparse

# Allow running directly: python lib/testbed_generator.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.config_loader import cfg

TESTBED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'testbeds'
)

# Alias → device name mapping per topology
TOPOLOGY_ALIASES = {
    'single': ['switch'],
    'dual':   ['switch', 'peer1'],
    'ring':   ['switch', 'peer1', 'peer2'],
}


def _build_testbed_dict(device_names: list) -> dict:
    """Build pyATS-compatible testbed dict for given device names."""
    testbed = {
        'testbed': {'name': 'HFCL_Switch_Testbed'},
        'devices': {}
    }

    for name in device_names:
        d = cfg['devices'][name]
        testbed['devices'][name] = {
            'alias':    d.get('alias', name.lower()),
            'type':     'switch',
            'os':       d.get('os', 'linux'),       # 'linux' not 'generic'
            'platform': d.get('platform', 'linux'),
            'credentials': {
                'default': {
                    'username': d['username'],
                    'password': d['password'],
                }
            },
            'connections': {
                'cli': {
                    'class':    'unicon.Unicon',
                    'protocol': d.get('protocol', 'ssh'),
                    'ip':       d['host'],
                    'port':     d.get('port', 22),
                    'arguments': {
                        'connection_timeout': d.get('connection_timeout', 60),
                        'ssh_options': d.get(
                            'ssh_options',
                            '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                        ),
                    },
                    'settings': {
                        'EXEC_TIMEOUT':               d.get('exec_timeout', 60),
                        'GRACEFUL_DISCONNECT_WAIT_SEC': 2,
                    }
                }
            }
        }

    return testbed


def generate(topology: str = None) -> list:
    os.makedirs(TESTBED_DIR, exist_ok=True)

    # Build alias → device name map
    alias_map = {
        info.get('alias', name): name
        for name, info in cfg['devices'].items()
    }

    topologies = (
        {topology: TOPOLOGY_ALIASES[topology]}
        if topology
        else TOPOLOGY_ALIASES
    )

    generated = []
    for topo_name, aliases in topologies.items():
        device_names = []
        missing = []
        for alias in aliases:
            if alias in alias_map:
                device_names.append(alias_map[alias])
            else:
                missing.append(alias)

        if not device_names:
            print(f"  [SKIP] '{topo_name}' — no devices found in config")
            continue

        out_path = os.path.join(TESTBED_DIR, f'testbed_{topo_name}.yaml')
        with open(out_path, 'w') as f:
            yaml.dump(
                _build_testbed_dict(device_names),
                f,
                default_flow_style=False,
                sort_keys=False
            )
        generated.append(out_path)

        # Only show missing note for multi-switch topologies
        if missing:
            note = f"  (add {', '.join(missing)} to lab_config.yaml when ready)"
        else:
            note = ""
        print(f"  [OK] {out_path}  ({', '.join(device_names)}){note}")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description='Generate pyATS testbed YAMLs from lab_config.yaml'
    )
    parser.add_argument(
        '--topology',
        choices=['single', 'dual', 'ring'],
        default=None,
        help='Topology to generate (default: all)'
    )
    args = parser.parse_args()
    print("Generating testbeds from config/lab_config.yaml ...")
    files = generate(args.topology)
    print(f"Done — {len(files)} file(s) in: {TESTBED_DIR}/")


if __name__ == '__main__':
    main()
