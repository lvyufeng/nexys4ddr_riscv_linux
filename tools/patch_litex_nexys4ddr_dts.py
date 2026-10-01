#!/usr/bin/env python3
"""Patch LiteX-generated Nexys4 DDR Linux DTS for project GPIO metadata."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def patch_ref_ngpio(text: str, ref: str, ngpio: int) -> tuple[str, bool]:
    pattern = rf"(&{re.escape(ref)}\s*\{{.*?litex,ngpio\s*=\s*<)\d+(>)"
    text, count = re.subn(
        pattern,
        lambda m: m.group(1) + str(ngpio) + m.group(2),
        text,
        count=1,
        flags=re.DOTALL,
    )
    return text, bool(count)


def insert_gpio_node(
    text: str,
    name: str,
    base: int,
    direction: str,
    *,
    interrupt: int | None = None,
    interrupt_controller: bool = False,
    reg_size: int = 0x4,
) -> tuple[str, bool]:
    if f"{name}: gpio@" in text:
        return text, False
    irq_provider = ""
    if interrupt_controller:
        irq_provider = "\n                interrupt-controller;\n                #interrupt-cells = <2>;\n                #address-cells = <0>;"
    interrupt_line = ""
    if interrupt is not None:
        interrupt_line = f"\n                interrupts = <{interrupt}>;"
    node = f"""
            {name}: gpio@{base:x} {{
                compatible = "litex,gpio";
                reg = <0x{base:x} 0x{reg_size:x}>;
                gpio-controller;
                #gpio-cells = <2>;{irq_provider}
                litex,direction = "{direction}";{interrupt_line}
                status = "disabled";
            }};
"""
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit(f"failed to locate /soc closing marker for {name} node insertion")
    return text.replace(marker, node + marker, 1), True


def append_gpio_ref(text: str, name: str, ngpio: int) -> tuple[str, bool]:
    if f"&{name}" in text:
        return text, False
    block = f"""
&{name} {{
        litex,ngpio = <{ngpio}>;
        status = "okay";
}};
"""
    return text.rstrip() + "\n" + block, True


def insert_xadc_node(text: str, base: int) -> tuple[str, bool]:
    if "xadc: hwmon@" in text or 'compatible = "litex,hwmon-xadc"' in text:
        return text, False
    node = f"""
            xadc: hwmon@{base:x} {{
                compatible = "litex,hwmon-xadc";
                reg = <0x{base:x} 0x20>;
                litex,temperature-csr-offset = <0x00>;
                litex,vccint-csr-offset = <0x04>;
                litex,vccaux-csr-offset = <0x08>;
                litex,vccbram-csr-offset = <0x0c>;
                litex,temperature-mul = <503975>;
                litex,temperature-div = <4096>;
                litex,temperature-offset = <273150>;
                litex,voltage-mul = <3000>;
                litex,voltage-div = <4096>;
                status = "okay";
            }};
"""
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit("failed to locate /soc closing marker for xadc insertion")
    return text.replace(marker, node + marker, 1), True


def insert_i2c_node(text: str, name: str, base: int) -> tuple[str, bool]:
    if f"{name}: i2c@" in text or f"i2c@{base:x}" in text:
        return text, False
    node = f"""
            {name}: i2c@{base:x} {{
                compatible = "litex,i2c";
                reg = <0x{base:x} 0x8>;
                #address-cells = <1>;
                #size-cells = <0>;
                status = "okay";
            }};
"""
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit(f"failed to locate /soc closing marker for {name} I2C insertion")
    return text.replace(marker, node + marker, 1), True


def insert_ps2_keyboard_node(text: str, base: int, interrupt: int | None) -> tuple[str, bool]:
    if "ps2_keyboard: ps2@" in text or 'compatible = "litex,ps2-keyboard"' in text:
        return text, False
    interrupt_line = ""
    if interrupt is not None:
        interrupt_line = f"\n                interrupts = <{interrupt}>;"
    # The LiteX PS/2 keyboard block samples receive frames in fabric and exposes
    # complete Set-2 bytes through a FIFO to a Linux serio driver. Newer gateware
    # also appends open-drain host command/status CSRs for PS/2 reset/enable
    # scanning, so reserve the full 0x40-byte register window.
    node = f"""
            ps2_keyboard: ps2@{base:x} {{
                compatible = "litex,ps2-keyboard";
                reg = <0x{base:x} 0x40>;{interrupt_line}
                litex,tx-supported;
                litex,host-init;
                status = "okay";
            }};
"""
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit("failed to locate /soc closing marker for ps2 keyboard insertion")
    return text.replace(marker, node + marker, 1), True


def insert_seven_seg_scanner_node(text: str, base: int, window: int) -> tuple[str, bool]:
    """Insert the hardware-scanned seven-segment register block node.

    The current target feeds the display from a `SevenSegScanner` CSR block
    (control + eight digit masks + status) rather than two `GPIOOut` banks, so it
    is exposed as a single custom-compatible register window instead of a gpiochip.
    """
    if "seven_seg: seven-seg@" in text or 'compatible = "litex,seven-seg-scanner"' in text:
        return text, False
    node = f"""
            seven_seg: seven-seg@{base:x} {{
                compatible = "litex,seven-seg-scanner";
                reg = <0x{base:x} 0x{window:x}>;
                status = "okay";
            }};
