#!/usr/bin/env python3
"""Local Nexys4 DDR LiteX Linux target.

This wraps the upstream LiteX-Boards Nexys4 DDR target and only adds project
peripherals that are not instantiated by the upstream target yet. Keeping this in
repo avoids editing the ignored third_party/litex-boards checkout.
"""

from migen import Array, Case, Cat, ClockDomain, Constant, If, Mux, Signal
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import SyncFIFO

from litex.gen import LiteXModule
from litex_boards.targets import digilent_nexys4ddr
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.cores.clock import S7IDELAYCTRL, S7MMCM
from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.soc.cores.video import VideoVGAPHY, video_timings
from litex.soc.cores.xadc import XADC
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStatus, CSRStorage
from litex.soc.interconnect.csr_eventmanager import EventManager, EventSourceLevel


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


class PS2SelfTestSource(LiteXModule):
    """Fabric PS/2 keyboard waveform source for hardware diagnostics.

    This deliberately does not drive the board's external PS/2/USB-HID pins. It
    feeds the fabric PS/2 RX decoder with a legal Set-2 key sequence so the
    LiteX RX FIFO, Linux `litex-ps2` serio driver, and `atkbd` can be tested at
    real PS/2 timing even when the external USB-HID-to-PS/2 bridge is not
    producing scan codes.
    """

    def __init__(self, sys_clk_freq, half_period_us=35):
        self.ctrl = CSRStorage(1, description="Write bit 0 = 1 to inject Set-2 A make/break PS/2 frames.")
        self.status = CSRStatus(1, description="Bit 0 = injection engine busy.")
        self.clk = Signal(reset=1)
        self.dat = Signal(reset=1)

        # # #

        # Sequence bytes: Set-2 'A' make (0x1c), break prefix (0xf0), make code.
        # Frames are start(0), 8 data bits LSB-first, odd parity, stop(1).
        def ps2_frame(byte):
            parity = 0 if (bin(byte).count("1") & 1) else 1
            return (0 << 0) | (byte << 1) | (parity << 9) | (1 << 10)

        frames = Array(Constant(ps2_frame(v), 11) for v in [0x1c, 0xf0, 0x1c])
        byte_idx = Signal(max=3)
        bit_idx = Signal(max=11)
        phase = Signal(2)
        shreg = Signal(11, reset=(1 << 10))
        busy = Signal(reset=0)
        divider = max(2, int(sys_clk_freq * half_period_us / 1_000_000))
        timer = Signal(max=divider)

        self.comb += [
            self.status.status.eq(busy),
            self.clk.eq(~busy | (phase != 1)),
            self.dat.eq(~busy | shreg[0]),
        ]

        self.sync += [
            If(~busy,
                timer.eq(0),
                phase.eq(0),
                bit_idx.eq(0),
                byte_idx.eq(0),
                shreg.eq(1 << 10),
                If(self.ctrl.re & self.ctrl.storage[0],
                    busy.eq(1),
                    shreg.eq(frames[0]),
                ),
            ).Else(
                If(timer == (divider - 1),
                    timer.eq(0),
                    If(phase == 0,
                        phase.eq(1),
                    ).Elif(phase == 1,
                        phase.eq(2),
                    ).Else(
                        phase.eq(0),
                        shreg.eq(Cat(shreg[1:11], Constant(1, 1))),
                        If(bit_idx == 10,
                            bit_idx.eq(0),
                            If(byte_idx == 2,
                                busy.eq(0),
                                byte_idx.eq(0),
                            ).Else(
                                byte_idx.eq(byte_idx + 1),
                                shreg.eq(frames[byte_idx + 1]),
                            ),
                        ).Else(
                            bit_idx.eq(bit_idx + 1),
                        ),
                    ),
                ).Else(
                    timer.eq(timer + 1),
                ),
            )
        ]



