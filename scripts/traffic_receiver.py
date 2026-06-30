#!/usr/bin/env python3

"""
===========================================================
Script : traffic_receiver.py

Purpose:
    Receive untagged Ethernet traffic for Layer-2 validation.

Author : Harish
===========================================================
"""

import argparse
import json
import os
import sys
import time

from scapy.all import sniff


packet_count = 0
source_macs = set()
destination_macs = set()


def process_packet(pkt):

    global packet_count

    packet_count += 1

    if pkt.haslayer("Ether"):

        source_macs.add(pkt.src)

        destination_macs.add(pkt.dst)


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--interface",
        required=True,
        help="Linux Interface"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Sniff duration (seconds)"
    )

    parser.add_argument(
        "--report",
        default="/tmp/receiver_report.json",
        help="JSON report path"
    )

    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.report), exist_ok=True)

    print("=" * 60)
    print("Traffic Receiver Started")
    print("=" * 60)
    print(f"Interface : {args.interface}")
    print(f"Timeout   : {args.timeout} seconds")
    print("=" * 60)

    start = time.time()

    try:

        sniff(
            iface=args.interface,
            prn=process_packet,
            store=False,
            timeout=args.timeout
        )

        duration = round(time.time() - start, 2)

        report = {

            "status": "PASS",

            "interface": args.interface,

            "packets_received": packet_count,

            "duration": duration,

            "source_macs": sorted(list(source_macs)),

            "destination_macs": sorted(list(destination_macs))

        }

        with open(args.report, "w") as fp:

            json.dump(report, fp, indent=4)

        print(json.dumps(report, indent=4))

        print("\nReceiver Completed")

        sys.exit(0)

    except Exception as e:

        print(f"ERROR : {e}")

        sys.exit(1)


if __name__ == "__main__":
    main()
