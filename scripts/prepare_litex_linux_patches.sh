#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

SRC=${SRC:-third_party/linux-on-litex-vexriscv/buildroot/patches}
DST=${DST:-local_patches}
rm -rf "$DST"
mkdir -p "$DST"
cp -a "$SRC"/. "$DST"/

# The reference tree's 0021 LiteUART RX IRQ backport can fail to apply against
# the currently downloaded Linux 6.9 tarball. UART polling still works for
# boot/login, so disable it for the first bring-up; revisit once Linux boots.
patch="$DST/linux/6.9/0021-tty-serial-liteuart-use-rx-irqs-when-available.patch"
if [ -f "$patch" ]; then
  mv "$patch" "$patch.disabled"
fi

printf 'Prepared local Buildroot patch tree in %s
' "$DST"
printf 'Linux 6.9 patches enabled:
'
find "$DST/linux/6.9" -maxdepth 1 -name '*.patch' -printf '%f
' | sort
