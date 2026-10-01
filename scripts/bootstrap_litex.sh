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

# Upstream revisions this project was verified against. third_party/ is
# gitignored, so without pinning, bootstrap would silently pick up new upstream
# commits that can change CSR placement or the Board/SoC API the local target
# relies on (litex_targets/nexys4ddr_linux.py wraps the upstream Nexys4 DDR
# target and even overrides its _CRG clocking class). Update these deliberately,
# together with a full rebuild, not incidentally. Set LITEX_UNPIN=1 to track
# upstream HEADs for experimentation.
LITEX_DEPS=(
  "migen|https://github.com/m-labs/migen.git|e19524c963a8342952840983047557707fbe0b6a"
  "litex|https://github.com/enjoy-digital/litex.git|11f94eaa6cc5c2c401cca386c080ce92001490a7"
  "litedram|https://github.com/enjoy-digital/litedram.git|8bc71e8d006de7c83f01391b37633f270ecbae81"
  "liteeth|https://github.com/enjoy-digital/liteeth.git|28b449364e98355cbf319de3fcb9ab61d012c609"
  "litesdcard|https://github.com/enjoy-digital/litesdcard.git|c48e76d0bcd8c079c0f24465ca1c0cf0cd1dbb3d"
  "litex-boards|https://github.com/litex-hub/litex-boards.git|9112df9ec881588df6b2c7f1064b55a7b32cc118"
  "pythondata-cpu-vexriscv|https://github.com/litex-hub/pythondata-cpu-vexriscv.git|642ecfed1c84460555d6d803d660cc60cfc1ecb6"
  "pythondata-cpu-vexriscv_smp|https://github.com/litex-hub/pythondata-cpu-vexriscv_smp.git|217d23d7e9ad5556c17a73dc6ffc1971765f3d7c"
  "pythondata-software-picolibc|https://github.com/litex-hub/pythondata-software-picolibc.git|9264d9771ae37b4d39d8fbe336aafef1f34c3e48"
  "pythondata-software-compiler_rt|https://github.com/litex-hub/pythondata-software-compiler_rt.git|6eb76609c9627bf26635e57c63fb22cda7115887"
)

clone_or_update() {
  local name=$1
  local url=$2
  local rev=$3
  local dir="$THIRD_PARTY/$name"
  if [ -d "$dir/.git" ]; then
    git -C "$dir" fetch --all --tags --quiet
  else
    git clone "$url" "$dir"
  fi
  if [ "${LITEX_UNPIN:-0}" = "1" ]; then
    echo "LITEX_UNPIN=1: tracking upstream HEAD for $name"
  else
    git -C "$dir" checkout --quiet "$rev"
  fi
  git -C "$dir" submodule update --init --recursive
}

for dep in "${LITEX_DEPS[@]}"; do
  IFS='|' read -r _name _url _rev <<< "$dep"
  clone_or_update "$_name" "$_url" "$_rev"
done

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
