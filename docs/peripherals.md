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

### User LED status (verified)

The LiteX `LedChaser` drives all 16 Nexys4 DDR user LEDs, exposed as a single
`litex,gpio` output controller. `litex_json2dts` defaults `litex,ngpio` to 4 when
the CSR JSON has no `leds_ngpio` constant, so the build/probe wrappers now patch
the generated `&leds` node to 16 (override with `LITEX_LEDS_NGPIO`). The
checked-in DTS files match.

Linux exposes the LEDs through the GPIO character device, not the legacy
`/sys/class/gpio` sysfs interface:

```text
/dev/gpiochip0
/sys/devices/platform/soc/f0003800.gpio
driver: litex-gpio
litex,ngpio = <16>  (0x10)
```

Hardware smoke test from the SD-root shell drove all 16 lines through a chaser
plus `0xffff`/`0xaaaa`/`0x5555` patterns:

```text
GPIO_CHIP name=gpiochip0 label=litex_gpio lines=16
LED_PATTERN=0x0001 ... 0x8000
LED_PATTERN=0xffff / 0xaaaa / 0x5555
LED_GPIO_TEST_OK
```

The Buildroot image now installs the `libgpiod` tools, so the LEDs can also be
driven directly over SSH, for example:

```bash
gpioinfo gpiochip0
gpioset gpiochip0 0=1 1=0 2=1 ...
```

### User switch/button status (verified)

The checked-in local LiteX target wrapper instantiates the Nexys4 DDR board
switches and push buttons as LiteX `GPIOIn` controllers, avoiding edits to the
ignored upstream `third_party/litex-boards` checkout. Their CSR locations are
pinned after the already-verified peripherals so the Ethernet, LED, and SPI-SD
address contract remains stable:

```text
switches:  CSR 0xf0005000, IRQ 4, 16 input lines
buttons:   CSR 0xf0005800, IRQ 5, 5 input lines
```

Linux exposes them through additional GPIO character devices:

```text
/dev/gpiochip1  litex_gpio  16 lines  switches
/dev/gpiochip2  litex_gpio   5 lines  buttons
/sys/bus/platform/drivers/litex-gpio/f0005000.gpio
/sys/bus/platform/drivers/litex-gpio/f0005800.gpio
```

Hardware/static smoke test from the SD-root shell passed with a GPIO character
UAPI test binary:

```text
GPIO_CHIP path=/dev/gpiochip1 name=gpiochip1 label=litex_gpio lines=16
GPIO_CHIP path=/dev/gpiochip2 name=gpiochip2 label=litex_gpio lines=5
SWITCHES mask=0x8000
BUTTONS  mask=0x00
GPIO_INPUT_PROBE_OK
```

For a live dynamic check, run a short watcher and flip switches / press buttons:

```bash
/tmp/gpio_input_probe watch 60
# prints CHANGE switches=0x.... buttons=0x.. when values change
```

## Storage / SPI-class peripherals

Candidate devices:

- microSD, SPI mode first for simplicity;
- accelerometer, depending on board wiring;
- temperature sensor, depending on board wiring;
- Pmod SPI/I2C devices.

Current verified storage status:

- the Linux-capable LiteX build script enables the board microSD slot with
  `--with-spi-sdcard` by default;
- the generated/local Ethernet-enabled DTS exposes `spi@f0004800` with
  `compatible = "litex,litespi"` and an `mmc-spi-slot` child;
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

Ethernet is now enabled with LiteX's Nexys4 DDR RMII Ethernet option and verified
on hardware while keeping the SD-root card as the root filesystem.

Current Ethernet metadata:

```text
LiteEth MAC CSR:  f0002000
LiteEth MDIO CSR: f0002800
LiteEth buffer:   80000000..80001fff
LiteEth IRQ:      3 in LiteX metadata, mapped by Linux as irq 13
SPI-SD CSR moved: f0004800
```

Hardware smoke test:

```bash
dmesg | grep -Ei 'eth|liteeth|mdio|phy'
ip link
ip link set eth0 up
udhcpc -i eth0
ip addr show eth0
ping -c 3 192.168.1.1
```

Observed result:

```text
liteeth f0002000.mac eth0: irq 13 slots: tx 2 rx 2 size 2048
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
udhcpc: lease of 192.168.1.223 obtained from 192.168.1.1
3 packets transmitted, 3 packets received, 0% packet loss
```

Dropbear is also enabled in the Buildroot image. With the default lab password
`root`, host-side SSH verification passed:

```bash
ssh root@192.168.1.223 hostname
# -> litex-sdroot
```

The DHCP address can change on later boots. After basic `eth0` works, TFTP/NFS
boot can be considered as a separate boot-media milestone.
