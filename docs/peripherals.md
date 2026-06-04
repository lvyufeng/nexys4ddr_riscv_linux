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

### RGB LED and seven-segment status (verified)

The local LiteX target wrapper also exposes the two Nexys4 DDR RGB LEDs and the
seven-segment display pins as simple LiteX `GPIOOut` banks. These are deliberately
plain GPIO controllers for the first milestone; PWM/color mixing and a richer
display driver can be layered on later.

The new CSR locations are pinned after the previously verified GPIO inputs so the
Ethernet, LED, SPI-SD, switch, and button addresses remain stable:

```text
rgb_leds:       CSR 0xf0006000, 6 output lines
seven_seg:      CSR 0xf0006800, 8 output lines
seven_seg_ctrl: CSR 0xf0007000, 8 output lines
```

Linux exposes the three new banks as GPIO character devices in the current
SD-root boot:

```text
/dev/gpiochip3  litex_gpio  6 lines  rgb_leds
/dev/gpiochip4  litex_gpio  8 lines  seven_seg segments
/dev/gpiochip5  litex_gpio  8 lines  seven_seg digit enables
```

RGB line order in the first GPIO bank is:

```text
bit 0: RGB LED0 red
bit 1: RGB LED0 green
bit 2: RGB LED0 blue
bit 3: RGB LED1 red
bit 4: RGB LED1 green
bit 5: RGB LED1 blue
```

The seven-segment digit-enable pins on Nexys4 DDR are active-low. The hardware
reset value for `seven_seg_ctrl` is `0xff` so all digits stay off until Linux
drives them. To show a pattern, write the segment mask first through
`/dev/gpiochip4`, then drive one digit-enable bit low through `/dev/gpiochip5`.

A small GPIO character-UAPI helper is kept in `tools/gpio_output_set.c`; build it
for the Buildroot RISC-V userspace and copy it to the board when `gpioset` is not
available in the running SD-root image:

```bash
third_party/buildroot/output/host/bin/riscv32-buildroot-linux-gnu-gcc.br_real \
  -O2 -Wall -Wextra -o build/test-tools/gpio_output_set tools/gpio_output_set.c
```

Hardware smoke test over SSH passed with the new display GPIO bitstream and
SD-root DTB:

```text
GPIO_CHIP path=/dev/gpiochip3 name=gpiochip3 label=litex_gpio lines=6
GPIO_OUTPUT_SET path=/dev/gpiochip3 lines=6 mask=0x1 hold_ms=2000
GPIO_OUTPUT_SET_OK
...
GPIO_OUTPUT_SET path=/dev/gpiochip3 lines=6 mask=0x20 hold_ms=2000
GPIO_OUTPUT_SET_OK

GPIO_CHIP path=/dev/gpiochip4 name=gpiochip4 label=litex_gpio lines=8
GPIO_OUTPUT_SET path=/dev/gpiochip4 lines=8 mask=0x3f hold_ms=300
GPIO_OUTPUT_SET_OK
GPIO_CHIP path=/dev/gpiochip5 name=gpiochip5 label=litex_gpio lines=8
GPIO_OUTPUT_SET path=/dev/gpiochip5 lines=8 mask=0xfe hold_ms=1000
GPIO_OUTPUT_SET_OK
...
GPIO_OUTPUT_SET path=/dev/gpiochip5 lines=8 mask=0xff hold_ms=500
GPIO_OUTPUT_SET_OK
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

### VGA framebuffer status (verified at 640x480@60Hz)

The local LiteX target wrapper keeps VGA opt-in and makes the timing preset
configurable. This avoids editing the ignored upstream LiteX-Boards checkout and
works around the upstream Nexys4 DDR target's fixed 40 MHz / `800x600@60Hz`
video setup.

Build the conservative verified mode with:

```bash
LITEX_WITH_VIDEO_FRAMEBUFFER=1 \
LITEX_VIDEO_TIMING='640x480@60Hz' \
LITEX_SYS_CLK_FREQ=60e6 \
./scripts/build_litex_nexys4ddr_linux.sh build/litex_nexys4ddr_linux_vga_fb_640x480_60mhz
```

The hardware-verified build completed with routed timing met:

```text
bitstream: build/litex_nexys4ddr_linux_vga_fb_640x480_60mhz/gateware/digilent_nexys4ddr.bit
WNS(ns):   0.002
VGA clock: 25.087 MHz actual, for LiteX `640x480@60Hz` timing
```

Generated video metadata for the verified build:

```text
framebuffer memory: 0x47e00000, size 0x0012c000
format:             a8b8g8r8
width/height:       640x480
stride:             2560

video_framebuffer CSR base:     0xf0007800
video_framebuffer_vtg CSR base: 0xf0008000
```

The first hardware-visible smoke test was deliberately done directly from the
LiteX BIOS, before relying on Linux simple-framebuffer. This proves the physical
VGA chain and LiteX video core independently of Linux userspace:

```bash
./scripts/program_litex_nexys4ddr.sh \
  build/litex_nexys4ddr_linux_vga_fb_640x480_60mhz/gateware/digilent_nexys4ddr.bit

./scripts/vga_bios_test_640x480.py --mode white
./scripts/vga_bios_test_640x480.py --mode bars
```

The BIOS helper writes the framebuffer in DDR and programs these 640x480 timing
CSRs:

```text
VTG hres=640, hsync_start=656, hsync_end=752, hscan=800
VTG vres=480, vsync_start=490, vsync_end=492, vscan=525
DMA base=0x47e00000, length=0x0012c000, loop=1, enable=1
VTG enable=1
```

Observed hardware result:

```text
white screen visible on VGA monitor
horizontal color bars visible on VGA monitor
DMA offset CSR changes between reads, confirming the DMA is running
```

Important bring-up note: the test monitor/USB setup was sensitive to display or
cable power events. If the Digilent FTDI interface re-enumerates and Vivado
reports the Artix-7 `DONE status = 0`, the FPGA SRAM configuration was lost;
reprogram the bitstream before rerunning VGA tests. Turning the monitor on/off
can therefore look like a VGA failure when it is actually a board/USB/power
stability issue.

Linux integration status:

- The generated VGA SD-root DTS exposes a `simple-framebuffer` node with the
  correct 640x480 geometry.
- Linux `simplefb` can map `/dev/fb0`, but simple-framebuffer by itself does not
  enable the LiteX video DMA/VTG; userspace or a real driver must program those
  CSRs.
- Next display milestone: add an automatic Linux-side enable path, then layer a
  framebuffer console/login or a minimal GUI on top.

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
