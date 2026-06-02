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
python3 -m pip install --upgrade pip setuptools wheel

clone_or_update() {
  local url=$1
  local dir=$2
  if [ -d "$dir/.git" ]; then
    git -C "$dir" pull --ff-only
  else
    git clone "$url" "$dir"
  fi
}

clone_or_update https://github.com/enjoy-digital/migen.git "$THIRD_PARTY/migen"
clone_or_update https://github.com/enjoy-digital/litex.git "$THIRD_PARTY/litex"
clone_or_update https://github.com/enjoy-digital/litedram.git "$THIRD_PARTY/litedram"
clone_or_update https://github.com/litex-hub/litex-boards.git "$THIRD_PARTY/litex-boards"

python3 -m pip install -e "$THIRD_PARTY/migen"
python3 -m pip install -e "$THIRD_PARTY/litex"
python3 -m pip install -e "$THIRD_PARTY/litedram"
python3 -m pip install -e "$THIRD_PARTY/litex-boards"

python3 - <<'PY'
import migen, litex, litedram, litex_boards
print("LiteX Python packages installed")
print("migen:", migen.__file__)
print("litex:", litex.__file__)
print("litedram:", litedram.__file__)
print("litex_boards:", litex_boards.__file__)
PY

printf '\nNext: inspect available Nexys targets, for example:\n'
printf '  source .venv/bin/activate\n'
printf '  python3 -m litex_boards.targets.digilent_nexys4ddr --help\n'
printf 'or search third_party/litex-boards/litex_boards/targets for nexys*.py\n'
