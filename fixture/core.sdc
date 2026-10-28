# Timing constraints of the generated cores (OpenLane 2 PNR and sign-off SDC), based on the OpenLane default constraints.
# Clock uncertainty: OpenLane's 0.25 ns for setup (irrelevant at the 10 us period) but 0.05 ns for hold: a same-edge hold check
# sees no jitter, the skew is computed from the propagated clocks and on-chip variation is covered by the 5 % timing derate
# (0.25 ns would make every short register-to-register path a hold-repair target).
set clock_port __VIRTUAL_CLK__
if { [info exists ::env(CLOCK_PORT)] } {
    set ::clock_port [lindex $::env(CLOCK_PORT) 0]
}
set port_args [get_ports $clock_port]
create_clock {*}$port_args -name $clock_port -period $::env(CLOCK_PERIOD)

set input_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
set output_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } { set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design] }
if { [info exists ::env(MAX_CAPACITANCE_CONSTRAINT)] } { set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design] }

set clk_input [get_port $clock_port]
set clk_indx [lsearch [all_inputs] $clk_input]
set all_inputs_wo_clk [lreplace [all_inputs] $clk_indx $clk_indx ""]
# reset is held for many cycles: no synchronous timing on it
set idx [lsearch $all_inputs_wo_clk [get_ports reset]]
if { $idx >= 0 } { set all_inputs_wo_clk [lreplace $all_inputs_wo_clk $idx $idx ""] }
set_false_path -from [get_ports reset]
set clocks [get_clocks $clock_port]
set_input_delay $input_delay_value -clock $clocks $all_inputs_wo_clk
set_output_delay $output_delay_value -clock $clocks [all_outputs]

if { ![info exists ::env(SYNTH_CLK_DRIVING_CELL)] } { set ::env(SYNTH_CLK_DRIVING_CELL) $::env(SYNTH_DRIVING_CELL) }
set_driving_cell -lib_cell [lindex [split $::env(SYNTH_DRIVING_CELL) "/"] 0] -pin [lindex [split $::env(SYNTH_DRIVING_CELL) "/"] 1] $all_inputs_wo_clk
set_driving_cell -lib_cell [lindex [split $::env(SYNTH_CLK_DRIVING_CELL) "/"] 0] -pin [lindex [split $::env(SYNTH_CLK_DRIVING_CELL) "/"] 1] $clk_input
set cap_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0]
set_load $cap_load [all_outputs]
set_clock_uncertainty -setup $::env(CLOCK_UNCERTAINTY_CONSTRAINT) $clocks
set_clock_uncertainty -hold 0.05 $clocks
set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) $clocks
set_timing_derate -early [expr 1-[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late [expr 1+[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
# Hold between register banks. The banks behind their own clock gates (input counters; layer-1 accumulators; s1, delay lines and
# layer-1 membranes; s2 and layer-2 membranes; read-out) are clocked in mutually exclusive states of the controller: the bank that
# launches a transfer is never clocked in the cycle in which the receiving bank captures it (counters: event cycles and S1;
# accumulators: L1; s1 bank: S1 and CLR; s2 bank: L2 and CLR; read-out: L3 and CLR), and in the one shared state (CLR) the D input
# of the receiving register is held at zero by the clear during the whole cycle. These transfers have no hold requirement, so hold
# is not checked between the gated clocks of different banks (setup is). Hold within a bank and from the controller is checked.
foreach icg [get_cells -quiet u_icg_c*] {
    set n [get_full_name $icg]
    create_generated_clock -name gclk_[string range $n 6 end] -source [get_pins $n/CLK] -divide_by 1 [get_pins $n/GCLK]
}
foreach b {a1 s1 s2 o} {
    if { [llength [get_cells -quiet u_icg_$b]] } {
        create_generated_clock -name gclk_$b -source [get_pins u_icg_$b/CLK] -divide_by 1 [get_pins u_icg_$b/GCLK]
    }
}
set_false_path -hold -from [get_clocks gclk_c*] -to [get_clocks gclk_a1]
set_false_path -hold -from [get_clocks gclk_a1] -to [get_clocks gclk_s1]
set_false_path -hold -from [get_clocks gclk_s1] -to [get_clocks gclk_s2]
set_false_path -hold -from [get_clocks gclk_s2] -to [get_clocks {gclk_o gclk_s1}]

if { [info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS) } {
    unset_propagated_clock [all_clocks]
} else {
    set_propagated_clock [all_clocks]
}
