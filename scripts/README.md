# Scripts

Helper scripts will be added here for:

- reference SoC generation/build;
- Vivado bitstream build;
- board programming;
- OpenSBI/Linux/rootfs builds;
- UART smoke tests.

Source Vivado before running FPGA build/program scripts:

```bash
set +u
unset ZSH_VERSION
source /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh
```

## Metadata and consistency checks

`tools/dts_patch_args.py` derives the `patch_litex_nexys4ddr_dts.py` argument list
from a `csr.json`; it is the single source of truth shared by both the build and
probe scripts (including the seven-segment scanner vs legacy GPIOOut distinction).

`tools/check_csr_dts_consistency.py` verifies that a generated DTS/DTB matches its
`csr.json` (base addresses, register windows, and node forms). Both scripts run it
after generating the DTS, so a stale artifact or a moved CSR slot fails the build
instead of producing a bitstream/DTB mismatch. It runs without Vivado:

```bash
./scripts/probe_litex_nexys4ddr_linux.sh build/check_meta
python3 tools/check_csr_dts_consistency.py \
  build/check_meta/csr.json build/check_meta/digilent_nexys4ddr_linux.dts
```
