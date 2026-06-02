set bitstream [file normalize "build/litex_nexys4ddr/gateware/digilent_nexys4ddr.bit"]
if {![file exists $bitstream]} {
    error "Missing bitstream: $bitstream. Run scripts/build_litex_nexys4ddr.sh first."
}

puts "LITEX_PROGRAM_ATTEMPT=1 BITSTREAM=$bitstream"
open_hw_manager
connect_hw_server -allow_non_jtag
open_hw_target

set devs [get_hw_devices xc7a100t*]
if {[llength $devs] == 0} {
    error "No xc7a100t hardware device found"
}
set dev [lindex $devs 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bitstream $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes false $dev
puts "LITEX_PROGRAMMED=$dev BITSTREAM=$bitstream"
close_hw_manager
