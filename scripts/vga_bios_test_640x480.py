#!/usr/bin/env python3
"""Exercise the LiteX VGA framebuffer directly from the LiteX BIOS.

This helper is intentionally host-side and uses only Python's standard library.
It talks to the LiteX BIOS over the USB-UART and programs the 640x480@60Hz
VideoFrameBuffer CSRs, then writes either a white screen or horizontal color bars
into DDR. It is useful before Linux framebuffer-console work because it proves the
Nexys4 DDR VGA pins, pixel clock, VTG, DMA, and framebuffer memory path with a
small, reproducible hardware smoke test.
"""

import argparse
import os
import select
import sys
import termios
import time

DEFAULT_PORTS = [
    "/dev/serial/by-id/usb-Digilent_Digilent_USB_Device_210292709191-if01-port0",
    "/dev/ttyUSB1",
]

FB_BASE = 0x47E00000
FB_WIDTH = 640
FB_HEIGHT = 480
FB_SIZE = FB_WIDTH * FB_HEIGHT * 4

CSR_DMA_BASE = 0xF0007800
CSR_DMA_LENGTH = 0xF0007804
CSR_DMA_ENABLE = 0xF0007808
CSR_DMA_DONE = 0xF000780C
CSR_DMA_LOOP = 0xF0007810
CSR_DMA_OFFSET = 0xF0007814

CSR_VTG_ENABLE = 0xF0008000
CSR_VTG_HRES = 0xF0008004
CSR_VTG_HSYNC_START = 0xF0008008
CSR_VTG_HSYNC_END = 0xF000800C
CSR_VTG_HSCAN = 0xF0008010
CSR_VTG_VRES = 0xF0008014
CSR_VTG_VSYNC_START = 0xF0008018
CSR_VTG_VSYNC_END = 0xF000801C
CSR_VTG_VSCAN = 0xF0008020

# LiteX framebuffer format is a8b8g8r8. These values produce visibly distinct
# bands even if a monitor/adapter labels RGB/BGR differently.
BAR_COLORS = [
    0xFFFFFFFF,
    0xFF0000FF,
    0xFF00FF00,
    0xFFFF0000,
    0xFF00FFFF,
    0xFFFF00FF,
    0xFFFFFF00,
    0xFF000000,
]


def find_port(explicit):
    candidates = [explicit] if explicit else DEFAULT_PORTS
    for _ in range(120):
        for port in candidates:
            if port and os.path.exists(port):
                return port
        time.sleep(0.25)
    raise FileNotFoundError("no LiteX UART found; checked: " + ", ".join(candidates))


def open_uart(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = termios.B1000000
    attrs[5] = termios.B1000000
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def read_for(fd, seconds, echo=True):
    out = bytearray()
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], min(0.1, max(0.0, end - time.time())))
        if fd in r:
            data = os.read(fd, 8192)
            if data:
                out.extend(data)
                if echo:
                    sys.stdout.write(data.decode("utf-8", "replace"))
                    sys.stdout.flush()
    return bytes(out)


def command(fd, text, wait=0.25):
    print(f">>> {text}", flush=True)
    for byte in (text + "\r\n").encode("ascii"):
        os.write(fd, bytes([byte]))
        time.sleep(0.0006)
    return read_for(fd, wait)


def mem_write(fd, addr, value, count=1, size=4, wait=0.2):
    command(fd, f"mem_write 0x{addr:08x} 0x{value:08x} {count} {size}", wait=wait)


def mem_read(fd, addr, length=4, wait=0.3):
    return command(fd, f"mem_read 0x{addr:08x} {length}", wait=wait)


def configure_vga_640x480(fd):
    mem_write(fd, CSR_VTG_ENABLE, 0, wait=0.15)
    mem_write(fd, CSR_DMA_ENABLE, 0, wait=0.15)

    # 640x480@60Hz LiteX timing preset.
    for addr, value in [
        (CSR_VTG_HRES, 640),
        (CSR_VTG_HSYNC_START, 656),
        (CSR_VTG_HSYNC_END, 752),
        (CSR_VTG_HSCAN, 800),
        (CSR_VTG_VRES, 480),
        (CSR_VTG_VSYNC_START, 490),
        (CSR_VTG_VSYNC_END, 492),
        (CSR_VTG_VSCAN, 525),
    ]:
        mem_write(fd, addr, value, wait=0.12)

    mem_write(fd, CSR_DMA_BASE, FB_BASE)
    mem_write(fd, CSR_DMA_LENGTH, FB_SIZE)
    mem_write(fd, CSR_DMA_LOOP, 1)
    mem_write(fd, CSR_DMA_ENABLE, 1)
    mem_write(fd, CSR_VTG_ENABLE, 1)


def fill_white(fd):
    mem_write(fd, FB_BASE, 0xFFFFFFFF, FB_WIDTH * FB_HEIGHT, wait=4.0)


def fill_bars(fd):
    rows_per_bar = FB_HEIGHT // len(BAR_COLORS)
    pixels_per_bar = FB_WIDTH * rows_per_bar
    for index, color in enumerate(BAR_COLORS):
        addr = FB_BASE + index * pixels_per_bar * 4
        mem_write(fd, addr, color, pixels_per_bar, wait=0.75)


def verify(fd):
    print("--- framebuffer readback ---", flush=True)
    mem_read(fd, FB_BASE, 16)
    print("--- DMA offset readback ---", flush=True)
    mem_read(fd, CSR_DMA_OFFSET, 4)
    time.sleep(1.0)
    mem_read(fd, CSR_DMA_OFFSET, 4)
    mem_read(fd, CSR_DMA_DONE, 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="LiteX UART device; defaults to Digilent if01 or /dev/ttyUSB1")
    parser.add_argument("--mode", choices=["white", "bars"], default="bars", help="framebuffer pattern to draw")
    parser.add_argument("--no-config", action="store_true", help="only rewrite framebuffer; leave current VTG/DMA CSR values unchanged")
    args = parser.parse_args()

    port = find_port(args.port)
    print(f"UART {port} -> {os.path.realpath(port)}", flush=True)
    fd = open_uart(port)
    try:
        command(fd, "", wait=0.3)
        if not args.no_config:
            if args.mode == "white":
                fill_white(fd)
                configure_vga_640x480(fd)
            else:
                fill_bars(fd)
                configure_vga_640x480(fd)
        elif args.mode == "white":
            fill_white(fd)
        else:
            fill_bars(fd)
        verify(fd)
    finally:
        os.close(fd)
    print(f"VGA_BIOS_TEST_DONE mode={args.mode}", flush=True)


if __name__ == "__main__":
    main()
