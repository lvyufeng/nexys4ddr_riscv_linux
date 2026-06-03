#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

THIRD_PARTY="$ROOT_DIR/third_party"
mkdir -p "$THIRD_PARTY"

clone_or_update() {
  local url=$1
  local dir=$2
  local branch=${3:-}
  if [ -d "$dir/.git" ]; then
    git -C "$dir" fetch --all --tags
    if [ -n "$branch" ]; then
      git -C "$dir" checkout "$branch"
      git -C "$dir" pull --ff-only origin "$branch"
    else
      git -C "$dir" pull --ff-only
    fi
  else
    if [ -n "$branch" ]; then
      git clone --branch "$branch" "$url" "$dir"
    else
      git clone "$url" "$dir"
    fi
  fi
  git -C "$dir" submodule update --init --recursive
}

clone_or_update https://github.com/litex-hub/linux-on-litex-vexriscv.git "$THIRD_PARTY/linux-on-litex-vexriscv"
clone_or_update https://github.com/buildroot/buildroot.git "$THIRD_PARTY/buildroot"
clone_or_update https://github.com/litex-hub/opensbi.git "$THIRD_PARTY/opensbi" "1.3.1-linux-on-litex-vexriscv"

printf '\nLinux-on-LiteX reference trees are ready under %s\n' "$THIRD_PARTY"
printf '  linux-on-litex-vexriscv: %s\n' "$(git -C "$THIRD_PARTY/linux-on-litex-vexriscv" rev-parse --short HEAD)"
printf '  buildroot:                %s\n' "$(git -C "$THIRD_PARTY/buildroot" rev-parse --short HEAD)"
printf '  opensbi:                  %s\n' "$(git -C "$THIRD_PARTY/opensbi" rev-parse --short HEAD)"
