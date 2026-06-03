#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

BR_OUT=${BR_OUT:-third_party/buildroot/output/images}
DST=${DST:-linux/images}
mkdir -p "$DST"

copy_if_exists() {
  local src=$1
  local dst=$2
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    printf 'copied %s -> %s\n' "$src" "$dst"
  else
    printf 'missing %s\n' "$src" >&2
    return 1
  fi
}

copy_if_exists "$BR_OUT/Image" "$DST/Image"
copy_if_exists "$BR_OUT/rootfs.cpio" "$DST/rootfs.cpio"

# Buildroot/OpenSBI normally produces fw_jump.bin; keep the serial-loader name
# aligned with linux/images/litex_vexriscv_smp_images.example.json.
if [ -f "$BR_OUT/fw_jump.bin" ]; then
  cp "$BR_OUT/fw_jump.bin" "$DST/opensbi.bin"
  printf 'copied %s -> %s\n' "$BR_OUT/fw_jump.bin" "$DST/opensbi.bin"
elif [ -f "$DST/opensbi.bin" ]; then
  printf 'keeping existing %s\n' "$DST/opensbi.bin"
else
  echo "missing OpenSBI image: $BR_OUT/fw_jump.bin or $DST/opensbi.bin" >&2
  exit 1
fi

if [ -f "$BR_OUT/rv32.dtb" ]; then
  cp "$BR_OUT/rv32.dtb" "$DST/rv32.dtb"
  printf 'copied %s -> %s\n' "$BR_OUT/rv32.dtb" "$DST/rv32.dtb"
elif [ -f "$DST/rv32.dtb" ]; then
  printf 'keeping existing %s\n' "$DST/rv32.dtb"
else
  ./scripts/build_litex_dtb.sh
fi

cp linux/images/litex_vexriscv_smp_images.example.json "$DST/litex_vexriscv_smp_images.json"
printf '\nCollected LiteX Linux serial-boot images:\n'
ls -lh "$DST"/Image "$DST"/rootfs.cpio "$DST"/rv32.dtb "$DST"/opensbi.bin "$DST"/litex_vexriscv_smp_images.json
