#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ ! -d third_party/opensbi/.git ]; then
  echo "Missing third_party/opensbi. Run scripts/bootstrap_linux_on_litex.sh first." >&2
  exit 1
fi

XILINX_RISCV=/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin
if [ -d "$XILINX_RISCV" ]; then
  export PATH="$XILINX_RISCV:$PATH"
fi

if ! command -v riscv64-unknown-elf-gcc >/dev/null 2>&1; then
  echo "Missing riscv64-unknown-elf-gcc in PATH." >&2
  exit 1
fi

make -C third_party/opensbi \
  CROSS_COMPILE=riscv64-unknown-elf- \
  PLATFORM=litex/vexriscv \
  PLATFORM_RISCV_ISA=rv32ima_zicsr_zifencei \
  PLATFORM_RISCV_ABI=ilp32 \
  -j"$(nproc)"

mkdir -p linux/images
cp third_party/opensbi/build/platform/litex/vexriscv/firmware/fw_jump.bin linux/images/opensbi.bin
printf 'OpenSBI image: linux/images/opensbi.bin\n'
ls -l linux/images/opensbi.bin
