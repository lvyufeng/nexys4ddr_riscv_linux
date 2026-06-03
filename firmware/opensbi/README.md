# OpenSBI for the LiteX/VexRiscvSMP reference SoC

The current LiteX Linux-capable SoC reserves OpenSBI memory through the generated CSR JSON/DTS:

```text
OpenSBI load/reserved address: 0x40f00000
OpenSBI reserved size:         0x00080000
DDR base:                      0x40000000
Kernel image load address:     0x40000000
Initramfs load window:         0x41000000..0x41800000
```

Use the generated DTS as the hardware contract:

```text
linux/dts/litex_nexys4ddr_vexriscv_smp.dts
```

## Expected serial boot shape

After the Linux-capable bitstream is programmed and the LiteX BIOS prompt is visible, use `litex_term --images` to upload images and jump to OpenSBI.

Template image map:

```text
linux/images/litex_vexriscv_smp_images.example.json
```

Important: `litex_term --images` boots the address of the last image in JSON insertion order. Keep `opensbi.bin` last so the serial loader jumps to OpenSBI after loading the kernel, DTB, and initramfs.

```json
{
  "Image": "0x40000000",
  "rv32.dtb": "0x40ef0000",
  "rootfs.cpio": "0x41000000",
  "opensbi.bin": "0x40f00000"
}
```

Example upload command once the files exist next to the JSON file:

```bash
.venv/bin/litex_term /dev/ttyUSB1 \
  --speed 115200 \
  --serial-boot \
  --images linux/images/litex_vexriscv_smp_images.json
```

Use `--safe` if serial upload is unreliable.

## Next work

OpenSBI source is not vendored in git history, but `scripts/bootstrap_linux_on_litex.sh` clones the reference `linux-on-litex-vexriscv`, Buildroot, and the matching `litex-hub/opensbi` branch under ignored `third_party/`.


## Verified OpenSBI-only smoke test

The helper scripts now build the OpenSBI jump image and DTB:

```bash
./scripts/build_opensbi_litex.sh
./scripts/build_litex_dtb.sh
```

`build_opensbi_litex.sh` uses Vivado 2025.2's bundled RISC-V GCC and overrides the OpenSBI ISA string to `rv32ima_zicsr_zifencei`, which is required by newer GCC/binutils for CSR/fence instructions.

With the Linux-capable LiteX bitstream programmed, this command uploads only DTB + OpenSBI and exits once the OpenSBI banner appears:

```bash
./scripts/boot_opensbi_only.sh /dev/ttyUSB1 --safe
```

Observed hardware result:

```text
[LITEX-TERM] Uploading .../rv32.dtb to 0x40ef0000
[LITEX-TERM] Uploading .../opensbi.bin to 0x40f00000
Executing booted program at 0x40f00000
OpenSBI
```

This validates the LiteX serial loader, DTB address, OpenSBI link/load address, and M-mode firmware entry. Linux kernel/rootfs are the next step.


Before re-running this smoke test after a successful OpenSBI jump, reprogram the Linux-capable LiteX bitstream or press the FPGA reset button so the LiteX BIOS boot menu is emitted again. The automatic `--serial-boot` handshake is emitted by the LiteX BIOS during the short boot window, not by OpenSBI. If the board is already at the `litex>` prompt, the manual command is `serialboot`, but automation can miss its short magic prompt.


## OpenSBI + Linux handoff verified

The full serial-loaded path has been verified on Nexys4 DDR hardware:

```text
opensbi.bin @ 0x40f00000
Image       @ 0x40000000
rv32.dtb    @ 0x40ef0000
rootfs.cpio @ 0x41000000
```

OpenSBI jumps to Linux S-mode at `0x40000000` with DTB argument `0x40ef0000`,
and Linux 6.9 reaches the Buildroot login prompt.
