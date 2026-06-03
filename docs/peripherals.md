# Nexys4 DDR peripheral enablement roadmap

The first Linux milestone only needs DDR, UART, timer, and interrupt controller. Other peripherals should be enabled in staged Linux-friendly groups.

## Baseline required for Linux

- DDR2 MIG backend
- UART console
- CLINT/ACLINT timer
- PLIC external interrupt controller
- boot ROM / firmware loader

## GPIO-class peripherals

Candidate devices:

- user LEDs
- switches
- push buttons
- RGB LEDs
- 7-segment display

Preferred Linux exposure:

- LEDs: `gpio-leds`
- buttons: `gpio-keys`
- switches: GPIO inputs, readable through libgpiod
- 7-segment: initially simple MMIO or GPIO mapping, later a proper driver if needed

## Storage / SPI-class peripherals

Candidate devices:

- microSD, SPI mode first for simplicity;
- accelerometer, depending on board wiring;
- temperature sensor, depending on board wiring;
- Pmod SPI/I2C devices.

Current verified storage status:

- the Linux-capable LiteX build script enables the board microSD slot with
  `--with-spi-sdcard` by default;
- the generated/local DTS exposes `spi@f0003800` with `compatible =
  "litex,litespi"` and an `mmc-spi-slot` child;
- Linux has `CONFIG_SPI_LITESPI=y`, `CONFIG_MMC_SPI=y`, and block filesystem
  support for ext2/3/4 plus VFAT/MS-DOS;
- hardware smoke test with an 8 GB SDHC card reached:

```text
mmc_spi spi0.0: SD/MMC host mmc0, no WP, no poweroff, cd polling
mmc0: new SDHC card on SPI
mmcblk0: mmc0:0000 SL08G 7.40 GiB
 mmcblk0: p1
```

Read-only VFAT mount test:

```bash
mkdir -p /mnt/sd
mount -o ro /dev/mmcblk0p1 /mnt/sd
mount | grep mmc
umount /mnt/sd
```

The card is now also prepared as a two-partition Linux rootfs card:

```text
/dev/mmcblk0p1  VFAT  LITEXBOOT   boot payload copy
/dev/mmcblk0p2  ext4  LITEXROOT   Buildroot rootfs
```

SD-root boot is verified with `rv32_sdroot.dtb`:

```text
Kernel command line: console=liteuart earlycon=liteuart,0xf0001000 rootwait root=/dev/mmcblk0p2 rootfstype=ext4 rw
/dev/root on / type ext4 (rw,relatime)
hostname: litex-sdroot
```

The serial loader now only uploads `Image`, `rv32_sdroot.dtb`, and `opensbi.bin`
for this path; the rootfs data is read from SD.

Next storage steps:

- optionally copy future kernel/DTB/OpenSBI artifacts from `/dev/mmcblk0p1`
  instead of serial-uploading them;
- consider native 4-bit SD mode later if SPI-mode throughput becomes a blocker.

## Display

Use simple framebuffer first:

- VGA timing generator in RTL;
- framebuffer stored in DDR;
- Linux `simple-framebuffer` binding.

Avoid complex GPU/display acceleration in the first pass.

## Audio and microphone

Treat these as later work:

- PWM audio output can be a simple RTL peripheral first;
- PDM microphone needs sampling, filtering, buffering, and likely DMA for Linux usability.

## USB / Ethernet

Do not implement from scratch in the first phases. Prefer an existing LiteX MAC or
third-party controller with Linux driver support.

Recommended Ethernet bring-up after SD-root:

1. Use LiteX's Nexys4 DDR Ethernet option for the board PHY if available, and
   regenerate the Linux metadata (`csr.json`/DTS) with Ethernet enabled.
2. Confirm the generated CSR base, interrupt, PHY reset/MDIO wiring, and DTS node.
3. Enable the matching Linux network driver in `linux/configs/litex_nexys4ddr_linux.config`.
4. Rebuild the bitstream and kernel, then boot from the already-working SD-root
   path so networking is debugged independently of rootfs upload.
5. Hardware smoke tests:

```bash
dmesg | grep -Ei 'eth|liteeth|mdio|phy'
ip link
ip link set eth0 up
udhcpc -i eth0
ping -c 3 <gateway-ip>
```

After basic `eth0` works, TFTP/NFS boot can be considered as a separate boot-media milestone.
