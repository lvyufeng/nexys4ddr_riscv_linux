# nexys4ddr_riscv_linux

RISC-V Linux-capable SoC project for the Digilent Nexys4 DDR / Artix-7 board.

The goal is to build a Linux-capable RISC-V platform on Nexys4 DDR, starting from a minimal bootable SoC and then enabling board peripherals in staged milestones. This is intentionally a separate project from `step_into_mips`: the old repository is a MIPS teaching-lab progression ending in StepOS, while this repository targets a RISC-V privileged/MMU/Linux platform.

## Target board

- Board: Digilent Nexys4 DDR, Rev. C compatible
- FPGA: Xilinx Artix-7 `xc7a100tcsg324-1`
- Clock: 100 MHz board clock
- Memory: 128 MiB DDR2 via MIG 7-series
- Console: USB-UART, typically `/dev/ttyUSB1`; the Linux-capable LiteX bitstream now defaults to `1000000 8N1`

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
DDR2 at 0x4000_0000 in the current LiteX reference SoC
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
Freeing unused kernel image
Run /init as init process
Welcome to Buildroot
buildroot login:
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

Current Stage 1 status: both the minimal LiteX bitstream and the Linux-capable VexRiscvSMP bitstream build with routed timing met, program successfully, and reach the LiteX BIOS UART prompt (`litex>`). OpenSBI + Linux 6.9 + Buildroot have also been serial-loaded into DDR and verified on hardware to reach `buildroot login:` and a root shell. The Linux-capable bitstream now includes the board microSD slot in SPI mode; Linux detects an inserted 8 GB SDHC card as `/dev/mmcblk0` and can mount its first partition.

Vivado environment example:

```bash
set +u
unset ZSH_VERSION
source /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh
```

## Verified Linux boot flow

The current reference boot path is:

```text
LiteX BIOS / serial SFL loader
  -> Image       @ 0x40000000
  -> rv32.dtb    @ 0x40ef0000
  -> rootfs.cpio.gz @ 0x41000000
  -> opensbi.bin @ 0x40f00000
  -> Buildroot login/root shell
```

Build and collect software images:

```bash
./scripts/bootstrap_linux_on_litex.sh
./scripts/build_buildroot_litex.sh
```

Then program the Linux-capable bitstream and boot over serial:

```bash
./scripts/program_litex_nexys4ddr.sh build/litex_nexys4ddr_linux/gateware/digilent_nexys4ddr.bit
./scripts/boot_litex_linux_serial.sh /dev/ttyUSB1
```

`boot_litex_linux_serial.sh` uses `scripts/serial_boot_litex_images.py`, a
non-interactive LiteX SFL uploader that works over SSH/background jobs without a
real terminal. The current serial path uses a gzip-compressed initramfs and a 1,000,000 baud
LiteUART configuration, reducing the uploaded image set from about 20 MiB to
about 14 MiB and improving SFL throughput by roughly an order of magnitude.
For an older 115200-baud bitstream, run the wrapper with `LITEX_BAUD=115200`.
The bitstream also enables board microSD in SPI mode (`LITEX_WITH_SPI_SDCARD=1`,
default); after boot, an inserted 8 GB SDHC card was verified as:

```text
mmc_spi spi0.0: SD/MMC host mmc0
mmc0: new SDHC card on SPI
mmcblk0: mmc0:0000 SL08G 7.40 GiB
 mmcblk0: p1
```

`/dev/mmcblk0p1` mounted read-only as VFAT in the hardware smoke test. Moving
rootfs or boot payloads onto SD is the next storage milestone; Ethernet/TFTP/NFS
remains another long-term boot-media path.

## Relationship to `step_into_mips`

The completed `step_into_mips` repository can be used as board bring-up reference for:

- Nexys4 DDR XDC pin constraints;
- MIG 7-series DDR2 project settings;
- UART/GPIO/timer MMIO testing habits;
- Vivado batch script style;
- serial/JTAG verification workflow.

It should not be used as the code base for Linux directly because Linux-capable RISC-V requires a different CPU architecture, privileged spec, MMU, interrupt topology, firmware, and device tree flow.
