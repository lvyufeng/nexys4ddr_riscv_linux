# Nexys4 DDR RISC-V Linux bring-up plan

## Goal

Bring up a Linux-capable RISC-V SoC on Nexys4 DDR, then incrementally enable board peripherals.

The project should avoid mixing too many unknowns at once. First validate a reference Linux SoC path, then develop or replace pieces with custom RTL.

## Stage 0: repository and board baseline

Deliverables:

- stable repository skeleton;
- board notes and constraints copied/adapted from the proven Nexys4 DDR flow;
- MIG DDR2 project file checked in under `boards/nexys4ddr/mig/`;
- memory map draft;
- Linux boot flow draft.

Verification:

```bash
git status --short
```

## Stage 1: reference Linux-capable SoC

Recommended first implementation path:

- LiteX + VexRiscv/VexRiscvSMP or another proven RISC-V Linux reference core;
- DDR2 through Nexys4 DDR MIG;
- UART console;
- CLINT/ACLINT timer;
- PLIC interrupt controller;
- generated or hand-written device tree;
- OpenSBI;
- Linux kernel + initramfs.

Acceptance:

```text
OpenSBI banner appears on UART
Linux kernel boots
BusyBox shell appears on UART
```

## Stage 2: minimal Linux SoC cleanup

Once Linux boots:

- freeze memory map;
- document exact DTS;
- create reproducible scripts for kernel/rootfs/firmware build;
- add serial smoke test script;
- add timing/resource report checks.

Acceptance:

```text
single command or documented sequence rebuilds bitstream + firmware + Linux image
```

## Stage 3: GPIO-class board peripherals

Enable simple peripherals using Linux-friendly device tree bindings:

- LEDs: `gpio-leds`;
- buttons: `gpio-keys`;
- switches: GPIO inputs;
- RGB LEDs and 7-segment display as GPIO/PWM/simple MMIO.

Acceptance examples:

```bash
gpiodetect
gpioinfo
gpioset ...
dmesg | grep -i gpio
```

## Stage 4: storage and SPI-class peripherals

Enable:

- microSD, SPI-mode first;
- accelerometer if connected through SPI/I2C;
- temperature sensor where applicable.

Current microSD status: SPI-mode board microSD is enabled in the Linux-capable
LiteX bitstream by default and verified on hardware. Linux enumerates the card as
`/dev/mmcblk0`; an 8 GB SDHC card has a VFAT boot partition and an ext4 rootfs
partition. The SD-root path is verified with `/dev/mmcblk0p2` mounted as `/` and
hostname `litex-sdroot`.

Acceptance:

```bash
dmesg | grep -Ei 'mmc|spi'
cat /proc/partitions
ls -l /dev/mmcblk0 /dev/mmcblk0p1 /dev/mmcblk0p2
cat /proc/cmdline
mount | grep ' / '
```

## Stage 4b: Ethernet / networking

After SD-root, Ethernet is the next useful Linux peripheral because it enables
package/file transfer and later TFTP/NFS boot experiments. Keep the SD-root card
as the known-good rootfs while adding Ethernet, so failures are isolated to the
MAC/PHY/DTS/driver path.

Acceptance:

```bash
dmesg | grep -Ei 'eth|liteeth|mdio|phy'
ip link
ip link set eth0 up
udhcpc -i eth0
ping -c 3 <gateway-ip>
```

## Stage 5: VGA framebuffer

Start with simple framebuffer rather than full GPU:

- framebuffer memory in DDR;
- VGA timing generator;
- Linux `simple-framebuffer` or equivalent handoff.

Acceptance:

```bash
cat /dev/urandom > /dev/fb0
```

## Stage 6: custom RISC-V CPU path

Develop custom CPU separately from the reference Linux path:

1. RV32I bare metal in BRAM.
2. UART printf and GPIO tests.
3. RV32IMAC support.
4. CSR and privileged architecture.
5. trap/exception/interrupt delegation.
6. Sv32 MMU and TLB.
7. CLINT/PLIC integration.
8. OpenSBI boot.
9. Linux S-mode boot.

Acceptance for final custom CPU:

```text
same Linux image and DTS boot on the custom CPU path
```

## Risk management

Do not debug custom CPU, DDR, OpenSBI, Linux kernel, DTS, rootfs, and all peripherals at the same time. Keep a known-good reference SoC path so failures can be isolated.
