#!/usr/bin/env python3
"""Derive tools/patch_litex_nexys4ddr_dts.py arguments from a LiteX csr.json.

This is the single source of truth for the DTS patch argument list. It replaces
the ~64-line block that used to be duplicated in both
scripts/build_litex_nexys4ddr_linux.sh and scripts/probe_litex_nexys4ddr_linux.sh.

Emits one argument per line so a shell caller can do:

    mapfile -t PATCH_ARGS < <(python3 tools/dts_patch_args.py "$CSR_JSON")
    python3 tools/patch_litex_nexys4ddr_dts.py "$DTS" "${PATCH_ARGS[@]}"

The seven-segment bank is discriminated by its LiteX core type, not by a GPIO
count: the current target wires a `SevenSegScanner` register block (single bank,
`control`/`digit0..7`/`status`, exposed as a custom compatible), while older
builds wired two `GPIOOut` banks (`seven_seg`/`seven_seg_ctrl`). Both layouts are
supported so an older checkpoint still generates a correct DTS.

Optional overrides come from the environment, mirroring the previous shell
defaults:

    LITEX_LEDS_NGPIO            (default 16)
    LITEX_SWITCHES_NGPIO        (default 16)
    LITEX_BUTTONS_NGPIO         (default 5)
    LITEX_RGB_LEDS_NGPIO        (default 6)
    LITEX_PS2_KEYBOARD_NGPIO    (default 2)
    LITEX_SEVEN_SEG_NGPIO       (default 8)  # legacy GPIOOut layout only
    LITEX_SEVEN_SEG_CTRL_NGPIO  (default 8)  # legacy GPIOOut layout only
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Bounded search window used to compute a bank's register span from csr.json.
# Generous enough to cover any current bank, small enough not to swallow a
# neighbouring bank's registers.
_SPAN_WINDOW = 0x100


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        raise SystemExit(f"{name}: expected an integer, got {raw!r}")


def bank_span(registers: dict, base: int) -> int:
    """Return the byte span of the CSR registers that live inside `base`.

    LiteX emits one 32-bit word per register, so a register occupying `size`
    words ends `size * 4` bytes after its address.
    """
    end = base
    for reg in registers.values():
        addr = reg.get("addr")
        if addr is None or not (base <= addr < base + _SPAN_WINDOW):
            continue
        end = max(end, addr + 4 * int(reg.get("size", 1)))
    return end - base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csr_json")
    args = parser.parse_args()

    with open(args.csr_json) as f:
        data = json.load(f)

    bases = data.get("csr_bases", {})
    registers = data.get("csr_registers", {})
    constants = data.get("constants", {})
    cores = data.get("cores", {})

    out: list[str] = []

    def add(flag: str, value) -> None:
        out.append(f"{flag}={value}")

    def add_flag(flag: str) -> None:
        out.append(flag)

    def add_if_present(flag: str, value) -> None:
        if value is not None:
            add(flag, value)

    # LED count is not emitted as a LiteX constant (LedChaser), so it stays an
    # environment/default override.
    add("--leds-ngpio", env_int("LITEX_LEDS_NGPIO", 16))

    for name, env_name, default in (
        ("switches", "LITEX_SWITCHES_NGPIO", 16),
        ("buttons", "LITEX_BUTTONS_NGPIO", 5),
        ("rgb_leds", "LITEX_RGB_LEDS_NGPIO", 6),
    ):
        ngpio = constants.get(f"{name}_ngpio")
        add(f"--{name.replace('_', '-')}-ngpio",
            ngpio if ngpio is not None else env_int(env_name, default))

    add_if_present("--buttons-base", _hex(bases.get("buttons")))
    add_if_present("--buttons-interrupt", constants.get("buttons_interrupt"))
    add_if_present("--rgb-leds-base", _hex(bases.get("rgb_leds")))

    seven_seg_base = bases.get("seven_seg")
    if cores.get("seven_seg") == "SevenSegScanner":
        # Hardware-scanned register block: one custom node, no GPIO banks.
        ngpio_zero = constants.get("seven_seg_ngpio", 0)
        add("--seven-seg-ngpio", ngpio_zero if ngpio_zero else 0)
        add("--seven-seg-ctrl-ngpio", 0)
        if seven_seg_base is not None:
            add_flag("--seven-seg-scanner")
            add_if_present("--seven-seg-base", _hex(seven_seg_base))
            window = bank_span(registers, seven_seg_base)
            add("--seven-seg-window", hex(window if window else 0x28))
    else:
        # Legacy two-bank GPIOOut layout.
        seven_seg_ngpio = constants.get("seven_seg_ngpio")
        add("--seven-seg-ngpio",
            seven_seg_ngpio if seven_seg_ngpio is not None
            else env_int("LITEX_SEVEN_SEG_NGPIO", 8))
        seven_seg_ctrl_ngpio = constants.get("seven_seg_ctrl_ngpio")
        add("--seven-seg-ctrl-ngpio",
            seven_seg_ctrl_ngpio if seven_seg_ctrl_ngpio is not None
            else env_int("LITEX_SEVEN_SEG_CTRL_NGPIO", 8))
        add_if_present("--seven-seg-base", _hex(seven_seg_base))
        add_if_present("--seven-seg-ctrl-base", _hex(bases.get("seven_seg_ctrl")))

    add_if_present("--ps2-keyboard-base", _hex(bases.get("ps2_keyboard")))
    add_if_present("--ps2-keyboard-interrupt", constants.get("ps2_keyboard_interrupt"))
    add("--ps2-keyboard-ngpio", env_int("LITEX_PS2_KEYBOARD_NGPIO", 2))

    add_if_present("--xadc-base", _hex(bases.get("xadc")))
    add_if_present("--temp-i2c-base", _hex(bases.get("temp_i2c")))

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))
    return 0


def _hex(value):
    return hex(value) if value is not None else None


if __name__ == "__main__":
    raise SystemExit(main())