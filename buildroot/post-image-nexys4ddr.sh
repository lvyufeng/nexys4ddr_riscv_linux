#!/usr/bin/env bash
set -euo pipefail

# Buildroot invokes post-image scripts from the Buildroot top-level directory.
# Keep this script path-stable by deriving the repository root from $0.
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DST="$ROOT_DIR/linux/images"
mkdir -p "$DST"

copy_required() {
  local src=$1
  local dst=$2
  if [ ! -f "$src" ]; then
    echo "Missing required Buildroot image: $src" >&2
    exit 1
  fi
  cp "$src" "$dst"
  printf 'copied %s -> %s\n' "$src" "$dst"
}

copy_required "$BINARIES_DIR/Image" "$DST/Image"
copy_required "$BINARIES_DIR/rootfs.cpio.gz" "$DST/rootfs.cpio.gz"
rm -f "$DST/rootfs.cpio"
copy_required "$BINARIES_DIR/fw_jump.bin" "$DST/opensbi.bin"

# Buildroot does not generate the LiteX DTB in this flow. Rebuild it here so
# linux,initrd-end matches the compressed initramfs size exactly.
INITRD_IMAGE="$DST/rootfs.cpio.gz" "$ROOT_DIR/scripts/build_litex_dtb.sh"

cp "$ROOT_DIR/linux/images/litex_vexriscv_smp_images.example.json" \
   "$DST/litex_vexriscv_smp_images.json"

printf '\nNexys4 DDR LiteX Linux images are ready in %s:\n' "$DST"
ls -lh "$DST"/Image "$DST"/rootfs.cpio.gz "$DST"/opensbi.bin "$DST"/rv32.dtb "$DST"/litex_vexriscv_smp_images.json
