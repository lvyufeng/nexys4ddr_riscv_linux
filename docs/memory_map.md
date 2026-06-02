# Draft memory map

This is the initial Linux-friendly memory map. It may change as the reference SoC is selected.

```text
0x0000_0000 - 0x0000_FFFF    boot ROM / reset vector area
0x0200_0000 - 0x0200_FFFF    CLINT / ACLINT timer region
0x0C00_0000 - 0x0FFF_FFFF    PLIC external interrupt controller
0x1000_0000 - 0x1000_0FFF    UART console, preferably ns16550-compatible
0x1001_0000 - 0x1001_0FFF    GPIO / LEDs / switches / buttons
0x1002_0000 - 0x1002_0FFF    SPI controller, future
0x1003_0000 - 0x1003_0FFF    VGA / framebuffer control, future
0x8000_0000 - 0x87FF_FFFF    DDR2, 128 MiB
```

## Linux expectations

Linux RISC-V commonly expects RAM at `0x8000_0000`. Keeping DDR there simplifies OpenSBI/Linux conventions.

Minimum Linux-visible devices:

- memory node for DDR;
- CPU and timebase;
- UART console;
- CLINT/ACLINT or equivalent timer interrupt source;
- PLIC for external interrupts.

## Device compatibility preference

Prefer Linux-supported compatible devices:

- UART: `ns16550a` when feasible;
- interrupt controller: `riscv,plic0` style PLIC;
- timer: `riscv,clint0` / ACLINT-compatible path;
- GPIO: generic GPIO with `gpio-leds` / `gpio-keys` bindings;
- framebuffer: `simple-framebuffer` after basic VGA timing is stable.
