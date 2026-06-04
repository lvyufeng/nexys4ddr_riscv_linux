#!/usr/bin/env python3
"""Local Nexys4 DDR LiteX Linux target.

This wraps the upstream LiteX-Boards Nexys4 DDR target and only adds project
peripherals that are not instantiated by the upstream target yet. Keeping this in
repo avoids editing the ignored third_party/litex-boards checkout.
"""

from migen import Cat, ClockDomain, Signal

from litex.gen import LiteXModule
from litex_boards.targets import digilent_nexys4ddr
from litex.soc.cores.clock import S7IDELAYCTRL, S7MMCM
from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.soc.cores.video import VideoVGAPHY, video_timings
from litex.soc.integration.builder import Builder


def video_pix_clk(timing):
    if timing not in video_timings:
        available = ", ".join(sorted(video_timings))
        raise ValueError(f"unsupported video timing {timing!r}; available: {available}")
    return video_timings[timing]["pix_clk"]


class LocalCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, vga_clk_freq=40e6):
        self.rst          = Signal()
        self.cd_sys       = ClockDomain()
        self.cd_sys2x     = ClockDomain()
        self.cd_sys2x_dqs = ClockDomain()
        self.cd_idelay    = ClockDomain()
        self.cd_eth       = ClockDomain()
        self.cd_vga       = ClockDomain()

        self.pll = pll = S7MMCM(speedgrade=-1)
        self.comb += pll.reset.eq(~platform.request("cpu_reset_n") | self.rst)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        pll.create_clkout(self.cd_sys2x,     2*sys_clk_freq)
        pll.create_clkout(self.cd_sys2x_dqs, 2*sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_idelay,    200e6)
        pll.create_clkout(self.cd_eth,       50e6)
        pll.create_clkout(self.cd_vga,       vga_clk_freq)
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)

        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


class LocalSoC(digilent_nexys4ddr.BaseSoC):
    def __init__(
        self,
        *args,
        with_switches=False,
        with_buttons=False,
        with_rgb_leds=False,
        with_seven_seg=False,
        with_video_terminal=False,
        with_video_framebuffer=False,
        video_timing="800x600@60Hz",
        sys_clk_freq=75e6,
        **kwargs,
    ):
        # The upstream Nexys4 DDR target hardcodes a 40 MHz VGA clock and
        # 800x600@60Hz. Keep local video timing configurable so hardware tests can
        # use conservative monitor-compatible modes such as 640x480@60Hz.
        vga_clk_freq = video_pix_clk(video_timing)
        upstream_crg = digilent_nexys4ddr._CRG
        digilent_nexys4ddr._CRG = lambda platform, sys_clk_freq: LocalCRG(
            platform, sys_clk_freq, vga_clk_freq=vga_clk_freq)
        try:
            super().__init__(
                *args,
                sys_clk_freq=sys_clk_freq,
                with_video_terminal=False,
                with_video_framebuffer=False,
                **kwargs,
            )
        finally:
            digilent_nexys4ddr._CRG = upstream_crg

        if with_video_terminal or with_video_framebuffer:
            self.videophy = VideoVGAPHY(self.platform.request("vga"), clock_domain="vga")
            if with_video_terminal:
                self.add_video_terminal(phy=self.videophy, timings=video_timing, clock_domain="vga")
            if with_video_framebuffer:
                self.add_video_framebuffer(phy=self.videophy, timings=video_timing, clock_domain="vga")
            self.add_constant("video_timing", video_timing)
            self.add_constant("video_pix_clk", int(vga_clk_freq))

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

        if with_rgb_leds:
            rgb0 = self.platform.request("rgb_led", 0)
            rgb1 = self.platform.request("rgb_led", 1)
            rgb_pads = Cat(rgb0.r, rgb0.g, rgb0.b, rgb1.r, rgb1.g, rgb1.b)
            self.rgb_leds = GPIOOut(rgb_pads)
            self.csr.add("rgb_leds", n=12, use_loc_if_exists=True)
            self.add_constant("rgb_leds_ngpio", 6)

        if with_seven_seg:
            self.seven_seg = GPIOOut(self.platform.request("seven_seg"), reset=0x00)
            self.csr.add("seven_seg", n=13, use_loc_if_exists=True)
            self.add_constant("seven_seg_ngpio", 8)

            # Nexys4 DDR digit enables are active-low. Reset all high so no digit
            # is selected until Linux explicitly drives the controller.
            self.seven_seg_ctrl = GPIOOut(self.platform.request("seven_seg_ctrl_n"), reset=0xff)
            self.csr.add("seven_seg_ctrl", n=14, use_loc_if_exists=True)
            self.add_constant("seven_seg_ctrl_ngpio", 8)


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
    parser.add_target_argument("--video-timing", default="800x600@60Hz", help="LiteX video timing preset, e.g. 640x480@60Hz or 800x600@60Hz.")
    parser.add_target_argument("--with-switches", action="store_true", help="Expose 16 board switches as LiteX GPIO inputs.")
    parser.add_target_argument("--with-buttons", action="store_true", help="Expose 5 board buttons as LiteX GPIO inputs.")
    parser.add_target_argument("--with-rgb-leds", action="store_true", help="Expose the two RGB LEDs as 6 LiteX GPIO outputs.")
    parser.add_target_argument("--with-seven-seg", action="store_true", help="Expose seven-segment segments and digit controls as LiteX GPIO outputs.")
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
        video_timing=args.video_timing,
        with_switches=args.with_switches,
        with_buttons=args.with_buttons,
        with_rgb_leds=args.with_rgb_leds,
        with_seven_seg=args.with_seven_seg,
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
