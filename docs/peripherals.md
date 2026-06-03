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

Next storage steps:

- prepare a dedicated SD-card partition layout on the host PC;
- copy a rootfs or boot payloads to SD;
- update bootargs / boot flow so large rootfs data no longer has to be
  uploaded over serial.

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

Do not implement from scratch in the first phases. If needed, prefer an existing LiteX/third-party MAC or controller with Linux driver support.
