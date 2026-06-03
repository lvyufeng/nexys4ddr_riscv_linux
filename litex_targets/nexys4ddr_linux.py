#!/usr/bin/env python3
"""Local Nexys4 DDR LiteX Linux target.

This wraps the upstream LiteX-Boards Nexys4 DDR target and only adds project
peripherals that are not instantiated by the upstream target yet. Keeping this in
repo avoids editing the ignored third_party/litex-boards checkout.
"""

from litex_boards.targets import digilent_nexys4ddr
from litex.soc.cores.gpio import GPIOIn
from litex.soc.integration.builder import Builder


class LocalSoC(digilent_nexys4ddr.BaseSoC):
    def __init__(self, *args, with_switches=False, with_buttons=False, **kwargs):
        super().__init__(*args, **kwargs)

        if with_switches:
            self.switches = GPIOIn(self.platform.request_all("user_sw"), with_irq=True)
            self.csr.add("switches", n=10, use_loc_if_exists=True)
            self.irq.add("switches")
            self.add_constant("switches_ngpio", 16)

        if with_buttons:
            self.buttons = GPIOIn(self.platform.request_all("user_btn"), with_irq=True)
            self.csr.add("buttons", n=11, use_loc_if_exists=True)
            self.irq.add("buttons")
            self.add_constant("buttons_ngpio", 5)


def main():
    from litex.build.parser import LiteXArgumentParser

    parser = LiteXArgumentParser(
        platform=digilent_nexys4ddr.digilent_nexys4ddr.Platform,
        description="Local LiteX Linux SoC on Nexys4DDR.",
    )
    parser.add_target_argument("--sys-clk-freq", default=75e6, type=float, help="System clock frequency.")
    ethopts = parser.target_group.add_mutually_exclusive_group()
    ethopts.add_argument("--with-ethernet", action="store_true", help="Enable Ethernet support.")
    ethopts.add_argument("--with-etherbone", action="store_true", help="Enable Etherbone support.")
    parser.add_target_argument("--eth-ip", default="192.168.1.50", help="Ethernet/Etherbone IP address.")
    parser.add_target_argument("--eth-dynamic-ip", action="store_true", help="Enable dynamic Ethernet IP assignment.")
    parser.add_target_argument("--remote-ip", default="192.168.1.100", help="Remote IP address of TFTP server.")
    sdopts = parser.target_group.add_mutually_exclusive_group()
    sdopts.add_argument("--with-spi-sdcard", action="store_true", help="Enable SPI-mode SDCard support.")
    sdopts.add_argument("--with-sdcard", action="store_true", help="Enable SDCard support.")
    viopts = parser.target_group.add_mutually_exclusive_group()
    viopts.add_argument("--with-video-terminal", action="store_true", help="Enable Video Terminal (VGA).")
    viopts.add_argument("--with-video-framebuffer", action="store_true", help="Enable Video Framebuffer (VGA).")
    parser.add_target_argument("--with-switches", action="store_true", help="Expose 16 board switches as LiteX GPIO inputs.")
    parser.add_target_argument("--with-buttons", action="store_true", help="Expose 5 board buttons as LiteX GPIO inputs.")
    args = parser.parse_args()

    soc = LocalSoC(
        sys_clk_freq=args.sys_clk_freq,
        with_ethernet=args.with_ethernet,
        with_etherbone=args.with_etherbone,
        eth_ip=args.eth_ip,
        eth_dynamic_ip=args.eth_dynamic_ip,
        remote_ip=args.remote_ip,
        with_video_terminal=args.with_video_terminal,
        with_video_framebuffer=args.with_video_framebuffer,
        with_switches=args.with_switches,
        with_buttons=args.with_buttons,
        **parser.soc_argdict,
    )
    if args.with_spi_sdcard:
        soc.add_spi_sdcard()
    if args.with_sdcard:
        soc.add_sdcard()

    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))


if __name__ == "__main__":
    main()
