# Toolchain assessment and bootstrap

Local status checked during Stage 0:

```text
Python 3.10.10: available
Vivado 2025.2: available
LiteX / Migen / LiteDRAM: not installed yet
RISC-V cross compiler: not found in PATH yet
OpenSBI source/toolchain: not installed yet
Buildroot source/config: not installed yet
```

## Selected Stage 1 reference path

Use **LiteX + VexRiscv/VexRiscvSMP** as the first reference Linux-capable SoC path.

Rationale:

- It has a mature FPGA SoC build flow.
- It can generate Linux-friendly CSR, memory map, and device tree data.
- It supports RISC-V Linux reference designs with OpenSBI/Buildroot flows.
- It lets this project validate Nexys4 DDR, UART, timer/interrupt, Linux kernel, and rootfs before attempting a custom CPU with MMU.

## Required tool groups

### FPGA / SoC generation

- Vivado 2025.2
- Python virtual environment
- LiteX
- Migen
- LiteDRAM
- LiteEth / LiteScope optional later
- LiteX boards

### Firmware and Linux

- RISC-V GCC toolchain, preferably `riscv64-unknown-elf-gcc` for firmware/OpenSBI and/or a Linux-capable cross toolchain from Buildroot.
- OpenSBI source tree.
- Linux kernel source tree.
- Buildroot source tree.

## Recommended local layout

Do not vendor large upstream repositories into the main git history unless needed. Use `third_party/` as a local ignored workspace:

```text
third_party/
  litex/
  migen/
  litedram/
  litex-boards/
  opensbi/
  linux/
  buildroot/
```

`third_party/` is ignored by `.gitignore`; scripts should recreate or point to it.

## Bootstrap direction

The first bootstrap script should:

1. create a Python virtual environment under `.venv/`;
2. clone/install LiteX dependencies into `third_party/`;
3. verify `litex-boards` can see a Nexys4 DDR/Nexys A7-compatible target;
4. separately fetch/build OpenSBI/Linux/Buildroot once the reference SoC target is known.

## Verification commands

```bash
python3 --version
vivado -version
python3 -c 'import litex, migen, litedram; print("litex ok")'
riscv64-unknown-elf-gcc --version
```
