# Toolchain assessment and bootstrap

Local status checked during Stage 0:

```text
Python 3.10.10: available
Vivado 2025.2: available
LiteX / Migen / LiteDRAM: installed locally by `scripts/bootstrap_litex.sh`
LiteX board target: `litex_boards.targets.digilent_nexys4ddr` probe succeeds
RISC-V cross compiler: Vivado-bundled `riscv64-unknown-elf-gcc` found at `/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin`
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
- Meson/Ninja for LiteX generated software builds
- pyserial for UART smoke tests
- LiteX
- Migen
- LiteDRAM
- LiteEth, required by the upstream Nexys4 DDR target import path
- LiteSDCard, required for the target's optional SDCard support
- LiteX boards
- `pythondata-cpu-vexriscv`
- `pythondata-cpu-vexriscv_smp` for Linux/OpenSBI-oriented VexRiscvSMP builds
- `pythondata-software-picolibc`
- `pythondata-software-compiler_rt`

### Firmware and Linux

- RISC-V GCC toolchain. Vivado 2025.2 provides `riscv64-unknown-elf-gcc` under `/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin`, which is enough to start LiteX BIOS/firmware builds. A Linux-capable cross toolchain from Buildroot will still be needed for the kernel/rootfs path.
- OpenSBI source tree.
- Linux kernel source tree.
- Buildroot source tree.

## Recommended local layout

Do not vendor large upstream repositories into the main git history unless needed. Use `third_party/` as a local ignored workspace:

```text
third_party/
  migen/
  litex/
  litedram/
  liteeth/
  litesdcard/
  litex-boards/
  pythondata-cpu-vexriscv/
  pythondata-cpu-vexriscv_smp/
  pythondata-software-picolibc/
  pythondata-software-compiler_rt/
  opensbi/
  linux/
  buildroot/
```

`third_party/` is ignored by `.gitignore`; scripts should recreate or point to it.

## Bootstrap direction

The first bootstrap script should:

1. create a Python virtual environment under `.venv/`;
2. clone/install LiteX dependencies into `third_party/`;
3. recursively initialize upstream submodules such as `pythondata-software-picolibc/data`;
4. verify `litex-boards` can see a Nexys4 DDR/Nexys A7-compatible target;
5. separately fetch/build OpenSBI/Linux/Buildroot once the reference SoC target is known.

## Verification commands

```bash
python3 --version
vivado -version
./scripts/bootstrap_litex.sh
./scripts/check_toolchain.sh
./scripts/probe_litex_nexys4ddr.sh
./scripts/build_litex_nexys4ddr.sh
riscv64-unknown-elf-gcc --version
```