class PS2KeyboardRx(LiteXModule):
    """PS/2 keyboard controller with fabric RX FIFO and optional host TX.

    The RX path samples PS/2 frames in fabric and raises one interrupt per
    received byte, avoiding the per-bit interrupt latency of Linux `ps2-gpio`.
    When external pads are provided, the block also drives the PS/2 clock/data
    pins as open-drain outputs so software can send host commands such as reset
    (0xff) and enable scanning (0xf4). Existing RX/data/status/event offsets are
    kept stable for the Linux driver.
    """

    def __init__(self, clk, dat, sys_clk_freq, fifo_depth=16, timeout_us=2000, pads=None):
        self.data = CSRStatus(8, description="Next received PS/2 byte. Reading pops one FIFO entry.")
        self.status = CSRStatus(32, description="Bit 0=RX readable, 1=RX writable, 2=overflow, 3=frame error, 4=parity error, 5=sampled clock, 6=sampled data, bits 8..15=FIFO level.")
        self.ctrl = CSRStorage(3, description="Bit 0=clear sticky RX error flags, 1=clear diagnostic counters/history, 2=reset RX decoder state.")

        self.submodules.fifo = fifo = SyncFIFO(width=8, depth=fifo_depth)
        self.ev = EventManager()
        self.ev.rx_ready = EventSourceLevel(description="Asserted while the PS/2 RX FIFO is not empty.")
        self.ev.finalize()

        # Keep data/status/ctrl/event offsets stable for the Linux driver. These
        # diagnostic CSRs are deliberately appended at offsets 0x18/0x1c.
        self.diag_edges = CSRStatus(32, description="Bits 0..15=PS/2 clock falling-edge count, bits 16..31=data transition count.")
        self.diag_sample = CSRStatus(32, description="Bits 0..7=recent clock samples, 8..15=recent data samples, 16=current clock, 17=current data, 24..27=RX bit index, 28=RX in frame.")

        # Optional host-command CSRs, appended after the previous 0x20 window.
        self.tx_data = CSRStorage(8, description="Write one PS/2 host command byte to transmit, for example 0xff reset or 0xf4 enable scanning.")
        self.tx_status = CSRStatus(32, description="Bit 0=TX busy, 1=TX ready, 2=electrical ACK bit seen, 3=timeout, 4=bus error, 5=TX supported, 6=clock driven low, 7=data driven low, bits 8..15=last response/ACK marker, 16..23=last TX byte, 24..28=TX state.")
        self.host_ctrl = CSRStorage(4, description="Bit 0=clear TX flags, 1=send reset 0xff, 2=send enable scanning 0xf4, 3=force release clock/data and abort TX.")

        # # #

        clk_raw = Signal(reset=1)
        dat_raw = Signal(reset=1)
        clk_i = Signal(reset=1)
        dat_i = Signal(reset=1)
        clk_d = Signal(reset=1)
        dat_d = Signal(reset=1)
        falling = Signal()
        rising = Signal()
        data_transition = Signal()
        clk_drive_low = Signal()
        dat_drive_low = Signal()
        rx_suppressed = Signal()

        if pads is not None:
            # PS/2 is open-drain. Release high by disabling the output driver;
            # drive only low and let board/internal pull-ups produce high.
            self.specials += [
                Tristate(pads.clk, o=0, oe=clk_drive_low, i=clk_raw),
                Tristate(pads.dat, o=0, oe=dat_drive_low, i=dat_raw),
            ]
        else:
            self.comb += [
                clk_raw.eq(clk),
                dat_raw.eq(dat),
            ]

        bit_idx = Signal(max=11)
        byte = Signal(8)
        parity = Signal()
        parity_bit = Signal()
        overflow = Signal()
        frame_error = Signal()
        parity_error = Signal()
        rx_valid = Signal()
        rx_byte = Signal(8)
        clk_history = Signal(8, reset=0xff)
        dat_history = Signal(8, reset=0xff)
        clk_fall_count = Signal(16)
        dat_transition_count = Signal(16)
        timeout_cycles = max(2, int(sys_clk_freq * timeout_us / 1_000_000))
        timer = Signal(max=timeout_cycles)

        # TX/host command state.
        tx_supported = pads is not None
        tx_state = Signal(5)
        tx_busy = Signal(reset=0)
        tx_ack_seen = Signal(reset=0)
        tx_timeout = Signal(reset=0)
        tx_bus_error = Signal(reset=0)
        tx_byte = Signal(8)
        tx_last_byte = Signal(8)
        tx_last_response = Signal(8)
        tx_shift = Signal(11, reset=(1 << 10))
        tx_bit_idx = Signal(max=12)
        tx_parity = Signal()
        tx_bit_value = Signal(reset=1)

        TX_IDLE        = 0
        TX_WAIT_IDLE   = 1
        TX_INHIBIT     = 2
        TX_REQUEST     = 3
        TX_SEND_HOLD   = 4
        TX_SEND_WAIT   = 5
        TX_RELEASE_ACK = 6
        TX_ACK_LOW     = 7
        TX_ACK_RISE    = 8

        tx_idle_cycles = max(2, int(sys_clk_freq * 50 / 1_000_000))
        # PS/2 host-to-device: host pulls clock low for at least 100 us,
        # then pulls data low and releases clock as a request-to-send.
        tx_inhibit_cycles = max(2, int(sys_clk_freq * 150 / 1_000_000))
        tx_request_cycles = max(2, int(sys_clk_freq * 20 / 1_000_000))
        # Device should start clocking within 15 ms. A complete packet should
        # finish quickly, but using the 15 ms watchdog per bit keeps recovery
        # safe with slow bridge firmware.
        tx_timeout_cycles = max(2, int(sys_clk_freq * 15_000 / 1_000_000))
        tx_timer = Signal(max=max(tx_timeout_cycles, tx_inhibit_cycles, tx_request_cycles, tx_idle_cycles) + 1)

        tx_bits = Array([tx_shift[i] for i in range(11)] + [Constant(1, 1)])

        self.specials += [
            MultiReg(clk_raw, clk_i),
            MultiReg(dat_raw, dat_i),
        ]

        self.comb += [
            falling.eq(clk_d & ~clk_i),
            rising.eq(~clk_d & clk_i),
            data_transition.eq(dat_d ^ dat_i),
            rx_suppressed.eq(tx_busy),
            tx_parity.eq(~(tx_byte[0] ^ tx_byte[1] ^ tx_byte[2] ^ tx_byte[3] ^
                           tx_byte[4] ^ tx_byte[5] ^ tx_byte[6] ^ tx_byte[7])),
            tx_bit_value.eq(tx_bits[tx_bit_idx]),
            fifo.din.eq(rx_byte),
            fifo.we.eq(rx_valid & fifo.writable),
            fifo.re.eq(self.data.we & fifo.readable),
            self.data.status.eq(fifo.dout),
            self.status.status[0].eq(fifo.readable),
            self.status.status[1].eq(fifo.writable),
            self.status.status[2].eq(overflow),
            self.status.status[3].eq(frame_error),
            self.status.status[4].eq(parity_error),
            self.status.status[5].eq(clk_i),
            self.status.status[6].eq(dat_i),
            self.status.status[8:16].eq(fifo.level),
            self.diag_edges.status[0:16].eq(clk_fall_count),
            self.diag_edges.status[16:32].eq(dat_transition_count),
            self.diag_sample.status[0:8].eq(clk_history),
            self.diag_sample.status[8:16].eq(dat_history),
            self.diag_sample.status[16].eq(clk_i),
            self.diag_sample.status[17].eq(dat_i),
            self.diag_sample.status[24:28].eq(bit_idx),
            self.diag_sample.status[28].eq(bit_idx != 0),
            self.tx_status.status[0].eq(tx_busy),
            self.tx_status.status[1].eq(~tx_busy),
            self.tx_status.status[2].eq(tx_ack_seen),
            self.tx_status.status[3].eq(tx_timeout),
            self.tx_status.status[4].eq(tx_bus_error),
            self.tx_status.status[5].eq(Constant(int(tx_supported), 1)),
            self.tx_status.status[6].eq(clk_drive_low),
            self.tx_status.status[7].eq(dat_drive_low),
            self.tx_status.status[8:16].eq(tx_last_response),
            self.tx_status.status[16:24].eq(tx_last_byte),
            self.tx_status.status[24:29].eq(tx_state),
            self.ev.rx_ready.trigger.eq(fifo.readable),
        ]

        data_bit_cases = {}
        for i in range(8):
            data_bit_cases[i + 1] = [
                If(dat_i, byte.eq(byte | (1 << i))),
                parity.eq(parity ^ dat_i),
                bit_idx.eq(bit_idx + 1),
            ]

        self.sync += [
            clk_d.eq(clk_i),
            dat_d.eq(dat_i),
            clk_history.eq(Cat(clk_history[1:8], clk_i)),
            dat_history.eq(Cat(dat_history[1:8], dat_i)),
            rx_valid.eq(0),
            If(falling,
                clk_fall_count.eq(clk_fall_count + 1),
            ),
            If(data_transition,
                dat_transition_count.eq(dat_transition_count + 1),
            ),
            If(self.ctrl.re & self.ctrl.storage[0],
                overflow.eq(0),
                frame_error.eq(0),
                parity_error.eq(0),
            ),
            If(self.ctrl.re & self.ctrl.storage[1],
                clk_fall_count.eq(0),
                dat_transition_count.eq(0),
                clk_history.eq(0xff),
                dat_history.eq(0xff),
            ),
            If((self.ctrl.re & self.ctrl.storage[2]) | rx_suppressed,
                bit_idx.eq(0),
                byte.eq(0),
                parity.eq(0),
                parity_bit.eq(0),
                timer.eq(0),
            ).Else(
                If(bit_idx != 0,
                    If(timer == (timeout_cycles - 1),
                        timer.eq(0),
                        bit_idx.eq(0),
                        frame_error.eq(1),
                    ).Else(
                        timer.eq(timer + 1),
                    ),
                ).Else(
                    timer.eq(0),
                ),
                If(falling,
                    timer.eq(0),
                    Case(bit_idx, {
                        0: [
                            If(dat_i,
                                frame_error.eq(1),
                            ).Else(
                                byte.eq(0),
                                parity.eq(0),
                                parity_bit.eq(0),
                                bit_idx.eq(1),
                            ),
                        ],
                        **data_bit_cases,
                        9: [
                            parity_bit.eq(dat_i),
                            bit_idx.eq(10),
                        ],
                        10: [
                            If(~dat_i,
                                frame_error.eq(1),
                            ).Elif(~(parity ^ parity_bit),
                                parity_error.eq(1),
                            ).Elif(fifo.writable,
                                rx_valid.eq(1),
                                rx_byte.eq(byte),
                            ).Else(
                                overflow.eq(1),
                            ),
                            bit_idx.eq(0),
                            byte.eq(0),
                            parity.eq(0),
                            parity_bit.eq(0),
                        ],
                    }),
                ),
            ),
        ]

        self.sync += [
            If(self.host_ctrl.re & self.host_ctrl.storage[0],
                tx_ack_seen.eq(0),
                tx_timeout.eq(0),
                tx_bus_error.eq(0),
                tx_last_response.eq(0),
            ),
            If(self.host_ctrl.re & self.host_ctrl.storage[3],
                tx_busy.eq(0),
                tx_state.eq(TX_IDLE),
                tx_timer.eq(0),
                tx_bit_idx.eq(0),
                clk_drive_low.eq(0),
                dat_drive_low.eq(0),
            ).Elif(~tx_busy,
                clk_drive_low.eq(0),
                dat_drive_low.eq(0),
                tx_state.eq(TX_IDLE),
                tx_timer.eq(0),
                tx_bit_idx.eq(0),
                If(tx_supported & self.tx_data.re,
                    tx_byte.eq(self.tx_data.storage),
                    tx_last_byte.eq(self.tx_data.storage),
                    tx_ack_seen.eq(0),
                    tx_timeout.eq(0),
                    tx_bus_error.eq(0),
                    tx_last_response.eq(0),
                    tx_busy.eq(1),
                    tx_state.eq(TX_WAIT_IDLE),
                ).Elif(tx_supported & self.host_ctrl.re & self.host_ctrl.storage[1],
                    tx_byte.eq(0xff),
                    tx_last_byte.eq(0xff),
                    tx_ack_seen.eq(0),
                    tx_timeout.eq(0),
                    tx_bus_error.eq(0),
                    tx_last_response.eq(0),
                    tx_busy.eq(1),
                    tx_state.eq(TX_WAIT_IDLE),
                ).Elif(tx_supported & self.host_ctrl.re & self.host_ctrl.storage[2],
                    tx_byte.eq(0xf4),
                    tx_last_byte.eq(0xf4),
                    tx_ack_seen.eq(0),
                    tx_timeout.eq(0),
                    tx_bus_error.eq(0),
                    tx_last_response.eq(0),
                    tx_busy.eq(1),
                    tx_state.eq(TX_WAIT_IDLE),
                ),
            ).Else(
                If(tx_state == TX_WAIT_IDLE,
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(0),
                    If(clk_i & dat_i,
                        If(tx_timer == (tx_idle_cycles - 1),
                            tx_timer.eq(0),
                            tx_shift.eq(Cat(Constant(0, 1), tx_byte, tx_parity, Constant(1, 1))),
                            tx_state.eq(TX_INHIBIT),
                        ).Else(
                            tx_timer.eq(tx_timer + 1),
                        ),
                    ).Else(
                        tx_timer.eq(0),
                    ),
                ).Elif(tx_state == TX_INHIBIT,
                    clk_drive_low.eq(1),
                    dat_drive_low.eq(0),
                    If(tx_timer == (tx_inhibit_cycles - 1),
                        tx_timer.eq(0),
                        tx_state.eq(TX_REQUEST),
                    ).Else(
                        tx_timer.eq(tx_timer + 1),
                    ),
                ).Elif(tx_state == TX_REQUEST,
                    clk_drive_low.eq(1),
                    dat_drive_low.eq(1),
                    If(tx_timer == (tx_request_cycles - 1),
                        tx_timer.eq(0),
                        tx_bit_idx.eq(0),
                        tx_state.eq(TX_SEND_WAIT),
                    ).Else(
                        tx_timer.eq(tx_timer + 1),
                    ),
                ).Elif(tx_state == TX_SEND_WAIT,
                    # Keep Clock released and present the current start/data/parity/
                    # stop bit. After each device falling edge, advance to the next
                    # bit while Clock is low so the device samples it on the next
                    # high interval.
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(~tx_bit_value),
                    If(falling,
                        tx_timer.eq(0),
                        If(tx_bit_idx == 9,
                            tx_bit_idx.eq(0),
                            tx_state.eq(TX_RELEASE_ACK),
                        ).Else(
                            tx_bit_idx.eq(tx_bit_idx + 1),
                        ),
                    ).Elif(tx_timer == (tx_timeout_cycles - 1),
                        tx_timeout.eq(1),
                        tx_last_response.eq(0xe5),
                        tx_busy.eq(0),
                        tx_state.eq(TX_IDLE),
                        tx_timer.eq(0),
                        clk_drive_low.eq(0),
                        dat_drive_low.eq(0),
                    ).Else(
                        tx_timer.eq(tx_timer + 1),
                    ),
                ).Elif(tx_state == TX_RELEASE_ACK,
                    # Release Data for the device ACK bit.  Keep TX busy until
                    # the ACK clock pulse has completed and the bus has returned
                    # idle so the next libps2 command cannot start while the
                    # bridge is still finishing the previous response.
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(0),
                    tx_timer.eq(0),
                    tx_state.eq(TX_ACK_LOW),
                ).Elif(tx_state == TX_ACK_LOW,
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(0),
                    If(falling,
                        tx_timer.eq(0),
                        tx_state.eq(TX_ACK_RISE),
                        tx_bit_idx.eq(0),
                        If(~dat_i,
                            tx_ack_seen.eq(1),
                            tx_last_response.eq(0xfa),
                        ).Else(
                            tx_bus_error.eq(1),
                            tx_last_response.eq(0xfe),
                        ),
                    ).Elif(tx_timer == (tx_timeout_cycles - 1),
                        tx_timeout.eq(1),
                        tx_last_response.eq(0xe6),
                        tx_busy.eq(0),
                        tx_state.eq(TX_IDLE),
                        tx_timer.eq(0),
                        tx_bit_idx.eq(0),
                    ).Else(
                        tx_timer.eq(tx_timer + 1),
                    ),
                ).Elif(tx_state == TX_ACK_RISE,
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(0),
                    If(clk_i & dat_i,
                        If(tx_timer == (tx_idle_cycles - 1),
                            tx_busy.eq(0),
                            tx_state.eq(TX_IDLE),
                            tx_timer.eq(0),
                            tx_bit_idx.eq(0),
                        ).Else(
                            tx_timer.eq(tx_timer + 1),
                        ),
                    ).Elif(tx_timer == (tx_timeout_cycles - 1),
                        tx_timeout.eq(1),
                        tx_last_response.eq(0xe7),
                        tx_busy.eq(0),
                        tx_state.eq(TX_IDLE),
                        tx_timer.eq(0),
                        tx_bit_idx.eq(0),
                    ).Else(
                        tx_timer.eq(tx_timer + 1),
                    ),
                ).Else(
                    tx_bus_error.eq(1),
                    tx_busy.eq(0),
                    tx_state.eq(TX_IDLE),
                    tx_timer.eq(0),
                    clk_drive_low.eq(0),
                    dat_drive_low.eq(0),
                ),
            ),
        ]


