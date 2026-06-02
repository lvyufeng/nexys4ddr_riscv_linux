#!/usr/bin/env python3
import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("Missing pyserial. Install with: .venv/bin/python3 -m pip install pyserial", file=sys.stderr)
    sys.exit(2)

parser = argparse.ArgumentParser(description="Smoke-test the LiteX BIOS UART console.")
parser.add_argument("port", nargs="?", default="/dev/ttyUSB1")
parser.add_argument("--baud", type=int, default=115200)
parser.add_argument("--timeout", type=float, default=8.0)
args = parser.parse_args()

with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
    ser.reset_input_buffer()
    ser.write(b"\r")
    deadline = time.time() + args.timeout
    data = bytearray()
    while time.time() < deadline:
        chunk = ser.read(4096)
        if chunk:
            data.extend(chunk)
            text = data.decode(errors="replace")
            if "LiteX" in text or "BIOS" in text or "litex" in text.lower():
                print(text, end="" if text.endswith("\n") else "\n")
                print("LITEX_UART_SMOKE_OK")
                sys.exit(0)
        else:
            ser.write(b"\r")
            time.sleep(0.2)

text = data.decode(errors="replace")
if text:
    print(text, end="" if text.endswith("\n") else "\n")
print("LITEX_UART_SMOKE_TIMEOUT", file=sys.stderr)
sys.exit(1)
