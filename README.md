# nexys4ddr_riscv_linux

RISC-V Linux-capable SoC project for the Digilent Nexys4 DDR / Artix-7 board.

The goal is to build a Linux-capable RISC-V platform on Nexys4 DDR, starting from a minimal bootable SoC and then enabling board peripherals in staged milestones. This is intentionally a separate project from `step_into_mips`: the old repository is a MIPS teaching-lab progression ending in StepOS, while this repository targets a RISC-V privileged/MMU/Linux platform.

## Target board

- Board: Digilent Nexys4 DDR, Rev. C compatible
- FPGA: Xilinx Artix-7 `xc7a100tcsg324-1`
- Clock: 100 MHz board clock
- Memory: 128 MiB DDR2 via MIG 7-series
- Console: USB-UART, typically `/dev/ttyUSB1`, `115200 8N1`

## Bring-up strategy

This project will use two tracks:

1. **Reference Linux SoC track**: first bring up a known Linux-capable RISC-V SoC path, preferably LiteX + VexRiscv/VexRiscvSMP or an equivalent reference core. This validates the board, DDR, OpenSBI, device tree, Linux kernel, and rootfs flow.
2. **Custom CPU track**: incrementally develop a custom RISC-V CPU, starting from RV32I bare metal and eventually adding the features required for Linux: RV32IMAC, privileged architecture, Sv32 MMU/TLB, CLINT/PLIC integration, OpenSBI, and Linux S-mode boot.

The first acceptance target is **not all peripherals**. The first target is a minimal Linux shell:

```text
Boot ROM / loader -> OpenSBI -> Linux kernel -> initramfs -> BusyBox shell
```

## Phase 1 minimum Linux platform

Minimum hardware/software needed:

```text
RISC-V Linux-capable CPU, initially reference core
DDR2 at 0x8000_0000
UART console
CLINT / ACLINT timer
PLIC external interrupt controller
Boot ROM / boot loader path
OpenSBI firmware
Linux kernel
initramfs / BusyBox rootfs
Device tree
```

Expected UART milestone:

```text
OpenSBI ...
Linux version ...
Freeing unused kernel memory
Run /init as init process
/ #
```

## Later peripheral milestones

After Linux boots reliably:

1. GPIO-class devices: LEDs, switches, buttons, RGB LEDs, 7-segment display.
2. SPI-class devices: microSD in SPI mode, accelerometer, temperature sensor where applicable.
3. Display: VGA timing + simple framebuffer.
4. Audio/mic and other board peripherals as separate driver/peripheral tasks.

See [`docs/peripherals.md`](docs/peripherals.md).

## Repository layout

```text
boards/nexys4ddr/   Board constraints, MIG project, board-specific notes
rtl/cpu/            Custom RISC-V CPU work
rtl/soc/            SoC top, buses, boot ROM, memory map integration
rtl/perip/          UART/CLINT/PLIC/GPIO/SPI/VGA/etc.
sim/                Unit and SoC simulations
firmware/           Boot ROM and OpenSBI integration notes/artifacts
linux/              Device tree, kernel config, Linux notes
buildroot/          Buildroot defconfigs and rootfs notes
scripts/            Build, simulation, programming, Linux/rootfs helper scripts
docs/               Bring-up plan, memory map, boot flow, peripheral docs
tools/              Helper tools
```

## Initial commands

The Stage 1 reference path uses LiteX's upstream Nexys4 DDR target to prove board, DDR, UART, and metadata generation before moving to Linux firmware/kernel work.

```bash
./scripts/bootstrap_litex.sh
./scripts/check_toolchain.sh
./scripts/probe_litex_nexys4ddr.sh
./scripts/probe_litex_nexys4ddr_linux.sh
./scripts/build_litex_nexys4ddr.sh
./scripts/build_litex_nexys4ddr_linux.sh
./scripts/program_litex_nexys4ddr.sh   # optional, requires connected board
```

The probe should generate `build/litex_nexys4ddr_probe/` with `csr.json`, `csr.csv`, `memory.x`, and gateware source/TCL/XDC files. Full bitstream/BIOS build requires Vivado plus a RISC-V cross compiler. The build script automatically adds Vivado 2025.2's bundled `riscv64-unknown-elf-gcc` path when present.

Current Stage 1 status: both the minimal LiteX bitstream and the Linux-capable VexRiscvSMP bitstream build with routed timing met, program successfully, and reach the LiteX BIOS UART prompt (`litex>`).

Vivado environment example:

```bash
set +u
unset ZSH_VERSION
source /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh
```

## Relationship to `step_into_mips`

The completed `step_into_mips` repository can be used as board bring-up reference for:

- Nexys4 DDR XDC pin constraints;
- MIG 7-series DDR2 project settings;
- UART/GPIO/timer MMIO testing habits;
- Vivado batch script style;
- serial/JTAG verification workflow.

It should not be used as the code base for Linux directly because Linux-capable RISC-V requires a different CPU architecture, privileged spec, MMU, interrupt topology, firmware, and device tree flow.