class SevenSegScanner(LiteXModule):
    """Hardware multiplexing controller for the Nexys4 DDR 8-digit display.

    Linux writes eight segment bytes at low rate; fabric scans the active-low
    digit enables at a stable rate so display refresh is not affected by Linux
    scheduling or I2C/hwmon reads.
    """

    def __init__(self, segments, digit_en_n, sys_clk_freq, scan_hz=1000):
        # One CSR word per register on the 32-bit aligned LiteX CSR bus. Keep the
        # block at CSR slot 13 under the existing name `seven_seg`; do not expose
        # it as a Linux GPIO controller.
        default_divider = max(1, int(sys_clk_freq // (scan_hz * 8)))
        self.control = CSRStorage(
            32,
            reset=(default_divider << 8) | (1 << 2) | (1 << 1) | 1,
            description="Bit 0 enable, bit 1 segment active-low, bit 2 reverse digit order, bits 8..31 scan divider.",
        )
        self.digit0 = CSRStorage(8, reset=0x00, description="Leftmost display cell segment mask before polarity inversion.")
        self.digit1 = CSRStorage(8, reset=0x00)
        self.digit2 = CSRStorage(8, reset=0x00)
        self.digit3 = CSRStorage(8, reset=0x00)
        self.digit4 = CSRStorage(8, reset=0x00)
        self.digit5 = CSRStorage(8, reset=0x00)
        self.digit6 = CSRStorage(8, reset=0x00)
        self.digit7 = CSRStorage(8, reset=0x00)
        self.status = CSRStatus(16, description="Bits 0..2 current scan index, bits 8..15 current physical digit line.")

        # # #

        cells = Array([
            self.digit0.storage,
            self.digit1.storage,
            self.digit2.storage,
            self.digit3.storage,
            self.digit4.storage,
            self.digit5.storage,
            self.digit6.storage,
            self.digit7.storage,
        ])
        idx = Signal(3)
        timer = Signal(24)
        divider = Signal(24)
        physical = Signal(3)
        seg_raw = Signal(8)
        seg_out = Signal(8)
        digit_mask = Signal(8)
        enabled = Signal()
        active_low = Signal()
        reverse = Signal()

        digit_masks = Array([Constant(0xff & ~(1 << i), 8) for i in range(8)])

        self.comb += [
            enabled.eq(self.control.storage[0]),
            active_low.eq(self.control.storage[1]),
            reverse.eq(self.control.storage[2]),
            divider.eq(self.control.storage[8:32]),
            physical.eq(Mux(reverse, 7 - idx, idx)),
            seg_raw.eq(cells[idx]),
            seg_out.eq(Mux(active_low, ~seg_raw, seg_raw)),
            digit_mask.eq(digit_masks[physical]),
            self.status.status.eq(Cat(idx, Constant(0, 5), digit_mask)),
        ]

        self.comb += [
            segments.eq(Mux(enabled, seg_out, Mux(active_low, 0xff, 0x00))),
            digit_en_n.eq(Mux(enabled, digit_mask, 0xff)),
        ]

        self.sync += [
            If(~enabled,
                timer.eq(0),
                idx.eq(0),
            ).Else(
                If(timer >= divider,
                    timer.eq(0),
                    idx.eq(idx + 1),
                ).Else(
                    timer.eq(timer + 1),
                )
            )
        ]


class LocalSoC(digilent_nexys4ddr.BaseSoC):
    def __init__(
        self,
        *args,
        with_switches=False,
        with_buttons=False,
        with_rgb_leds=False,
        with_seven_seg=False,
        with_xadc=False,
        with_temp_i2c=False,
        with_ps2_keyboard=False,
        with_ps2_selftest=False,
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
            # Stable hardware-scanned seven-segment display controller. Linux only
            # writes the eight segment bytes at low rate; fabric performs the
            # active-low digit multiplexing at a fixed scan rate to avoid visible
            # flicker from userspace scheduling/GPIO ioctl jitter.
            self.seven_seg = SevenSegScanner(
                self.platform.request("seven_seg"),
                self.platform.request("seven_seg_ctrl_n"),
                sys_clk_freq=sys_clk_freq,
            )
            self.csr.add("seven_seg", n=13, use_loc_if_exists=True)
            self.add_constant("seven_seg_hardware_scanner", 1)
            self.add_constant("seven_seg_ngpio", 0)
            self.add_constant("seven_seg_ctrl_ngpio", 0)

        if with_xadc:
            # FPGA die temperature/rail monitor. Keep this after the existing
            # display and VGA/PS2 CSR slots so the already verified GPIO/video
            # address contract remains stable.
            self.xadc = XADC()
            self.csr.add("xadc", n=19, use_loc_if_exists=True)

        if with_temp_i2c:
            # Nexys4 DDR external board temperature sensor pins. This exposes
            # the raw LiteX bit-banged I2C master; Linux/userspace can scan the
            # bus to confirm the actual sensor address before relying on it.
            self.temp_i2c = I2CMaster(self.platform.request("temp_sensor", 0))
            self.csr.add("temp_i2c", n=20, use_loc_if_exists=True)

        if with_ps2_selftest and not with_ps2_keyboard:
            raise ValueError("with_ps2_selftest requires with_ps2_keyboard")

        if with_ps2_keyboard:
            # Nexys4 DDR USB-HID host port is bridged on-board to PS/2 pins
            # (clk=F4, dat=B2). A per-bit Linux ps2-gpio IRQ handler proved too
            # slow at real PS/2 clock rates, so decode receive frames in fabric
            # and expose one IRQ per received byte to a small Linux serio driver.
            # Keep this at CSR slot 17 so the verified VGA DMA/VTG slots 15/16
            # (0xf0007800/0xf0008000) stay unchanged.
            if with_ps2_selftest:
                # Diagnostic-only path: feed the RX decoder from a fabric-generated
                # Set-2 receive waveform instead of the board's external USB-HID
                # bridge. Do not use this for the final local-keyboard milestone
                # bitstream.
                self.ps2_selftest = PS2SelfTestSource(sys_clk_freq=sys_clk_freq)
                ps2_clk = self.ps2_selftest.clk
                ps2_dat = self.ps2_selftest.dat
                self.csr.add("ps2_selftest", n=18, use_loc_if_exists=True)
            else:
                ps2 = self.platform.request("ps2")
                ps2_clk = ps2.clk
                ps2_dat = ps2.dat
            ps2_pads = None if with_ps2_selftest else ps2
            self.ps2_keyboard = PS2KeyboardRx(ps2_clk, ps2_dat, sys_clk_freq=sys_clk_freq, pads=ps2_pads)
            self.csr.add("ps2_keyboard", n=17, use_loc_if_exists=True)
            self.irq.add("ps2_keyboard")
            self.add_constant("ps2_keyboard_rx", 1)
            self.add_constant("ps2_keyboard_selftest", int(with_ps2_selftest))


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
    parser.add_target_argument("--with-seven-seg", action="store_true", help="Expose the seven-segment display through the fabric SevenSegScanner CSR.")
    parser.add_target_argument("--with-xadc", action="store_true", help="Expose the FPGA XADC/SysMon block for Linux hwmon temperature display.")
    parser.add_target_argument("--with-temp-i2c", action="store_true", help="Expose the Nexys4 DDR board temperature sensor pins as a LiteX I2C master.")
    parser.add_target_argument("--with-ps2-keyboard", action="store_true", help="Expose Nexys4 DDR USB-HID/PS2 keyboard clk/dat as an IRQ-capable LiteX GPIO tristate bank.")
    parser.add_target_argument("--with-ps2-selftest", action="store_true", help="Diagnostic only: feed ps2-gpio from a fabric-generated PS/2 Set-2 A make/break waveform instead of external pins.")
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
        with_xadc=args.with_xadc,
        with_temp_i2c=args.with_temp_i2c,
        with_ps2_keyboard=args.with_ps2_keyboard,
        with_ps2_selftest=args.with_ps2_selftest,
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
