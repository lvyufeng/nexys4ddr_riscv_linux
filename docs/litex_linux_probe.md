# LiteX VexRiscvSMP Linux metadata probe

Stage 1 uses the upstream LiteX Nexys4 DDR target with the VexRiscvSMP Linux CPU variant to generate the Linux-facing SoC metadata.

## Command

```bash
./scripts/probe_litex_nexys4ddr_linux.sh
```

The probe runs:

```text
litex_boards.targets.digilent_nexys4ddr
  --cpu-type=vexriscv_smp
  --cpu-variant=linux
  --cpu-count=1
  --hardware-breakpoints=0
  --build --no-compile
```

`--hardware-breakpoints=0` is intentional: it selects a pre-generated VexRiscvSMP cluster netlist from `pythondata-cpu-vexriscv_smp`, avoiding the need for local SBT/Scala/SpinalHDL netlist generation during the probe.

## Generated files

The ignored build output contains:

```text
build/litex_nexys4ddr_linux_probe/csr.json
build/litex_nexys4ddr_linux_probe/csr.csv
build/litex_nexys4ddr_linux_probe/memory.x
build/litex_nexys4ddr_linux_probe/digilent_nexys4ddr_linux.dts
```

A checked-in reference copy of the generated DTS is kept at:

```text
linux/dts/litex_nexys4ddr_vexriscv_smp.dts
```

## Linux metadata confirmed

The probe confirms that VexRiscvSMP `linux` mode wires the Linux-critical blocks and constants:

```text
CPU:        VexRiscv SMP-LINUX
ISA:        rv32i2p0_ma
MMU:        sv32
CPU count:  1
CLINT:      0xf0010000, 64 KiB
PLIC:       0xf0c00000, 4 MiB
OpenSBI:    0x40f00000, 512 KiB reserved in DDR
DDR:        0x40000000, 128 MiB
UART:       LiteUART at 0xf0001000, IRQ 1
Timer IRQ:  IRQ 2
```

The generated DTS includes:

- `mmu-type = "riscv,sv32"`;
- RISC-V CPU interrupt controller node;
- `riscv,clint0` node;
- SiFive-compatible PLIC node;
- `reserved-memory` for OpenSBI;
- LiteUART console bootargs;
- DDR memory node.

## Important memory-map note

The LiteX reference Linux flow does **not** use the conventional custom-platform map from `docs/memory_map.md`. It uses LiteX's own map:

```text
main_ram @ 0x40000000
opensbi  @ 0x40f00000
csr      @ 0xf0000000
clint    @ 0xf0010000
plic     @ 0xf0c00000
```

For the reference SoC track, follow this generated LiteX map and generated DTS exactly. For the later custom CPU/SoC track, we can return to the conventional RISC-V Linux map with DDR at `0x80000000`, CLINT around `0x02000000`, PLIC around `0x0c000000`, and Linux-standard UART choices such as `ns16550a`.

## Next step

Build or fetch the Linux boot artifacts expected by this LiteX flow:

1. OpenSBI for RV32 + LiteX/VexRiscvSMP handoff.
2. Linux kernel configured for RV32 `rv32ima` + Sv32.
3. BusyBox/initramfs image loaded at the DTS `linux,initrd-start` address.
4. A loader path that places OpenSBI/kernel/initramfs at the addresses described by the generated metadata.

## Full Linux-capable bitstream build

After the metadata probe succeeds, build the Linux-capable VexRiscvSMP SoC bitstream with:

```bash
./scripts/build_litex_nexys4ddr_linux.sh
```

The build uses the same CPU/options as the metadata probe and writes the bitstream under:

```text
build/litex_nexys4ddr_linux/gateware/digilent_nexys4ddr.bit
```

Program it with:

```bash
./scripts/program_litex_nexys4ddr.sh build/litex_nexys4ddr_linux/gateware/digilent_nexys4ddr.bit
```

This bitstream has been built successfully, routed timing is met, programmed to the Nexys4 DDR with startup HIGH, and verified to reach the LiteX BIOS prompt over UART (`LITEX_UART_SMOKE_OK`). The OpenSBI/Linux/rootfs artifacts are loaded later through `litex_term --images` or a payload image.

## Serial image loading plan

`litex_term --images` can load multiple binaries to DDR and then jump to the address of the last image in the JSON file. For the current generated DTS, use this address plan:

```json
{
  "Image": "0x40000000",
  "rootfs.cpio": "0x41000000",
  "fw_jump.bin": "0x40f00000"
}
```

Keep `fw_jump.bin` last so LiteX jumps to OpenSBI. A template is checked in at:

```text
linux/images/litex_vexriscv_smp_images.example.json
```

Then run:

```bash
.venv/bin/litex_term /dev/ttyUSB1   --speed 115200   --serial-boot   --images linux/images/litex_vexriscv_smp_images.json
```
