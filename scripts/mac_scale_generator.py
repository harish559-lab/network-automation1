from scapy.all import Ether, ARP, sendp
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--iface", required=True)

parser.add_argument("--count", type=int, required=True)

args = parser.parse_args()

iface = args.iface
count = args.count

print(f"Generating {count} MAC addresses")

for i in range(count):

    mac = (
        f"02:00:"
        f"{(i >> 16) & 0xff:02x}:"
        f"{(i >> 8) & 0xff:02x}:"
        f"{i & 0xff:02x}:"
        f"{(i % 255):02x}"
    )

    pkt = Ether(src=mac, dst="ff:ff:ff:ff:ff:ff") / ARP(pdst="192.168.1.1")

    sendp(pkt, iface=iface, verbose=False)

print("Traffic generation completed")
