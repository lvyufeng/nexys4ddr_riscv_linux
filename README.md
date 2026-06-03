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

Current Stage 1 status: both the minimal LiteX bitstream and the Linux-capable VexRiscvSMP bitstream build with routed timing met, program successfully, and reach the LiteX BIOS UART prompt (`litex>`). OpenSBI + Linux 6.9 + Buildroot have also been serial-loaded into DDR and verified on hardware to reach `buildroot login:` and a root shell. The default Linux-capable bitstream now includes the board microSD slot in SPI mode plus LiteEth Ethernet; an 8 GB SDHC card is prepared with a VFAT boot partition and ext4 root partition, Linux has booted with `/dev/mmcblk0p2` mounted as `/`, and Dropbear SSH has been verified over Ethernet.

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
  -> Image          @ 0x40000000
  -> rv32.dtb       @ 0x40ef0000
  -> rootfs.cpio.gz @ 0x41000000
  -> opensbi.bin    @ 0x40f00000
  -> Buildroot login/root shell
```

A second verified boot path keeps only the kernel, DTB, and OpenSBI on the serial
loader and mounts the root filesystem from the board microSD card:

```text
LiteX BIOS / serial SFL loader
  -> Image           @ 0x40000000
  -> rv32_sdroot.dtb @ 0x40ef0000
  -> opensbi.bin     @ 0x40f00000
  -> root=/dev/mmcblk0p2 rootfstype=ext4 rw
  -> litex-sdroot login/root shell
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

For the SD-root path, prepare the SD-root DTB/image map and boot without uploading
`rootfs.cpio.gz`:

```bash
./scripts/prepare_litex_sdroot_images.sh
./scripts/boot_litex_linux_sdroot_serial.sh /dev/ttyUSB1
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

`/dev/mmcblk0p1` mounted read-only as VFAT in the first hardware smoke test. The
same 8 GB card is now prepared as:

```text
/dev/mmcblk0p1  VFAT  LITEXBOOT   boot payload copy
/dev/mmcblk0p2  ext4  LITEXROOT   Buildroot rootfs
```

The SD-root smoke test passed with hostname `litex-sdroot`, kernel command line
`root=/dev/mmcblk0p2 rootfstype=ext4 rw`, and `/dev/root on / type ext4`.

The current default Linux-capable LiteX build also enables the Nexys4 DDR RMII
Ethernet path (`LITEX_WITH_ETHERNET=1`). Hardware verification passed with the
SD-root card still mounted as root:

```text
liteeth f0002000.mac eth0: irq 13 slots: tx 2 rx 2 size 2048
eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
udhcpc: lease of 192.168.1.223 obtained from 192.168.1.1
ping 192.168.1.1: 3 packets transmitted, 3 packets received, 0% packet loss
```

The Buildroot image now enables Dropbear and sets the lab root password to
`root` by default, so the board can be reached over SSH after DHCP:

```bash
ssh root@192.168.1.223
# password: root
```

Host-side SSH verification returned `litex-sdroot` from the board. The DHCP
address can change on later boots, so use the serial console or DHCP leases to
confirm the current address.

Ethernet/TFTP/NFS boot remains a later boot-media path; for now Ethernet is a
Linux peripheral on top of the verified SD-root boot flow.

The board's GPIO-class peripherals are now enabled and verified from SD-root Linux.
The 16 user LEDs appear as `/dev/gpiochip0` (`litex_gpio`, 16 output lines) and
a chaser plus `0xffff`/`0xaaaa`/`0x5555` patterns drove all 16 LEDs
successfully. The 16 user switches and 5 push buttons are enabled as Linux GPIO
input controllers (`/dev/gpiochip1` and `/dev/gpiochip2`) and verified from the
SD-root shell with a GPIO character UAPI smoke test. The two RGB LEDs and
seven-segment display are also enabled as simple GPIO output controllers:

```text
/dev/gpiochip3  rgb_leds        6 output lines
/dev/gpiochip4  seven_seg       8 output lines
/dev/gpiochip5  seven_seg_ctrl  8 output lines, active-low digit enables
```

The RGB LED channels and seven-segment digit scan were verified over SSH with a
GPIO character-UAPI helper. See [`docs/peripherals.md`](docs/peripherals.md).

## Relationship to `step_into_mips`

The completed `step_into_mips` repository can be used as board bring-up reference for:

- Nexys4 DDR XDC pin constraints;
- MIG 7-series DDR2 project settings;
- UART/GPIO/timer MMIO testing habits;
- Vivado batch script style;
- serial/JTAG verification workflow.

It should not be used as the code base for Linux directly because Linux-capable RISC-V requires a different CPU architecture, privileged spec, MMU, interrupt topology, firmware, and device tree flow.
