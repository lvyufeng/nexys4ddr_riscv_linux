# Nexys4 DDR board baseline

Target board: Digilent Nexys4 DDR / Artix-7 `xc7a100tcsg324-1`.

This directory contains the board files imported from the verified `step_into_mips` Lab 10 hardware flow:

```text
nexys4ddr.xdc              baseline clock/reset/UART/LED constraints
mig/nexys4ddr_mig.prj      MIG 7-series DDR2 project file
```

## Initial board resources for Linux bring-up

- 100 MHz board clock on `clk100mhz`.
- Center button reset on `rst`.
- USB-UART console:
  - FPGA RX input: `uart_rx_i`
  - FPGA TX output: `uart_tx_o`
  - host device usually `/dev/ttyUSB1`
  - baud/config: `115200 8N1`
- 16 user LEDs on `led[15:0]`.
- DDR2, 128 MiB, through MIG 7-series.

## Notes

The current XDC intentionally starts with only the resources needed by the first bring-up stages: clock, reset, UART, and LEDs. Additional Nexys4 DDR peripherals should be added as they are implemented and verified.

The MIG project file is copied from a working Nexys4 DDR configuration. Stage 1 should instantiate a generated MIG IP from this `.prj`, then connect the RISC-V Linux SoC DDR port to the MIG user/AXI interface.

## Reference provenance

These files were imported from the completed `step_into_mips` Lab 10 flow, which already verified:

- true MIG DDR2 bitstream generation;
- routed timing met on `xc7a100tcsg324-1`;
- JTAG programming with startup status HIGH;
- UART console at `/dev/ttyUSB1`, `115200 8N1`.
