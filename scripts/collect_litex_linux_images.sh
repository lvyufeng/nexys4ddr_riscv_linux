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
ROOTFS_IMAGE=
if [ -f "$BR_OUT/rootfs.cpio.gz" ]; then
  ROOTFS_IMAGE=rootfs.cpio.gz
  cp "$BR_OUT/$ROOTFS_IMAGE" "$DST/$ROOTFS_IMAGE"
  rm -f "$DST/rootfs.cpio"
  printf 'copied %s -> %s\n' "$BR_OUT/$ROOTFS_IMAGE" "$DST/$ROOTFS_IMAGE"
elif [ -f "$BR_OUT/rootfs.cpio" ]; then
  ROOTFS_IMAGE=rootfs.cpio
  cp "$BR_OUT/$ROOTFS_IMAGE" "$DST/$ROOTFS_IMAGE"
  rm -f "$DST/rootfs.cpio.gz"
  printf 'copied %s -> %s\n' "$BR_OUT/$ROOTFS_IMAGE" "$DST/$ROOTFS_IMAGE"
else
  echo "missing rootfs image: $BR_OUT/rootfs.cpio.gz or $BR_OUT/rootfs.cpio" >&2
  exit 1
fi

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

if [ "$ROOTFS_IMAGE" = rootfs.cpio.gz ]; then
  INITRD_IMAGE="$DST/$ROOTFS_IMAGE" ./scripts/build_litex_dtb.sh
elif [ -f "$BR_OUT/rv32.dtb" ]; then
  cp "$BR_OUT/rv32.dtb" "$DST/rv32.dtb"
  printf 'copied %s -> %s\n' "$BR_OUT/rv32.dtb" "$DST/rv32.dtb"
elif [ -f "$DST/rv32.dtb" ]; then
  printf 'keeping existing %s\n' "$DST/rv32.dtb"
else
  ./scripts/build_litex_dtb.sh
fi

python3 - "$DST/litex_vexriscv_smp_images.json" "$ROOTFS_IMAGE" <<'PY'
from pathlib import Path
import json
import sys
out = Path(sys.argv[1])
rootfs = sys.argv[2]
out.write_text(json.dumps({
    "Image": "0x40000000",
    "rv32.dtb": "0x40ef0000",
    rootfs: "0x41000000",
    "opensbi.bin": "0x40f00000",
}, indent=2) + "\n")
PY
printf '\nCollected LiteX Linux serial-boot images:\n'
ls -lh "$DST"/Image "$DST/$ROOTFS_IMAGE" "$DST"/rv32.dtb "$DST"/opensbi.bin "$DST"/litex_vexriscv_smp_images.json
