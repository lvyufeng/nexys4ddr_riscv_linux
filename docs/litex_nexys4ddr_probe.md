# LiteX Nexys4 DDR target probe

LiteX already provides a Nexys4 DDR target:

```text
litex_boards.targets.digilent_nexys4ddr
litex_boards.platforms.digilent_nexys4ddr
```

The target includes board resources for:

- 100 MHz clock;
- reset;
- UART;
- LEDs, RGB LEDs, switches, buttons, 7-segment;
- DDR2 via LiteDRAM `A7DDRPHY` and `MT47H64M16`;
- RMII Ethernet;
- SDCard / SPI SDCard;
- VGA;
- accelerometer, temperature sensor, microphone, audio, PS/2, PMODs.

## Probe command

After running `scripts/bootstrap_litex.sh`:

```bash
./scripts/probe_litex_nexys4ddr.sh
```

This runs the LiteX target with `--build --no-compile`, which generates SoC metadata and gateware files without invoking Vivado or compiling firmware.

Generated outputs include:

```text
build/litex_nexys4ddr_probe/csr.csv
build/litex_nexys4ddr_probe/csr.json
build/litex_nexys4ddr_probe/memory.x
build/litex_nexys4ddr_probe/gateware/digilent_nexys4ddr.v
build/litex_nexys4ddr_probe/gateware/digilent_nexys4ddr.xdc
```

## Current default map from the probe

Default LiteX regions observed in the probe:

```text
rom      @ 0x00000000, 128 KiB
sram     @ 0x10000000, 8 KiB
main_ram @ 0x40000000, 128 MiB DDR2
csr      @ 0xf0000000, 64 KiB
```

The default target also creates an uncached CPU I/O region at `0x80000000..0xffffffff`, UART IRQ 0, and timer IRQ 1.

For Linux, we will likely override or adapt the final map so DDR appears at the conventional RISC-V Linux base `0x80000000`, unless the LiteX Linux flow being used expects its own generated layout.

## Full build command

```bash
./scripts/build_litex_nexys4ddr.sh
```

The build script sources Vivado 2025.2 when available and adds Vivado's bundled RISC-V compiler directory:

```text
/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin
```

LiteX software generation also requires Meson/Ninja and initialized `pythondata-*` submodules, especially `pythondata-software-picolibc/data`; `scripts/bootstrap_litex.sh` handles these dependencies.

## Program command

After a successful full build and with the Nexys4 DDR connected over JTAG:

```bash
./scripts/program_litex_nexys4ddr.sh
```

Expected marker:

```text
LITEX_PROGRAMMED=xc7a100t_0 BITSTREAM=...
```

The first LiteX bitstream was programmed successfully on the lab Nexys4 DDR board with startup status HIGH.

## UART smoke test

The default LiteX BIOS console uses USB-UART at 115200 baud. The host device is typically `/dev/ttyUSB1` on the current lab machine.

```bash
.venv/bin/python3 scripts/smoke_litex_uart.py /dev/ttyUSB1
```

Observed marker after programming the minimal reference bitstream:

```text
litex>
LITEX_UART_SMOKE_OK
```

This verifies the Stage 1 minimum reference SoC reaches the LiteX BIOS prompt over UART. The next milestone is to replace/extend the BIOS-only flow with OpenSBI + Linux kernel + initramfs.
