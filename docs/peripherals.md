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

- microSD, likely SPI mode first for simplicity
- accelerometer, depending on board wiring
- temperature sensor, depending on board wiring
- Pmod SPI/I2C devices

Preferred approach:

- start with one simple SPI master;
- validate loopback or a known SPI device;
- add device tree nodes one at a time.

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
