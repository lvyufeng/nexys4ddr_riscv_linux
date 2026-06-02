# Stage 1 reference SoC path

Stage 1 uses a known Linux-capable RISC-V SoC flow before attempting a custom CPU.

## Preferred path

Use LiteX with a VexRiscv/VexRiscvSMP Linux-capable CPU configuration.

The first concrete target is the upstream LiteX board module:

```text
litex_boards.targets.digilent_nexys4ddr
```

A no-compile probe is now captured in `scripts/probe_litex_nexys4ddr.sh`. It confirms that LiteX can elaborate a Nexys4 DDR SoC with VexRiscv, LiteDRAM DDR2, UART, timer, LEDs, and generated CSR/memory metadata.

The immediate objective is to build a reference bitstream that proves:

- Nexys4 DDR DDR2 initialization works in the new repository;
- UART console is usable;
- timer and interrupt topology are Linux-compatible;
- OpenSBI can hand off to Linux;
- Linux can reach a BusyBox shell on UART.

Current Stage 1 BIOS-only status: the minimal LiteX Nexys4 DDR bitstream builds, meets timing, programs over JTAG, and reaches the LiteX BIOS UART prompt.

## Why a reference SoC first

A custom Linux CPU requires several difficult blocks at once:

- RV32IMAC or RV64IMAC ISA support;
- privileged architecture;
- exception/interrupt delegation;
- Sv32/Sv39 MMU and TLB;
- CLINT/PLIC semantics;
- OpenSBI compatibility;
- Linux DTS/kernel/rootfs correctness.

A reference SoC isolates board/DDR/Linux-flow problems from custom CPU bugs.

## First concrete steps

1. Run `scripts/bootstrap_litex.sh` to install LiteX/Migen/LiteDRAM/litex-boards into local ignored directories.
2. Run `scripts/probe_litex_nexys4ddr.sh` to generate LiteX SoC metadata without invoking Vivado.
3. Install or point `PATH` at a RISC-V cross compiler so LiteX can build BIOS/software.
4. Build a minimal LiteX SoC bitstream with UART and DDR. **Done:** `build/litex_nexys4ddr/gateware/digilent_nexys4ddr.bit` builds and meets timing.
5. Program the board and verify the LiteX BIOS UART prompt. **Done:** `LITEX_PROGRAMMED=xc7a100t_0`, `LITEX_UART_SMOKE_OK`.
6. Add Linux-capable CPU config and OpenSBI/Linux artifacts.
7. Capture UART Linux boot logs.

## Probe result

The default upstream target currently elaborates with:

```text
CPU:        VexRiscv standard
Clock:      75 MHz system clock from 100 MHz board clock
Bus:        32-bit Wishbone
ROM:        0x00000000, 128 KiB
SRAM:       0x10000000, 8 KiB
main_ram:   0x40000000, 128 MiB DDR2
CSR window: 0xf0000000, 64 KiB
IRQs:       UART=0, timer0=1
CSRs:       ctrl, ddrphy, identifier_mem, leds, sdram, timer0, uart
```

This is enough for firmware/DDR bring-up. For the Linux milestone, the final address map may need to be adjusted to the conventional RISC-V Linux DRAM base `0x80000000`, or the generated LiteX Linux device tree/boot flow must consistently describe the LiteX default `0x40000000` DRAM base.

## Acceptance

```text
OpenSBI banner
Linux kernel banner
BusyBox / # shell
```
