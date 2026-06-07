#!/usr/bin/env bash
set -euo pipefail

# Buildroot post-build hook for the Nexys4 DDR image. Runs after the target
# filesystem is assembled (with $TARGET_DIR as the staged rootfs) and before the
# filesystem images are packed.
#
# Add a getty on tty1 so the VGA framebuffer console (fbcon) presents a local
# login prompt. Also add an explicit LiteUART getty on ttyLXU0: with both
# console=liteuart and console=tty0 in the kernel command line, /dev/console can
# resolve to tty0, so Buildroot's default console:: getty alone does not keep a
# login on the serial port. The explicit ttyLXU0 getty keeps serial/SSH as the
# primary control path regardless of which console /dev/console points at.
#
# Idempotent: each line is only appended if absent, so repeated builds and the
# overlay do not accumulate duplicates.

TARGET_DIR=${1:-${TARGET_DIR:-}}
if [ -z "$TARGET_DIR" ]; then
  echo "post-build-nexys4ddr: TARGET_DIR not provided" >&2
  exit 1
fi

INITTAB="$TARGET_DIR/etc/inittab"
TTY1_LINE='tty1::respawn:/sbin/getty -L tty1 0 linux'
SERIAL_LINE='ttyLXU0::respawn:/sbin/getty -L ttyLXU0 0 vt100'

if [ ! -f "$INITTAB" ]; then
  echo "post-build-nexys4ddr: missing $INITTAB" >&2
  exit 1
fi

if grep -qE '^tty1::' "$INITTAB"; then
  echo "post-build-nexys4ddr: tty1 getty already present in inittab"
else
  printf '%s # VGA framebuffer console login\n' "$TTY1_LINE" >> "$INITTAB"
  echo "post-build-nexys4ddr: added tty1 getty for VGA console login"
fi

if grep -qE '^ttyLXU0::' "$INITTAB"; then
  echo "post-build-nexys4ddr: ttyLXU0 getty already present in inittab"
else
  printf '%s # LiteUART serial console login\n' "$SERIAL_LINE" >> "$INITTAB"
  echo "post-build-nexys4ddr: added ttyLXU0 getty for serial control"
fi


ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
HOST_DIR=${HOST_DIR:-}
CC=${CC:-}
if [ -z "$CC" ] && [ -n "$HOST_DIR" ]; then
  # Prefer Buildroot's compiler wrapper over *.br_real so the target sysroot
  # and wrapper-added flags are applied automatically.
  for candidate in "$HOST_DIR"/bin/*-gcc "$HOST_DIR"/bin/*-gcc.br_real; do
    if [ -x "$candidate" ]; then
      CC=$candidate
      break
    fi
  done
fi

if [ -n "$CC" ] && [ -x "$CC" ]; then
  install -d "$TARGET_DIR/usr/bin"
  "$CC" -O2 -Wall -Wextra -o "$TARGET_DIR/usr/bin/sevenseg_temp_display" \
    "$ROOT_DIR/tools/sevenseg_temp_display.c"
  echo "post-build-nexys4ddr: installed /usr/bin/sevenseg_temp_display"
else
  echo "post-build-nexys4ddr: cross compiler not found; skipping sevenseg_temp_display" >&2
fi
