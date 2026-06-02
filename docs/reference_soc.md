# Stage 1 reference SoC path

Stage 1 uses a known Linux-capable RISC-V SoC flow before attempting a custom CPU.

## Preferred path

Use LiteX with a VexRiscv/VexRiscvSMP Linux-capable CPU configuration.

The immediate objective is to build a reference bitstream that proves:

- Nexys4 DDR DDR2 initialization works in the new repository;
- UART console is usable;
- timer and interrupt topology are Linux-compatible;
- OpenSBI can hand off to Linux;
- Linux can reach a BusyBox shell on UART.

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
2. Identify the closest LiteX board target for Nexys4 DDR or Nexys A7 DDR.
3. Build a minimal LiteX SoC with UART and DDR.
4. Add Linux-capable CPU config and OpenSBI/Linux artifacts.
5. Capture UART boot logs.

## Acceptance

```text
OpenSBI banner
Linux kernel banner
BusyBox / # shell
```
