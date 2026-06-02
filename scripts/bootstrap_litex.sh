#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
THIRD_PARTY="$ROOT_DIR/third_party"
VENV="$ROOT_DIR/.venv"

mkdir -p "$THIRD_PARTY"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel meson ninja pyserial

clone_or_update() {
  local url=$1
  local dir=$2
  if [ -d "$dir/.git" ]; then
    git -C "$dir" pull --ff-only
  else
    git clone "$url" "$dir"
  fi
  git -C "$dir" submodule update --init --recursive
}

clone_or_update https://github.com/m-labs/migen.git "$THIRD_PARTY/migen"
clone_or_update https://github.com/enjoy-digital/litex.git "$THIRD_PARTY/litex"
clone_or_update https://github.com/enjoy-digital/litedram.git "$THIRD_PARTY/litedram"
clone_or_update https://github.com/enjoy-digital/liteeth.git "$THIRD_PARTY/liteeth"
clone_or_update https://github.com/enjoy-digital/litesdcard.git "$THIRD_PARTY/litesdcard"
clone_or_update https://github.com/litex-hub/litex-boards.git "$THIRD_PARTY/litex-boards"
clone_or_update https://github.com/litex-hub/pythondata-cpu-vexriscv.git "$THIRD_PARTY/pythondata-cpu-vexriscv"
clone_or_update https://github.com/litex-hub/pythondata-cpu-vexriscv_smp.git "$THIRD_PARTY/pythondata-cpu-vexriscv_smp"
clone_or_update https://github.com/litex-hub/pythondata-software-picolibc.git "$THIRD_PARTY/pythondata-software-picolibc"
clone_or_update https://github.com/litex-hub/pythondata-software-compiler_rt.git "$THIRD_PARTY/pythondata-software-compiler_rt"

python3 -m pip install -e "$THIRD_PARTY/migen"
python3 -m pip install -e "$THIRD_PARTY/litex"
python3 -m pip install -e "$THIRD_PARTY/litedram"
python3 -m pip install -e "$THIRD_PARTY/liteeth"
python3 -m pip install -e "$THIRD_PARTY/litesdcard"
python3 -m pip install -e "$THIRD_PARTY/litex-boards"
python3 -m pip install -e "$THIRD_PARTY/pythondata-cpu-vexriscv"
python3 -m pip install -e "$THIRD_PARTY/pythondata-cpu-vexriscv_smp"
python3 -m pip install -e "$THIRD_PARTY/pythondata-software-picolibc"
python3 -m pip install -e "$THIRD_PARTY/pythondata-software-compiler_rt"

python3 - <<'PY'
import migen, litex, litedram, liteeth, litesdcard, litex_boards, pythondata_cpu_vexriscv, pythondata_cpu_vexriscv_smp, pythondata_software_picolibc, pythondata_software_compiler_rt
print("LiteX Python packages installed")
print("migen:", migen.__file__)
print("litex:", litex.__file__)
print("litedram:", litedram.__file__)
print("liteeth:", liteeth.__file__)
print("litesdcard:", litesdcard.__file__)
print("litex_boards:", litex_boards.__file__)
print("pythondata_cpu_vexriscv:", pythondata_cpu_vexriscv.__file__)
print("pythondata_cpu_vexriscv_smp:", pythondata_cpu_vexriscv_smp.__file__)
print("pythondata_software_picolibc:", pythondata_software_picolibc.__file__)
print("pythondata_software_compiler_rt:", pythondata_software_compiler_rt.__file__)
PY

printf '\nNext: inspect available Nexys targets, for example:\n'
printf '  source .venv/bin/activate\n'
printf '  python3 -m litex_boards.targets.digilent_nexys4ddr --help\n'
printf 'or search third_party/litex-boards/litex_boards/targets for nexys*.py\n'
