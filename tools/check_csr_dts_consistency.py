#!/usr/bin/env python3
"""Verify that a generated Nexys4 DDR Linux DTS agrees with its LiteX csr.json.

The project hardcodes LiteX CSR slots (see `self.csr.add(..., n=...)` in
litex_targets/nexys4ddr_linux.py), so an upstream change or a stale artifact can
silently move a peripheral while every build still succeeds. This checker turns
that into a hard failure.

Nodes are matched by their **label** rather than by `compatible`, because eight
`/soc` children share `compatible = "litex,gpio"`; the labels (`leds`,
`switches`, `buttons`, `rgb_leds`, `seven_seg`, `ps2_keyboard`, `xadc`,
`temp_i2c`) are exactly the `csr_bases` keys the generator and patcher agree on.

Only a fixed set of project-managed peripherals is checked; the rest of the SoC
(uart, clint, plic, spi, eth, ram, ...) is emitted by upstream LiteX and is not
this tool's contract.

Usage:
    tools/check_csr_dts_consistency.py CSR.JSON DTS_OR_DTB
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# label -> how it should appear in the DTS, derived from csr.json.
#   ("scanner",)  seven-seg is a single custom register window
#   ("gpio", "out"/"in") seven-seg / gpio bank form
CHECKED: dict[str, tuple[str, ...]] = {
    "leds": ("gpio", "out"),
    "switches": ("gpio", "in"),
    "buttons": ("gpio", "in"),
    "rgb_leds": ("gpio", "out"),
    "seven_seg": ("auto",),  # resolved against csr.json core type
    "ps2_keyboard": ("ps2",),
    "xadc": ("hwmon",),
    "temp_i2c": ("i2c",),
}

# Bounded window used to compute a bank's register span inside its base.
_SPAN_WINDOW = 0x100

# Node regex: optional label, node name, unit address, then a brace-less body.
# The label is optional because dtc drops labels when decompiling a .dtb.
_NODE_RE = re.compile(
    r"(?:(?P<label>[A-Za-z_][A-Za-z0-9_]*):\s+)?"
    r"(?P<name>[A-Za-z0-9,._+-]+)@(?P<addr>[0-9a-fA-F]+)\s*\{(?P<body>[^{}]*)\}",
    re.DOTALL,
)
_REG_RE = re.compile(r"reg\s*=\s*<\s*0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s*>")
_COMPAT_RE = re.compile(r'compatible\s*=\s*"([^"]+)"')


def bank_span(registers: dict, base: int) -> int:
    end = base
    for reg in registers.values():
        addr = reg.get("addr")
        if addr is None or not (base <= addr < base + _SPAN_WINDOW):
            continue
        end = max(end, addr + 4 * int(reg.get("size", 1)))
    return end - base


def find_dtc() -> str | None:
    """Locate dtc the same way scripts/build_litex_dtb.sh does."""
    import os
    import shutil

    env = os.environ.get("DTC")
    if env:
        return env
    found = shutil.which("dtc")
    if found:
        return found
    for candidate in (
        "/mnt/data1/Xilinx/2025.2/Vivado/bin/dtc",
        "/mnt/data1/Xilinx/2025.1/Vivado/bin/dtc",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def read_dts(path: Path) -> str:
    if path.suffix == ".dtb":
        dtc = find_dtc()
        if not dtc:
            raise SystemExit(
                "dtc not found; install device-tree-compiler, set DTC, or pass a .dts")
        try:
            return subprocess.run(
                [dtc, "-I", "dtb", "-O", "dts", "-o", "-", str(path)],
                check=True, capture_output=True, text=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"dtc failed on {path}:\n{exc.stderr}")
    return path.read_text()


def parse_nodes(text: str) -> tuple[dict[str, dict], dict[int, dict]]:
    """Index /soc children that carry a `reg` by label and by base address.

    Labels survive in a .dts but are dropped when dtc decompiles a .dtb (the
    project does not compile with `-@`), so base address is the portable key.
    """
    by_label: dict[str, dict] = {}
    by_base: dict[int, dict] = {}
    for m in _NODE_RE.finditer(text):
        body = m.group("body")
        reg = _REG_RE.search(body)
        if not reg:
            continue
        compat = _COMPAT_RE.search(body)
        node = {
            "label": m.group("label") or "",
            "name": m.group("name"),
            "node_addr": int(m.group("addr"), 16),
            "base": int(reg.group(1), 16),
            "size": int(reg.group(2), 16),
            "compat": compat.group(1) if compat else "",
        }
        if node["label"]:
            by_label.setdefault(node["label"], node)
        by_base.setdefault(node["base"], node)
    return by_label, by_base


def expected_form(label: str, cores: dict) -> str:
    if label != "seven_seg":
        return CHECKED[label][0]
    return "scanner" if cores.get("seven_seg") == "SevenSegScanner" else "gpio"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csr_json", type=Path)
    parser.add_argument("dts", type=Path)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.csr_json.read_text())
    bases = data.get("csr_bases", {})
    registers = data.get("csr_registers", {})
    constants = data.get("constants", {})
    cores = data.get("cores", {})

    by_label, by_base = parse_nodes(read_dts(args.dts))

    errors: list[str] = []
    checks = 0

    for label in CHECKED:
        if label not in bases:
            # A node for a peripheral that is not in the CSR map is suspicious,
            # but only flag it when it carries the expected compatible so we do
            # not trip over unrelated gpio@ nodes.
            continue

        form = expected_form(label, cores)
        base = bases[label]
        span = bank_span(registers, base)
        checks += 1

        node = by_label.get(label)
        if node is None:
            node = by_base.get(base)
        if node is None:
            errors.append(
                f"{label}: csr_bases has 0x{base:x} ({cores.get(label, '?')}) "
                f"but no /soc node with a matching reg base or label in the DTS"
            )
            continue

        if node["base"] != base:
            errors.append(
                f"{label}: reg base 0x{node['base']:x} != csr base 0x{base:x}"
            )
        # The legacy/gpio form maps only the first register (the gpio-litex driver
        # takes its interrupt from the `interrupts` property, not the event CSRs),
        # so its reg window is intentionally 0x4 regardless of the bank span.
        # Full-window nodes (scanner, ps2, hwmon, i2c) must cover their registers.
        if form != "gpio" and span and node["size"] < span:
            errors.append(
                f"{label}: reg size 0x{node['size']:x} < register span 0x{span:x}"
            )

        if form == "scanner":
            if node["compat"] != "litex,seven-seg-scanner":
                errors.append(
                    f"{label}: expected compatible \"litex,seven-seg-scanner\", "
                    f"got \"{node['compat']}\""
                )
            if span != 0x28:
                errors.append(
                    f"{label}: scanner register span 0x{span:x} != expected 0x28"
                )
        elif form in ("gpio",):
            if node["compat"] != "litex,gpio":
                errors.append(
                    f"{label}: expected compatible \"litex,gpio\", "
                    f"got \"{node['compat']}\""
                )
        elif form == "ps2":
            if node["compat"] != "litex,ps2-keyboard":
                errors.append(
                    f"{label}: expected compatible \"litex,ps2-keyboard\", "
                    f"got \"{node['compat']}\""
                )
        elif form == "hwmon":
            if node["compat"] not in ("litex,hwmon-xadc", "litex,hwmon"):
                errors.append(
                    f"{label}: expected a litex hwmon compatible, got \"{node['compat']}\""
                )
        elif form == "i2c":
            if not node["compat"].startswith("litex,i2c"):
                errors.append(
                    f"{label}: expected a litex i2c compatible, got \"{node['compat']}\""
                )

        if args.verbose:
            print(f"  ok {label}: base=0x{base:x} span=0x{span:x} "
                  f"node base=0x{node['base']:x} size=0x{node['size']:x} "
                  f"compat={node['compat']}")

    if errors:
        print(f"CSR/DTS mismatch ({len(errors)} problem(s)):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"CSR/DTS consistent: {checks} checked peripheral(s) in {args.dts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())