#!/usr/bin/env bash
set -euo pipefail

echo "== Python =="
python3 --version

echo "== Vivado =="
if command -v vivado >/dev/null 2>&1; then
  vivado -version | head -1
else
  echo "vivado not found in PATH; source Vivado settings64.sh first"
fi

echo "== Python packages =="
python3 - <<'PY'
mods = ["migen", "litex", "litedram", "litex_boards"]
for mod in mods:
    try:
        m = __import__(mod)
        print(f"{mod}: {getattr(m, '__file__', 'ok')}")
    except Exception as e:
        print(f"{mod}: missing ({e})")
PY

echo "== RISC-V compilers =="
for cc in riscv64-unknown-elf-gcc riscv64-linux-gnu-gcc riscv32-unknown-elf-gcc riscv32-linux-gnu-gcc; do
  if command -v "$cc" >/dev/null 2>&1; then
    echo "$cc: $($cc --version | head -1)"
  else
    echo "$cc: missing"
  fi
done
