#!/usr/bin/env python3
"""
Send one fixed frame to the DH360D LCD and hold it, so you can compare what
you asked for against what the panel actually shows.

Stop the daemon first, or the two will fight over the port:

    sudo systemctl stop dh360d
    sudo python3 tools/probe.py --temp 45 --cpu 72 --rpm 1800 --ram 63
    sudo systemctl start dh360d

--raw skips the XOR 2 compensation, which is how you confirm the encoding on
an unknown panel: the displayed numbers should come back with bit 1 flipped.
"""
import argparse
import os
import struct
import sys
import time

import serial

DEFAULT_PORTS = ("/dev/darkflash_lcd", "/dev/ttyACM0")


def build_frame(temp, cpu, rpm, ram, xor=2):
    return (bytes([0x74, 0x03, (temp ^ xor) & 0xFF, (cpu ^ xor) & 0xFF])
            + struct.pack(">H", (rpm ^ xor) & 0xFFFF)
            + bytes([(ram ^ xor) & 0xFF]))


def pick_port(explicit):
    if explicit:
        return explicit
    for p in DEFAULT_PORTS:
        if os.path.exists(p):
            return p
    sys.exit("no LCD serial port found (looked for %s)" % ", ".join(DEFAULT_PORTS))


def main():
    ap = argparse.ArgumentParser(description="DH360D LCD frame probe")
    ap.add_argument("--temp", type=int, default=45, help="temperature in C")
    ap.add_argument("--cpu", type=int, default=72, help="CPU load %%")
    ap.add_argument("--rpm", type=int, default=1800, help="fan/pump RPM")
    ap.add_argument("--ram", type=int, default=63, help="RAM use %%")
    ap.add_argument("--seconds", type=int, default=20, help="how long to hold")
    ap.add_argument("--port", help="serial port (default: autodetect)")
    ap.add_argument("--raw", action="store_true",
                    help="send values without the XOR 2 compensation")
    args = ap.parse_args()

    xor = 0 if args.raw else 2
    port = pick_port(args.port)
    pkt = build_frame(args.temp, args.cpu, args.rpm, args.ram, xor)

    print(f"port  : {port}")
    print(f"frame : {pkt.hex(' ')}")
    if args.raw:
        print("mode  : RAW (no XOR) - expect each number to show with bit 1 flipped")
    print(f"expect: temp {args.temp} / cpu {args.cpu} / fan {args.rpm} / ram {args.ram}")
    print(f"holding for {args.seconds}s\n")

    try:
        with serial.Serial(port, 115200, timeout=0.5) as s:
            time.sleep(0.5)
            s.reset_output_buffer()
            for i in range(args.seconds):
                s.write(pkt)
                s.flush()
                if (i + 1) % 5 == 0:
                    print(f"  {i + 1}/{args.seconds}s", flush=True)
                time.sleep(1.0)
    except serial.SerialException as e:
        sys.exit(f"serial error: {e}\n(is dh360d.service still running?)")

    print("\ndone - compare the panel against the expected values above.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
