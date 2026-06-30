#!/usr/bin/env python3

"""
=============================================================
Script : traffic_sender.py

Purpose:
    Generate untagged Ethernet traffic for Layer-2 testing.

Author : Harish
=============================================================
"""

import argparse
import json
import os
import sys
import time

from scapy.all import Ether, Raw, sendp, get_if_hwaddr


def main():

    parser = argparse.ArgumentParser(
        description="Generate Untagged Ethernet Traffic"
    )

    parser.add_argument(
        "--interface",
        required=True,
        help="Linux Interface"
    )

    parser.add_argument(
        "--dst-mac",
        default="ff:ff:ff:ff:ff:ff",
        help="Destination MAC Address"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of packets"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.01,
        help="Delay between packets"
    )

    parser.add_argument(
        "--payload-size",
        type=int,
        default=100,
        help="Payload Size"
    )

    parser.add_argument(
        "--report",
        default="/tmp/sender_report.json",
        help="JSON report path"
    )

    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.report), exist_ok=True)

    src_mac = get_if_hwaddr(args.interface)

    payload = "A" * args.payload_size

    frame = Ether(
        src=src_mac,
        dst=args.dst_mac
    ) / Raw(load=payload)

    print("=" * 60)
    print("Traffic Sender Started")
    print("=" * 60)
    print(f"Interface      : {args.interface}")
    print(f"Source MAC     : {src_mac}")
    print(f"Destination MAC: {args.dst_mac}")
    print(f"Packets        : {args.count}")
    print("=" * 60)

    start = time.time()

    try:

        sendp(
            frame,
            iface=args.interface,
            count=args.count,
            inter=args.interval,
            verbose=False
        )

        duration = round(time.time() - start, 2)

        report = {

            "status": "PASS",

            "interface": args.interface,

            "source_mac": src_mac,

            "destination_mac": args.dst_mac,

            "packets_sent": args.count,

            "payload_size": args.payload_size,

            "duration": duration

        }

        with open(args.report, "w") as fp:
            json.dump(report, fp, indent=4)

        print(json.dumps(report, indent=4))

        print("\nTraffic Generation Completed")

        sys.exit(0)

    except Exception as e:

        print(f"ERROR : {e}")

        sys.exit(1)


if __name__ == "__main__":
    main()
