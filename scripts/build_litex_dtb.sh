#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

DTS=${1:-linux/dts/litex_nexys4ddr_vexriscv_smp.dts}
DTB=${2:-linux/images/rv32.dtb}

DTC=${DTC:-}
if [ -z "$DTC" ]; then
  if command -v dtc >/dev/null 2>&1; then
    DTC=$(command -v dtc)
  elif [ -x /mnt/data1/Xilinx/2025.2/Vivado/bin/dtc ]; then
    DTC=/mnt/data1/Xilinx/2025.2/Vivado/bin/dtc
  else
    echo "Missing dtc. Install device-tree-compiler or source Vivado 2025.2." >&2
    exit 1
  fi
fi

TMP_DTS=
cleanup() {
  if [ -n "$TMP_DTS" ]; then
    rm -f "$TMP_DTS"
  fi
}
trap cleanup EXIT

if [ "${INITRD_IMAGE:-}" = "none" ]; then
  INITRD_IMAGE=
elif [ -z "${INITRD_IMAGE:-}" ] && [ -f linux/images/rootfs.cpio.gz ] && grep -q "linux,initrd-end" "$DTS"; then
  INITRD_IMAGE=linux/images/rootfs.cpio.gz
fi

# When INITRD_IMAGE is provided, patch linux,initrd-end to the exact loaded
# file end. This matters for gzip-compressed initramfs images: using a much
# larger static window can make Linux inspect unrelated DDR bytes after the
# compressed stream. Set INITRD_IMAGE=none for DTBs that intentionally boot
# from a block-device rootfs and do not contain linux,initrd-* properties.
if [ -n "${INITRD_IMAGE:-}" ]; then
  if [ ! -f "$INITRD_IMAGE" ]; then
    echo "Missing INITRD_IMAGE: $INITRD_IMAGE" >&2
    exit 1
  fi
  INITRD_START=${INITRD_START:-0x41000000}
  INITRD_INFO=$(python3 - "$INITRD_START" "$INITRD_IMAGE" <<'PY'
import os
import sys
start = int(sys.argv[1], 0)
size = os.path.getsize(sys.argv[2])
end = start + size
print(f"0x{end:08x} {size}")
PY
)
  INITRD_END=${INITRD_INFO%% *}
  INITRD_SIZE=${INITRD_INFO##* }
  TMP_DTS=$(mktemp)
  python3 - "$DTS" "$TMP_DTS" "$INITRD_END" <<'PY'
from pathlib import Path
import re
import sys
src, dst, initrd_end = sys.argv[1:]
text = Path(src).read_text()
new = re.sub(
    r"linux,initrd-end\s*=\s*<0x[0-9a-fA-F]+>;",
    f"linux,initrd-end   = <{initrd_end}>;",
    text,
    count=1,
)
if new == text:
    raise SystemExit("failed to patch linux,initrd-end in DTS")
Path(dst).write_text(new)
PY
  DTS=$TMP_DTS
  printf 'DTB initrd image: %s (%s bytes)\n' "$INITRD_IMAGE" "$INITRD_SIZE"
  printf 'DTB initrd range: %s..%s\n' "$INITRD_START" "$INITRD_END"
fi

mkdir -p "$(dirname "$DTB")"
"$DTC" -I dts -O dtb -o "$DTB" "$DTS"
printf 'DTB image: %s\n' "$DTB"
ls -l "$DTB"
