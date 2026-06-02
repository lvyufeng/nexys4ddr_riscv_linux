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

Important: `litex_term --images` boots the address of the last image in JSON insertion order. Keep `fw_jump.bin` last so the serial loader jumps to OpenSBI after loading the kernel and initramfs.

```json
{
  "Image": "0x40000000",
  "rootfs.cpio": "0x41000000",
  "fw_jump.bin": "0x40f00000"
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

OpenSBI source is not vendored in this repository yet. The next step is to bring in a reproducible OpenSBI/Linux/Buildroot flow, preferably derived from `linux-on-litex-vexriscv`, and verify the correct LiteX/VexRiscv platform target and RV32 toolchain.
