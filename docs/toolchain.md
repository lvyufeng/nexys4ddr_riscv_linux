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

### Pinned upstream revisions

`scripts/bootstrap_litex.sh` checks out a fixed revision for each dependency,
because the local target wraps the upstream Nexys4 DDR board target and overrides
parts of its API (`litex_targets/nexys4ddr_linux.py` monkey-patches the upstream
`_CRG` clocking class). Tracking upstream HEAD would let a refactor silently move
CSRs or change that API while every build still appears to succeed.

These are the revisions the current bitstreams and device trees were verified
against:

```text
migen                            e19524c963a8342952840983047557707fbe0b6a
litex                            11f94eaa6cc5c2c401cca386c080ce92001490a7
litedram                         8bc71e8d006de7c83f01391b37633f270ecbae81
liteeth                          28b449364e98355cbf319de3fcb9ab61d012c609
litesdcard                       c48e76d0bcd8c079c0f24465ca1c0cf0cd1dbb3d
litex-boards                     9112df9ec881588df6b2c7f1064b55a7b32cc118
pythondata-cpu-vexriscv          642ecfed1c84460555d6d803d660cc60cfc1ecb6
pythondata-cpu-vexriscv_smp      217d23d7e9ad5556c17a73dc6ffc1971765f3d7c
pythondata-software-picolibc     9264d9771ae37b4d39d8fbe336aafef1f34c3e48
pythondata-software-compiler_rt  6eb76609c9627bf26635e57c63fb22cda7115887
```

To update a dependency, change its SHA in `LITEX_DEPS` in
`scripts/bootstrap_litex.sh`, then rebuild and re-verify. Set `LITEX_UNPIN=1` to
track upstream HEADs for experimentation.

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

## CSR/device-tree consistency check

LiteX CSR slots are pinned by number in `litex_targets/nexys4ddr_linux.py`, so a
stale `csr.json` or an upstream change can relocate a peripheral while builds
still succeed. `tools/check_csr_dts_consistency.py` compares a generated DTS (or
DTB) against its `csr.json` and fails on any base-address, register-window, or
node-form mismatch. Both the build and probe scripts run it automatically; it can
also be run by hand, which needs neither Vivado nor a bitstream rebuild (metadata
regeneration uses `--no-compile`):

```bash
./scripts/probe_litex_nexys4ddr_linux.sh build/check_meta
python3 tools/check_csr_dts_consistency.py \
  build/check_meta/csr.json build/check_meta/digilent_nexys4ddr_linux.dts
```
