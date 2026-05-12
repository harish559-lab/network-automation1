#!/usr/bin/env python3
"""
MAC_generate_traffic.py
-----------------------
Generates bi-directional Layer-2 traffic using Scapy so the HFCL switch
learns two dynamic MAC entries (one per direction) in its MAC address table.

Usage:
    sudo python3 MAC_generate_traffic.py --interface enp2s0
"""

import argparse
import time
from scapy.all import Ether, IP, UDP, sendp, conf

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Bi-directional traffic generator (Scapy)")
parser.add_argument("--interface", required=True, help="Network interface to send traffic on (e.g. enp2s0)")
parser.add_argument("--count",     type=int,   default=20,  help="Number of packets per direction (default: 20)")
parser.add_argument("--interval",  type=float, default=0.1, help="Interval between packets in seconds (default: 0.1)")
args = parser.parse_args()

IFACE    = args.interface
COUNT    = args.count
INTERVAL = args.interval

# ---------------------------------------------------------------------------
# Spoofed MAC/IP addresses
# These will appear as Dynamic entries in the HFCL MAC table:
#   Dynamic  1  00:11:22:33:44:aa  <port>
#   Dynamic  1  00:11:22:33:44:bb  <port>
# ---------------------------------------------------------------------------
SRC_MAC = "00:11:22:33:44:AA"
DST_MAC = "00:11:22:33:44:BB"
SRC_IP  = "10.0.0.1"
DST_IP  = "10.0.0.2"

conf.verb = 0   # suppress Scapy output

print(f"{'='*60}")
print(f"  HFCL Switch — Bi-directional Traffic Generator")
print(f"  Interface : {IFACE}")
print(f"  SRC MAC   : {SRC_MAC}  →  DST MAC: {DST_MAC}")
print(f"  Packets   : {COUNT} per direction")
print(f"{'='*60}")

# ---------------------------------------------------------------------------
# Direction 1 : SRC → DST
# Switch learns SRC_MAC (00:11:22:33:44:AA) on the ingress port
# ---------------------------------------------------------------------------
print(f"\n[*] Direction 1: {SRC_MAC} → {DST_MAC}")
pkt_fwd = (
    Ether(src=SRC_MAC, dst=DST_MAC) /
    IP(src=SRC_IP, dst=DST_IP) /
    UDP(sport=5000, dport=5001)
)
sendp(pkt_fwd, iface=IFACE, count=COUNT, inter=INTERVAL)
print(f"[✓] Forward direction complete — {COUNT} packets sent")

time.sleep(1)

# ---------------------------------------------------------------------------
# Direction 2 : DST → SRC
# Switch learns DST_MAC (00:11:22:33:44:BB) on the return port
# ---------------------------------------------------------------------------
print(f"\n[*] Direction 2: {DST_MAC} → {SRC_MAC}")
pkt_rev = (
    Ether(src=DST_MAC, dst=SRC_MAC) /
    IP(src=DST_IP, dst=SRC_IP) /
    UDP(sport=5001, dport=5000)
)
sendp(pkt_rev, iface=IFACE, count=COUNT, inter=INTERVAL)
print(f"[✓] Reverse direction complete — {COUNT} packets sent")

print(f"\n{'='*60}")
print(f"[✅] Bi-directional traffic generation complete.")
print(f"     SRC MAC: {SRC_MAC}")
print(f"     DST MAC: {DST_MAC}")
print(f"     Both MACs should now appear as 'Dynamic' entries")
print(f"     in the HFCL switch MAC address table.")
print(f"{'='*60}")
