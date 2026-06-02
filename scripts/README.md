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
