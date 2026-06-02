#!/usr/bin/env python3
"""
MAC_movement_traffic.py
-----------------------
Sends traffic from a specified interface with a specified source MAC.
Used to simulate MAC movement between ports on HFCL switch.

Usage:
    sudo python3 MAC_movement_traffic.py --interface enp2s0 --src-mac 00:11:22:33:44:55
    sudo python3 MAC_movement_traffic.py --interface enp44s0 --src-mac 00:11:22:33:44:55
"""

import argparse
from scapy.all import sendp, Ether, IP, UDP

parser = argparse.ArgumentParser()
parser.add_argument("--interface", required=True, help="Network interface to send from")
parser.add_argument("--src-mac",  required=True, help="Source MAC address")
parser.add_argument("--dst-mac",  default="ff:ff:ff:ff:ff:ff", help="Destination MAC")
parser.add_argument("--count",    type=int, default=20, help="Number of packets")
args = parser.parse_args()

IFACE    = args.interface
SRC_MAC  = args.src_mac
DST_MAC  = args.dst_mac
COUNT    = args.count
INTERVAL = 0.1

print("=" * 60)
print(f"  HFCL Switch — MAC Movement Traffic Generator")
print(f"  Interface : {IFACE}")
print(f"  SRC MAC   : {SRC_MAC}  →  DST MAC: {DST_MAC}")
print(f"  Packets   : {COUNT}")
print("=" * 60)

pkt = Ether(src=SRC_MAC, dst=DST_MAC) / IP(src="10.0.0.1", dst="10.0.0.2") / UDP()

print(f"\n[*] Sending {COUNT} packets from {IFACE} with src MAC {SRC_MAC}")
sendp(pkt, iface=IFACE, count=COUNT, inter=INTERVAL, verbose=False)
print(f"[✓] Complete — {COUNT} packets sent")
print("=" * 60)
print(f"[✅] Traffic generation complete.")
print(f"     SRC MAC: {SRC_MAC}")
print(f"     Interface: {IFACE}")
print(f"     MAC should now appear as 'Dynamic' entry in switch MAC table.")
print("=" * 60)
