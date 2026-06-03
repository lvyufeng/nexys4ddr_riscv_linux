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


def insert_buttons_node(text: str, buttons_base: int, buttons_interrupt: int | None) -> tuple[str, bool]:
    if "buttons: gpio@" in text:
        return text, False
    interrupt_line = ""
    if buttons_interrupt is not None:
        interrupt_line = f"\n                interrupts = <{buttons_interrupt}>;"
    node = f'''
            buttons: gpio@{buttons_base:x} {{
                compatible = "litex,gpio";
                reg = <0x{buttons_base:x} 0x4>;
                gpio-controller;
                #gpio-cells = <2>;
                litex,direction = "in";{interrupt_line}
                status = "disabled";
            }};
'''
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit("failed to locate /soc closing marker for buttons node insertion")
    return text.replace(marker, node + marker, 1), True


def append_buttons_ref(text: str, ngpio: int) -> tuple[str, bool]:
    if "&buttons" in text:
        return text, False
    block = f'''
&buttons {{
        litex,ngpio = <{ngpio}>;
        status = "okay";
}};
'''
    return text.rstrip() + "\n" + block, True


def insert_gpio_node(text: str, name: str, base: int, direction: str) -> tuple[str, bool]:
    if f"{name}: gpio@" in text:
        return text, False
    node = f'''
            {name}: gpio@{base:x} {{
                compatible = "litex,gpio";
                reg = <0x{base:x} 0x4>;
                gpio-controller;
                #gpio-cells = <2>;
                litex,direction = "{direction}";
                status = "disabled";
            }};
'''
    marker = "\n        };\n\n        aliases {"
    if marker not in text:
        raise SystemExit(f"failed to locate /soc closing marker for {name} node insertion")
    return text.replace(marker, node + marker, 1), True


def append_gpio_ref(text: str, name: str, ngpio: int) -> tuple[str, bool]:
    if f"&{name}" in text:
        return text, False
    block = f'''
&{name} {{
        litex,ngpio = <{ngpio}>;
        status = "okay";
}};
'''
    return text.rstrip() + "\n" + block, True


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
        text, inserted = insert_buttons_node(text, args.buttons_base, args.buttons_interrupt)
        if inserted:
            print(f"Inserted buttons GPIO node at 0x{args.buttons_base:x}")
        text, appended = append_buttons_ref(text, args.buttons_ngpio)
        if appended:
            print(f"Appended &buttons litex,ngpio = <{args.buttons_ngpio}>")

    extra_outputs = [
        ("rgb_leds", args.rgb_leds_base, args.rgb_leds_ngpio),
        ("seven_seg", args.seven_seg_base, args.seven_seg_ngpio),
        ("seven_seg_ctrl", args.seven_seg_ctrl_base, args.seven_seg_ctrl_ngpio),
    ]
    for name, base, ngpio in extra_outputs:
        if base is None:
            continue
        text, inserted = insert_gpio_node(text, name, base, "out")
        if inserted:
            print(f"Inserted {name} GPIO node at 0x{base:x}")
        text, appended = append_gpio_ref(text, name, ngpio)
        if appended:
            print(f"Appended &{name} litex,ngpio = <{ngpio}>")

    args.dts.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