"""
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit("failed to locate /soc closing marker for seven_seg scanner insertion")
    return text.replace(marker, node + marker, 1), True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dts", type=Path)
    parser.add_argument("--leds-ngpio", type=int, default=16)
    parser.add_argument("--switches-ngpio", type=int, default=16)
    parser.add_argument("--buttons-ngpio", type=int, default=5)
    parser.add_argument("--buttons-base", type=lambda x: int(x, 0))
    parser.add_argument("--buttons-interrupt", type=int)
    parser.add_argument("--rgb-leds-ngpio", type=int, default=6)
    parser.add_argument("--rgb-leds-base", type=lambda x: int(x, 0))
    parser.add_argument("--seven-seg-ngpio", type=int, default=8)
    parser.add_argument("--seven-seg-base", type=lambda x: int(x, 0))
    parser.add_argument("--seven-seg-ctrl-ngpio", type=int, default=8)
    parser.add_argument("--seven-seg-ctrl-base", type=lambda x: int(x, 0))
    parser.add_argument(
        "--seven-seg-scanner",
        action="store_true",
        help="Emit a litex,seven-seg-scanner node instead of GPIO banks.",
    )
    parser.add_argument(
        "--seven-seg-window",
        type=lambda x: int(x, 0),
        default=0x28,
        help="Register window size for the scanner node.",
    )
    parser.add_argument("--ps2-keyboard-ngpio", type=int, default=2)
    parser.add_argument("--ps2-keyboard-base", type=lambda x: int(x, 0))
    parser.add_argument("--ps2-keyboard-interrupt", type=int)
    parser.add_argument("--xadc-base", type=lambda x: int(x, 0))
    parser.add_argument("--temp-i2c-base", type=lambda x: int(x, 0))
    args = parser.parse_args()

    text = args.dts.read_text()

    text, patched_leds = patch_ref_ngpio(text, "leds", args.leds_ngpio)
    if patched_leds:
        print(f"Patched &leds litex,ngpio = <{args.leds_ngpio}>")

    if "&switches" in text:
        text, patched_switches = patch_ref_ngpio(text, "switches", args.switches_ngpio)
        if patched_switches:
            print(f"Patched &switches litex,ngpio = <{args.switches_ngpio}>")

    if args.buttons_base is not None:
        text, inserted = insert_gpio_node(
            text, "buttons", args.buttons_base, "in", interrupt=args.buttons_interrupt
        )
        if inserted:
            print(f"Inserted buttons GPIO node at 0x{args.buttons_base:x}")
        text, appended = append_gpio_ref(text, "buttons", args.buttons_ngpio)
        if appended:
            print(f"Appended &buttons litex,ngpio = <{args.buttons_ngpio}>")

    extra_outputs = [
        ("rgb_leds", args.rgb_leds_base, args.rgb_leds_ngpio),
    ]
    for name, base, ngpio in extra_outputs:
        if base is None or ngpio <= 0:
            continue
        text, inserted = insert_gpio_node(text, name, base, "out")
        if inserted:
            print(f"Inserted {name} GPIO node at 0x{base:x}")
        text, appended = append_gpio_ref(text, name, ngpio)
        if appended:
            print(f"Appended &{name} litex,ngpio = <{ngpio}>")

    # The seven-segment display has two mutually exclusive hardware contracts:
    # a single SevenSegScanner register window, or the legacy pair of GPIOOut
    # banks. dts_patch_args.py discriminates by the generated core type and sets
    # exactly one of these paths; the ngpio<=0 guard still suppresses any bank
    # whose count is zero so a stale constant cannot emit a bogus gpiochip.
    if args.seven_seg_scanner:
        if args.seven_seg_base is not None:
            text, inserted = insert_seven_seg_scanner_node(
                text, args.seven_seg_base, args.seven_seg_window)
            if inserted:
                print(f"Inserted seven_seg scanner node at 0x{args.seven_seg_base:x} "
                      f"(window 0x{args.seven_seg_window:x})")
    else:
        for name, base, ngpio in (
            ("seven_seg", args.seven_seg_base, args.seven_seg_ngpio),
            ("seven_seg_ctrl", args.seven_seg_ctrl_base, args.seven_seg_ctrl_ngpio),
        ):
            if base is None or ngpio <= 0:
                continue
            text, inserted = insert_gpio_node(text, name, base, "out")
            if inserted:
                print(f"Inserted {name} GPIO node at 0x{base:x}")
            text, appended = append_gpio_ref(text, name, ngpio)
            if appended:
                print(f"Appended &{name} litex,ngpio = <{ngpio}>")

    if args.ps2_keyboard_base is not None:
        text, inserted = insert_ps2_keyboard_node(
            text,
            args.ps2_keyboard_base,
            args.ps2_keyboard_interrupt,
        )
        if inserted:
            print(f"Inserted ps2_keyboard RX node at 0x{args.ps2_keyboard_base:x}")

    if args.xadc_base is not None:
        text, inserted = insert_xadc_node(text, args.xadc_base)
        if inserted:
            print(f"Inserted xadc hwmon node at 0x{args.xadc_base:x}")

    if args.temp_i2c_base is not None:
        text, inserted = insert_i2c_node(text, "temp_i2c", args.temp_i2c_base)
        if inserted:
            print(f"Inserted temp_i2c node at 0x{args.temp_i2c_base:x}")

    args.dts.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
