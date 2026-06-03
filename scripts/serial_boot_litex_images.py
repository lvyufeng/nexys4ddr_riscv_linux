#!/usr/bin/env python3
"""Serial-load LiteX images without requiring an interactive TTY.

This is a small non-interactive LiteX SFL (serial flash loader) client for CI or
remote SSH sessions where litex_term's Console/termios handling is inconvenient.
It supports the image JSON format used by litex_term:

{
  "Image": "0x40000000",
  "rv32.dtb": "0x40ef0000",
  "rootfs.cpio.gz": "0x41000000",
  "opensbi.bin": "0x40f00000"
}

The last JSON entry is used as the jump address, matching litex_term behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import serial
from serial import SerialException

SFL_PROMPT_REQ = b"F7:    boot from serial\n"
SFL_PROMPT_ACK = b"\x06"
SFL_MAGIC_REQ = b"sL5DdSMmkekro\n"
SFL_MAGIC_ACK = b"z6IHG7cYDID6o\n"

SFL_CMD_ABORT = b"\x00"
SFL_CMD_LOAD = b"\x01"
SFL_CMD_JUMP = b"\x02"

SFL_ACK_SUCCESS = b"K"
SFL_ACK_CRCERROR = b"C"
SFL_ACK_UNKNOWN = b"U"
SFL_ACK_ERROR = b"E"

CRC16_TABLE = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
]


def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = CRC16_TABLE[((crc >> 8) ^ byte) & 0xFF] ^ ((crc << 8) & 0xFFFF_FFFF)
    return crc & 0xFFFF


def encode_frame(cmd: bytes, payload: bytes) -> bytes:
    if len(cmd) != 1:
        raise ValueError("SFL command must be one byte")
    if len(payload) > 255:
        raise ValueError("SFL payload too large")
    body = cmd + payload
    return bytes([len(payload)]) + crc16(body).to_bytes(2, "big") + body


def printable(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


class SerialBooter:
    def __init__(self, port: str, speed: int, log_path: str | None = None):
        self.ser = serial.Serial(port, speed, timeout=0.05, write_timeout=2.0)
        self.log = open(log_path, "ab", buffering=0) if log_path else None
        self.recent = bytearray()
        self.serial_failed = False

    def close(self) -> None:
        if self.log:
            self.log.close()
        self.ser.close()

    def _record(self, data: bytes, echo: bool = True) -> None:
        if not data:
            return
        if self.log:
            self.log.write(data)
        if echo:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        self.recent.extend(data)
        if len(self.recent) > 4096:
            del self.recent[:-4096]

    def read_some(self, echo: bool = True) -> bytes:
        try:
            data = self.ser.read(4096)
        except SerialException as e:
            self.serial_failed = True
            print(f"\n[SFL] Serial read failed: {e}", flush=True)
            return b""
        self._record(data, echo=echo)
        return data

    def wait_for_serial_loader(self, timeout: float) -> None:
        print("[SFL] Waiting for LiteX serial loader...", flush=True)
        deadline = time.monotonic() + timeout
        prompted = False
        command_sent = False
        last_probe = 0.0

        # Kick the BIOS once. If it is already at litex>, this reveals the prompt.
        self.ser.write(b"\r")
        self.ser.flush()

        while time.monotonic() < deadline:
            self.read_some(echo=True)

            if SFL_PROMPT_REQ in self.recent and not prompted:
                print("\n[SFL] BIOS serial-boot menu detected; sending ACK.", flush=True)
                self.ser.write(SFL_PROMPT_ACK)
                self.ser.flush()
                prompted = True

            if SFL_MAGIC_REQ in self.recent:
                print("\n[SFL] Firmware download request detected; sending magic ACK.", flush=True)
                self.ser.write(SFL_MAGIC_ACK)
                self.ser.flush()
                time.sleep(0.1)
                self.drain()
                return

            now = time.monotonic()
            recent_lower = bytes(self.recent).lower()
            if (not command_sent) and (b"litex" in recent_lower and b">" in recent_lower):
                print("\n[SFL] LiteX prompt detected; issuing serialboot command.", flush=True)
                self.ser.write(b"serialboot\r")
                self.ser.flush()
                command_sent = True

            if not command_sent and not prompted and now - last_probe > 2.0:
                # If we missed the boot menu and are sitting at a prompt, this will work.
                self.ser.write(b"\r")
                self.ser.flush()
                last_probe = now

        raise TimeoutError("Timed out waiting for LiteX serial loader magic")

    def drain(self) -> None:
        end = time.monotonic() + 0.2
        while time.monotonic() < end:
            data = self.ser.read(4096)
            if data:
                self._record(data, echo=True)
                end = time.monotonic() + 0.05

    def read_ack(self, timeout: float = 2.0) -> bytes:
        old_timeout = self.ser.timeout
        changed_timeout = old_timeout != timeout
        if changed_timeout:
            self.ser.timeout = timeout
        try:
            reply = self.ser.read(1)
        finally:
            if changed_timeout:
                self.ser.timeout = old_timeout
        if not reply:
            raise TimeoutError("Timed out waiting for SFL ACK")
        return reply

    def send_frame(self, cmd: bytes, payload: bytes, retries: int = 16) -> None:
        self.send_encoded_frames([encode_frame(cmd, payload)], retries=retries)

    def send_encoded_frames(self, frames: list[bytes], retries: int = 16) -> None:
        """Send one or more SFL frames and collect their ACKs.

        LiteX SFL acknowledges every frame. Waiting for each ACK before sending
        the next frame makes the host pay the USB-UART latency timer once per
        251-byte chunk. Sending a small window first and then draining the ACKs
        keeps the UART busy while preserving the protocol's per-frame checks.
        """
        if not frames:
            return

        pending = list(enumerate(frames))
        last_replies: list[bytes] = []
        for attempt in range(retries):
            for _, frame in pending:
                self.ser.write(frame)
            self.ser.flush()

            retry: list[tuple[int, bytes]] = []
            last_replies = []
            for idx, frame in pending:
                reply = self.read_ack()
                last_replies.append(reply)
                if reply == SFL_ACK_SUCCESS:
                    continue
                if reply == SFL_ACK_CRCERROR:
                    retry.append((idx, frame))
                    continue
                raise RuntimeError(f"Unexpected SFL reply {reply!r}")

            if not retry:
                return
            print(f"[SFL] CRC retry: {len(retry)} frame(s), attempt {attempt + 1}/{retries}", flush=True)
            pending = retry

        raise RuntimeError(f"Too many CRC errors; last replies={last_replies!r}")

    def upload_file(self, path: Path, address: int, chunk_size: int, ack_window: int) -> None:
        size = path.stat().st_size
        print(f"[SFL] Uploading {path} to 0x{address:08x} ({size} bytes, ack-window={ack_window})...", flush=True)
        start = time.monotonic()
        sent = 0
        last_report = start

        def report(force: bool = False) -> None:
            nonlocal last_report
            now = time.monotonic()
            if force or now - last_report >= 1.0 or sent == size:
                pct = 100.0 * sent / size if size else 100.0
                rate = sent / max(now - start, 1e-6) / 1024.0
                print(f"[SFL]   {path.name}: {sent}/{size} bytes ({pct:5.1f}%, {rate:5.1f} KiB/s)", flush=True)
                last_report = now

        old_timeout = self.ser.timeout
        self.ser.timeout = 2.0
        try:
            with path.open("rb") as f:
                current = address
                pending: list[bytes] = []
                pending_bytes = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    pending.append(encode_frame(SFL_CMD_LOAD, current.to_bytes(4, "big") + chunk))
                    current += len(chunk)
                    pending_bytes += len(chunk)
                    if len(pending) >= ack_window:
                        self.send_encoded_frames(pending)
                        sent += pending_bytes
                        pending = []
                        pending_bytes = 0
                        report()

                if pending:
                    self.send_encoded_frames(pending)
                    sent += pending_bytes
                    report(force=True)
        finally:
            self.ser.timeout = old_timeout
        elapsed = time.monotonic() - start
        print(f"[SFL] Upload complete: {path.name} ({size / max(elapsed, 1e-6) / 1024.0:.1f} KiB/s).", flush=True)

    def jump(self, address: int) -> None:
        print(f"[SFL] Jumping to 0x{address:08x}...", flush=True)
        self.send_frame(SFL_CMD_JUMP, address.to_bytes(4, "big"))

    def console_until(self, marker: bytes | None, timeout: float) -> bool:
        print("[SFL] Console capture started.", flush=True)
        deadline = time.monotonic() + timeout
        seen = bytearray()
        while time.monotonic() < deadline:
            data = self.read_some(echo=True)
            if self.serial_failed:
                print("\n[SFL] Console capture stopped after serial read failure.", flush=True)
                return False
            if data:
                seen.extend(data)
                if len(seen) > max(4096, len(marker or b"")):
                    del seen[:-max(4096, len(marker or b""))]
                if marker and marker in seen:
                    print("\n[SFL] Exit marker detected.", flush=True)
                    return True
            else:
                time.sleep(0.02)
        print("\n[SFL] Console capture timeout.", flush=True)
        return False


def load_images(images_path: Path) -> tuple[list[tuple[Path, int]], int]:
    with images_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    base_dir = images_path.parent
    images: list[tuple[Path, int]] = []
    for name, addr in raw.items():
        path = base_dir / name
        images.append((path, int(str(addr), 0)))
    if not images:
        raise ValueError("image JSON is empty")
    for path, _ in images:
        if not path.exists():
            raise FileNotFoundError(path)
    return images, images[-1][1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyUSB1")
    parser.add_argument("--speed", type=int, default=1000000)
    parser.add_argument("--images", required=True)
    parser.add_argument("--chunk-size", type=int, default=251, help="SFL data bytes per load frame, max 251")
    parser.add_argument("--ack-window", type=int, default=8, help="number of SFL load frames to send before draining ACKs")
    parser.add_argument("--safe", action="store_true", help="use one-frame ACK windows for maximum compatibility")
    parser.add_argument("--loader-timeout", type=float, default=30.0)
    parser.add_argument("--console-timeout", type=float, default=300.0)
    parser.add_argument("--exit-on", default="buildroot login:")
    parser.add_argument("--log", default=None)
    args = parser.parse_args()

    if not (1 <= args.chunk_size <= 251):
        parser.error("--chunk-size must be in [1, 251]")
    if args.safe:
        args.ack_window = 1
    if args.ack_window < 1:
        parser.error("--ack-window must be >= 1")

    images, jump_address = load_images(Path(args.images))
    print("[SFL] Images:", flush=True)
    for path, address in images:
        print(f"[SFL]   {path} -> 0x{address:08x} ({path.stat().st_size} bytes)", flush=True)
    print(f"[SFL] Boot address: 0x{jump_address:08x}", flush=True)

    booter = SerialBooter(args.port, args.speed, args.log)
    try:
        booter.wait_for_serial_loader(args.loader_timeout)
        for path, address in images:
            booter.upload_file(path, address, args.chunk_size, args.ack_window)
        booter.jump(jump_address)
        marker = args.exit_on.encode() if args.exit_on else None
        ok = booter.console_until(marker, args.console_timeout)
        return 0 if ok or marker is None else 1
    finally:
        booter.close()


if __name__ == "__main__":
    raise SystemExit(main())
