# Nexys4 DDR board notes

Target board: Digilent Nexys4 DDR / Artix-7 `xc7a100tcsg324-1`.

Initial board resources for Linux bring-up:

- 100 MHz system clock
- DDR2, 128 MiB, through MIG 7-series
- USB-UART console, typically `/dev/ttyUSB1`, `115200 8N1`
- user LEDs/buttons/switches for later GPIO enablement

The proven `step_into_mips` Lab 9/Lab 10 flow should be used as reference for:

- XDC pin constraints;
- MIG project settings;
- JTAG programming flow;
- UART capture/verification habits.

The actual Linux SoC constraints and MIG project will be kept in this directory once copied/adapted.
