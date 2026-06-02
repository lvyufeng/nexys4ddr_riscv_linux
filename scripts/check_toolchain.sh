#!/usr/bin/env bash
set -euo pipefail

echo "== Python =="
python3 --version
if [ -x .venv/bin/python3 ]; then
  VENV_PY=.venv/bin/python3
  echo "venv python: $($VENV_PY --version)"
else
  VENV_PY=python3
  echo "venv python: missing; run scripts/bootstrap_litex.sh for LiteX packages"
fi

echo "== Vivado =="
if command -v vivado >/dev/null 2>&1; then
  vivado -version | head -1
else
  echo "vivado not found in PATH; source Vivado settings64.sh first"
fi

echo "== Python packages =="
"$VENV_PY" - <<'PY'
mods = ["serial", "mesonbuild", "migen", "litex", "litedram", "liteeth", "litesdcard", "litex_boards", "pythondata_cpu_vexriscv", "pythondata_software_picolibc", "pythondata_software_compiler_rt"]
for mod in mods:
    try:
        m = __import__(mod)
        print(f"{mod}: {getattr(m, '__file__', 'ok')}")
    except Exception as e:
        print(f"{mod}: missing ({e})")
PY

echo "== RISC-V compilers =="
XILINX_RISCV=/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin
if [ -d "$XILINX_RISCV" ]; then
  echo "Vivado bundled RISC-V bin: $XILINX_RISCV"
  export PATH="$XILINX_RISCV:$PATH"
fi
for cc in riscv64-unknown-elf-gcc riscv64-linux-gnu-gcc riscv32-unknown-elf-gcc riscv32-linux-gnu-gcc; do
  if command -v "$cc" >/dev/null 2>&1; then
    echo "$cc: $($cc --version | head -1)"
  else
    echo "$cc: missing"
  fi
done
