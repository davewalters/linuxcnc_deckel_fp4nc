#!usr/bin/env python3

import hal
import linuxcnc
import time
import math

# Create a new component
fp4_gearbox = hal.component("fp4_gearbox")
c = linuxcnc.command()

# Inputs

# Gearshift microswitches
fp4_gearbox.newpin("gearbox_microswitch_S36", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S37", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S38", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S39", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S40", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S41", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S42", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S43", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_microswitch_S44", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("gearbox_hirange_state", hal.HAL_BIT, hal.HAL_IN)

# Spindle jog parameters
fp4_gearbox.newpin("spindle_jog_motor_frequency", hal.HAL_FLOAT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_jog_period", hal.HAL_FLOAT, hal.HAL_IN)

# Gearshift time limit - per gearshift motor
fp4_gearbox.newpin("max_shift_time", hal.HAL_FLOAT, hal.HAL_IN)

# Spindle Motor Active
fp4_gearbox.newpin("spindle_run_vfd2_DI1", hal.HAL_BIT, hal.HAL_IN)

# Spindle states and setpoints
fp4_gearbox.newpin("spindle_cw_run", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_ccw_run", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_on", hal.HAL_BIT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_cmd_rps", hal.HAL_FLOAT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_speed_out_rps", hal.HAL_FLOAT, hal.HAL_IN)
fp4_gearbox.newpin("spindle_actual_speed_rps", hal.HAL_FLOAT, hal.HAL_IN)

# Tool change request
fp4_gearbox.newpin("safe_tool_change_request", hal.HAL_BIT, hal.HAL_IN)

# Outputs connected to HAL signals
# Gearshift motor relays
fp4_gearbox.newpin("gearbox_motor_M5_relay_K13", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("gearbox_motor_M6_relay_K14", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("gearbox_motor_M7_relay_K15", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("gearbox_motors_rev_relay_K16", hal.HAL_BIT, hal.HAL_OUT)

# Errors and  states
fp4_gearbox.newpin("gearshift_is_error", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("gearshift_error_code", hal.HAL_U32, hal.HAL_OUT)
fp4_gearbox.newpin("gearshift_is_blocking", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("gearshift_is_blocking_not", hal.HAL_BIT, hal.HAL_OUT)
fp4_gearbox.newpin("state_machine_state", hal.HAL_FLOAT, hal.HAL_OUT)

# VFD voltage, gear ratio, nominal output speed, previous spindle_cmd 
fp4_gearbox.newpin("spindle_vfd2_analog_nom", hal.HAL_FLOAT, hal.HAL_OUT)
fp4_gearbox.newpin("gear_ratio", hal.HAL_FLOAT, hal.HAL_OUT)
fp4_gearbox.newpin("gearbox_output_speed", hal.HAL_FLOAT, hal.HAL_OUT)
fp4_gearbox.newpin("spindle_cmd_rps_old", hal.HAL_FLOAT, hal.HAL_OUT)
fp4_gearbox.newpin("spindle_speed_override", hal.HAL_FLOAT, hal.HAL_OUT)

# Ready the component
fp4_gearbox.ready()

class MicroSwitch:
    def __init__(self, id, comp, hal_pin_name):
        self.id = id
        self.comp = comp
        self.hal_pin = hal_pin_name
        self.state = False

    def get_state(self):
        self.state = self.comp[self.hal_pin]
        return self.state
    
    def get_id(self):
        return self.id

class Relay:
    def __init__(self, id, comp, hal_pin_name):
        self.id = id
        self.comp = comp
        self.state = False
        self.hal_pin = hal_pin_name

    def activate(self):
        self.state = True
        self.comp[self.hal_pin] = True
    
    def deactivate(self):
        self.state = False
        self.comp[self.hal_pin] = False

class GearMotor:
    def __init__(self, motor_id, comp, switch_ids, switch_pin_names, run_relay_id, run_relay_pin, ccw_relay_id, ccw_relay_pin):
        self.id = motor_id
        self.switches = [MicroSwitch(sid, comp, pin_name) for sid, pin_name in zip(switch_ids, switch_pin_names)]
        self.run_relay = Relay(run_relay_id, comp, run_relay_pin)
        self.ccw_relay = Relay(ccw_relay_id, comp, ccw_relay_pin)
        self.last_known_switch_id = None
        self.active_switch_id = None
        self.active_switch_count = 0
        self.direction = "cw"
        self.run_state = False
        self.target_switch_id = None
        self.on_target = False
        self.fake_position = None

    def set_direction(self):
        if self.direction == "ccw":
            self.ccw_relay.activate()
        else:
            self.ccw_relay.deactivate()

    def set_run_state(self, state):
        if state is True:
            self.run_relay.activate()
        else:
            self.run_relay.deactivate()
        self.run_state = state

    def get_active_switch(self):
        self.active_switch_count = 0
        self.update_switch_states()
        for switch in self.switches:
            if switch.state is True:
                self.active_switch_id = switch.id
                self.active_switch_count +=1
                self.last_known_switch_id = switch.id
            else:
                self.active_switch = None

    def switch_direction(self):
        if self.direction == "cw":
            self.direction = "ccw"
        else:
            self.direction = "cw"

    def set_position(self):
        self.get_active_switch()
        if self.active_switch_count > 0 and self.active_switch_id == self.target_switch_id:
            print("Target switch is reached: active_switch_id: " + str(self.active_switch_id) + " target_switch_id: " + str(self.target_switch_id))
            self.set_run_state(False)
            self.on_target = True
        else:
            self.on_target = False
            self.set_run_state(True)

    def update_switch_states(self):
        for switch in self.switches:
            switch.get_state()
 
class SpindleMotor:
    def __init__(self):
        self.max_frequency = 50
        self.max_rpm = 3000
        self.max_volts = 10
        self.gain = self.max_volts / self.max_rpm      #V/rpm
        self.jog_state = None
        self.jog_motor_frequency = 0.0
        self.jog_period = 1.0
        self.jog_start_time = None
        self.jog_timer = None
        self.jog_voltage_amplitude = 0.0
        self.jog_omega = (2 * math.pi) / self.jog_period
        self.stopping_time = 0
        self.max_stopping_time = 5.0   #s
        self.stopping_timer_start = None
        self.stopped_speed_rps = 0.4
        self.analog_voltage = 0.0
        self.spindle_actual_speed_rps = 0
        self.target_rpm = 0
    
    def set_spindle_motor_rpm(self, spindle_cmd_rps, gearbox_output_speed, hi_range_ratio):
        #determine motor rpm to achieve spindle speed given hi-range ratio and gearbox output speed
        if gearbox_output_speed == 0:
            self.target_rpm = 0
        else:
            gearbox_setpoint = abs(spindle_cmd_rps) * 60 / hi_range_ratio
            self.target_rpm = (gearbox_setpoint / gearbox_output_speed) * self.max_rpm
            self.target_rpm = int((max(0, min(self.target_rpm, self.max_rpm))))
        print("spindle motor rpm: " + str(self.target_rpm))
        return True

    def set_spindle_motor_frequency(self):
        self.target_frequency = (self.target_rpm / self.max_rpm) * self.max_frequency
        self.target_frequency = (max(0, min(self.target_frequency, self.max_frequency)))
        return True
    
    def stop_motor(self):
        self.set_vfd_analog_voltage(0, True)
        self.stopping_timer_start = time.time()

    def is_stopped(self):
        if abs(self.spindle_actual_speed_rps) < self.stopped_speed_rps or \
            self.stopping_timer_expired():
            self.stopping_time = 0
            return True
        else:
            self.stopping_time = time.time() - self.stopping_timer_start
            return False
        
    def stopping_timer_expired(self):
        if self.stopping_time > self.max_stopping_time:
            return True
        else:
            return False
    
    def activate_jog(self):
        self.jog_state = True
        self.jog_start_time = time.time()
    
    def deactivate_jog(self):
        self.jog_state = False
        self.update_jog_voltage()

    def set_vfd_analog_voltage(self, target_rpm, run_cw):
        if run_cw:
            self.analog_voltage = max(0, min(self.gain * target_rpm, self.max_volts))
        else:
            self.analog_voltage = -max(0, min(self.gain * target_rpm, self.max_volts))
    
    def cleanup(self):
        self.deactivate_jog()
        self.stop_motor()
        return True
    
    def abort(self):
        self.stop_motor()
        return True
    
    def update_jog_voltage(self):
        self.jog_voltage_amplitude = max(0, min((self.jog_motor_frequency / self.max_frequency) * self.max_volts, self.max_volts))
        self.jog_omega = (2 * math.pi) / self.jog_period
        if self.jog_state is True:
            t = time.time() - self.jog_start_time
            jog_voltage = self.jog_voltage_amplitude * math.sin(self.jog_omega * t)
            self.analog_voltage = jog_voltage
        else:
            self.analog_voltage = 0.0

class SpindleMotorState():
    def __init__(self):
        self.motor_active_state = False

    def is_motor_active(self):
        return self.motor_active_state
    
    def update_input_pins(self):
        self.motor_active_state = fp4_gearbox['spindle_run_vfd2_DI1']
    

class Gearbox:
    def __init__(self, sm_state):
        self.gearbox_output_speed = None
        self.gearshift_is_error = None
        self.switch_targets = None
        self.hirange_state = None
        self.hirange_ratio = 1.0
        self.is_blocking = False
        self.is_blocking_not = True
        self.is_shifting_state = False
        self.sm_state = sm_state
        self.shift_start_time = None
        self.max_shift_time = 1.0
        self.abort_error_code = 0
        m5_switch_hal_pins = ['gearbox_microswitch_S36', 'gearbox_microswitch_S37', 'gearbox_microswitch_S38']
        m6_switch_hal_pins = ['gearbox_microswitch_S39', 'gearbox_microswitch_S40', 'gearbox_microswitch_S41']
        m7_switch_hal_pins = ['gearbox_microswitch_S42', 'gearbox_microswitch_S43', 'gearbox_microswitch_S44']
        
        #gearmotor ID, comp, microswitch ids (3), switch_hal_pins (3), run relay_id, run_relay_hal_pin, ccw relay, ccw_relay_hal_pin     
        self.gearmotors = {
            5: GearMotor(5, fp4_gearbox, range(36, 39), m5_switch_hal_pins, 13, 'gearbox_motor_M5_relay_K13', 16, 'gearbox_motors_rev_relay_K16'),
            6: GearMotor(6, fp4_gearbox, range(39, 42), m6_switch_hal_pins, 14, 'gearbox_motor_M6_relay_K14', 16, 'gearbox_motors_rev_relay_K16'),
            7: GearMotor(7, fp4_gearbox, range(42, 45), m7_switch_hal_pins, 15, 'gearbox_motor_M7_relay_K15', 16, 'gearbox_motors_rev_relay_K16')
        }
        self.shift_sequence = [5, 6, 7]
        self.shift_sequence_index = 0

        self.speed_table = {
            # Format: speed: [M5_position, M6_position, M7_position]
            # M5: S36 = 0, S37 = 1, S38 = 2
            # M6: S39 = 0, S40 = 1, S41 = 2
            # M7: S42 = 0, S43 = 1, S44 = 2
            0:[38,41,44],
            63:[38,41,43],
            80:[37,41,43],
            100:[36,41,43],
            125:[38,40,43],
            150:[37,40,43],
            200:[36,40,43],
            250:[38,39,43],
            315:[37,39,43],
            400:[36,39,43],
            500:[38,41,42],
            630:[37,41,42],
            800:[36,41,42],
            1000:[38,40,42],
            1250:[37,40,42],
            1600:[36,40,42],
            2000:[38,39,42],
            2500:[37,39,42],
            3150:[36,39,42]
        }
    
    def blocking(self, state):
        if state == True:
            self.is_blocking = True
            self.is_blocking_not = False
        else:
            self.is_blocking = False
            self.is_blocking_not = True
    
    def sum_active_switch_count(self):
        self.active_switch_sum = 0
        for gearmotor in self.gearmotors.values():
            self.active_switch_sum += gearmotor.active_switch_count

    def set_hirange_ratio(self):
        if self.hirange_state:
            self.hirange_ratio = 2.0
        else:
            self.hirange_ratio = 1.0
    
    def get_gearbox_output_speed(self, spindle_cmd_rps):
        #determine nominal gearbox speed at 50Hz = smallest speed >= spindle_speed
        #direction is dealt with outside gearbox by sign of vfd analog 
        print("spindle_cmd_rps: " + str(spindle_cmd_rps))
        print("hirange_ratio: " + str(self.hirange_ratio))
        gearbox_speed_setpoint = int(abs(spindle_cmd_rps) * 60 / self.hirange_ratio)
        gearbox_speed_setpoint = max(0, min(3150, gearbox_speed_setpoint))
        print("gearbox_speed_setpoint: " + str(gearbox_speed_setpoint))
        eligible_speeds = [speed for speed in self.speed_table if speed >= gearbox_speed_setpoint]
        self.gearbox_output_speed = min(eligible_speeds) if eligible_speeds else None

    def get_switch_targets(self):
        self.switch_targets = self.speed_table.get(self.gearbox_output_speed)
        self.gearmotors[5].target_switch_id = self.switch_targets[0]
        self.gearmotors[6].target_switch_id = self.switch_targets[1]
        self.gearmotors[7].target_switch_id = self.switch_targets[2]
        print("Switch targets: " + str(self.switch_targets[0]) + ", " + str(self.switch_targets[1]) + ", " + str(self.switch_targets[2]))

    def reverse_gearmotor_direction(self):
        for gearmotor in self.gearmotors.values():
            gearmotor.switch_direction()
    
    def check_shift_status(self):
        shift_status = 0
        for gearmotor in self.gearmotors.values():
            gearmotor.get_active_switch()
            if gearmotor.active_switch_id == gearmotor.target_switch_id:
                shift_status +=1
        if shift_status > 2:
            return True
        else:
            self.abort_error_code +=4
            return False
        
    def is_indeterminate(self):
        for gearmotor in self.gearmotors.values():
            gearmotor.get_active_switch()
        self.sum_active_switch_count()
        if self.active_switch_sum < 2:
            return True
        else:
            return False
            
    def set_shift_sequence(self):
        # If there is one motor in an indeterminate state, we should shift that one first
        # Could occur after an e-stop or a failed shift attempt
        if self.gearmotors[6].active_switch_id == None:
            self.shift_sequence = [6, 5, 7]
        elif self.gearmotors[7].active_switch_id == None:
            self.shift_sequence = [7, 5, 6]
        else:
            self.shift_sequence = [5, 6, 7]
        print("shift sequence: " + str(self.shift_sequence))
           
    def set_shift_actions(self, spindle_cmd_rps):
        self.set_hirange_ratio()
        # determine the gearbox output speed and switch target positions
        self.get_gearbox_output_speed(spindle_cmd_rps)
        self.get_switch_targets()
        # If the gearbox is in an indeterminate state, don't shift
        if self.is_indeterminate():
            self.is_shifting_state = False
            self.abort_error_code +=2
            return False
        else:
            self.set_shift_sequence()        
            self.is_shifting_state = True
            self.shift_start_time = time.time()
            return True
        
    def is_shifting(self):
        if self.is_shifting_state == True:
            return True
        
    def continue_shifting(self):
        if self.sm_state.is_motor_active() is False:
            self.abort_error_code +=1
            self.is_shifting_state = False
            return False
        else:
            gearmotor_id = self.shift_sequence[self.shift_sequence_index]
            self.gearmotors[gearmotor_id].set_position()
            self.elapsed_shift_time = time.time() - self.shift_start_time

            if self.gearmotors[gearmotor_id].on_target is True:
                self.shift_sequence_index +=1
                self.shift_start_time = time.time()

            if self.shift_sequence_index > 2:
                self.is_shifting_state = False
                self.abort_error_code = 0
                self.shift_sequence_index = 0
                self.elapsed_shift_time = 0
                
            if self.elapsed_shift_time > self.max_shift_time:
                self.abort_error_code += 8
                self.is_shifting_state = False

            return True

    def report_success(self):
        self.gearshift_is_error = False
        self.blocking(False)
        self.abort_error_code = 0
    
    def report_failure(self):
        self.gearshift_is_error = True
        self.blocking(True)
        print("Abort error code: " + str(self.abort_error_code))
        
    def cleanup(self):
        for gearmotor in self.gearmotors.values():
            gearmotor.set_run_state(False)
        self.report_success()
        return True
        
    def abort(self):
        for gearmotor in self.gearmotors.values():
            gearmotor.set_run_state(False)
        self.report_failure()
        

class GearboxStateMachine:
    def __init__(self, sm_state):
        self.sm_state = sm_state
        self.spindle_cw_run = False
        self.spindle_ccw_run = False
        self.spindle_on = False
        self.spindle_cmd_rps = 0
        self.spindle_cmd_rps_old = 0
        self.spindle_speed_out_rps = 0
        self.spindle_speed_override = 1
        self.safe_tool_change_request = None
        self.gear_ratio = 0
        self.shift_attempts = 0
        self.max_shift_attempts = 4
        self.state = "INHIBIT"
        self.previous_state = "NULL"
                
        # Instantiate Gearbox and Spindle Motor Objects
        self.gb = Gearbox(sm_state)
        self.sm = SpindleMotor()

    def get_gearbox_ratio(self):
        self.gear_ratio = self.gb.gearbox_output_speed / self.sm.max_rpm
    
    def is_safe_tool_change_request(self):
        return self.safe_tool_change_request
        
    def change_gears(self):
        #if speed == 0 and no tool change requested, no need to change gears - just set motor speed to 0
        #if gearbox_output_speed != 0 and tool change requested,  change gears to put the gearbox in neutral for safety
        #otherwise, if speed setpoint has changed, change gears
        
        self.spindle_cmd_rps = fp4_gearbox['spindle_cmd_rps']
        self.gb.set_hirange_ratio()
        self.gb.get_gearbox_output_speed(self.spindle_cmd_rps)

        if self.safe_tool_change_request:
            if (self.gb.gearbox_output_speed or 0) != 0:
                print("Tool change active and gearbox not in neutral - shifting to Neutral")
                return True
            else:
                #Already in neutral, hold state
                return False 
        #Allow normal gear shifts only when no tool change request is active
        if abs(self.spindle_cmd_rps) != abs(self.spindle_cmd_rps_old):
            return True
        
        return False

        
    def spindle_run_forwards(self):
        self.spindle_cmd_rps = fp4_gearbox['spindle_cmd_rps']
        if abs(self.spindle_cmd_rps) == abs(self.spindle_cmd_rps_old) and \
                self.spindle_cw_run is True:
            return True
        
    def spindle_run_reverse(self):
        self.spindle_cmd_rps = fp4_gearbox['spindle_cmd_rps']
        if abs(self.spindle_cmd_rps) == abs(self.spindle_cmd_rps_old) and \
                self.spindle_ccw_run is True:
            return True
    
    def is_spindle_stop(self):
        if self.spindle_on is False:
            return True
        
    def get_spindle_speed_override(self):
        #if self.spindle_cmd_rps != 0:
        #    self.spindle_speed_override = max(0, min((self.spindle_speed_out_rps / self.spindle_cmd_rps , 1)))
        #else:
        #    self.spindle_speed_override = 1
        self.spindle_speed_override = 1
        
    def update(self):
        if self.state != self.previous_state:
            print("State: " + str(self.state))
            self.previous_state = self.state

        if self.state == "INHIBIT":
            if self.sm_state.is_motor_active() is True:
                self.sm.stop_motor()
                self.state = "MOTOR_ZERO_SPEED"
            else:
                self.state = "INHIBIT"

        elif self.state == "MOTOR_STOPPING":
            self.sm.stop_motor()
            if self.sm.is_stopped():
                self.state = "MOTOR_ZERO_SPEED"

        elif self.state == "MOTOR_ZERO_SPEED":
            if self.sm_state.is_motor_active() is False:
                self.state = "INHIBIT"
            
            elif self.change_gears():
                self.state = "SET_SHIFT_ACTIONS"

            elif self.spindle_run_reverse():
                self.state = "SPINDLE_CCW_RUN"

            elif self.spindle_run_forwards():
                self.state = "SPINDLE_CW_RUN"

            else:
                self.state = "MOTOR_ZERO_SPEED"

        elif self.state == "SET_SHIFT_ACTIONS":
            self.gb.blocking(True)
            self.spindle_speed_override = 1
            if self.safe_tool_change_request:
                self.spindle_cmd_rps = 0.0
                shift_actions = self.gb.set_shift_actions(0.0)
            else:
                shift_actions = self.gb.set_shift_actions(self.spindle_cmd_rps)
                       
            if shift_actions:
                self.sm.activate_jog()
                self.state = "SHIFTING"
            else:
                self.state = "ABORT"

        elif self.state == "SHIFTING":
            if self.gb.is_shifting():
                self.sm.update_jog_voltage()
                if self.gb.continue_shifting() is False:
                    self.state = "ABORT"
            else:
                self.state = "CHECK_SHIFT_STATUS"

        elif self.state == "CHECK_SHIFT_STATUS":
            self.sm.deactivate_jog()
            self.get_gearbox_ratio()
            if self.gb.check_shift_status():
                if self.safe_tool_change_request:
                    self.state = "TOOL_CHANGE_HOLD"
                else:
                    self.state = "SET_SPINDLE_MOTOR_SPEED"
            else:
                self.state = "ABORT"

        elif self.state =="TOOL_CHANGE_HOLD":
            if not self.safe_tool_change_request:
                self.spindle_cmd_rps = fp4_gearbox['spindle_cmd_rps']
                self.state = "SET_SHIFT_ACTIONS"
            else:
                pass
               
        elif self.state == "SET_SPINDLE_MOTOR_SPEED":
            if self.sm.set_spindle_motor_rpm(self.spindle_cmd_rps, self.gb.gearbox_output_speed, self.gb.hirange_ratio) and \
                self.sm.set_spindle_motor_frequency():
                self.state = "DONE"
            else:
                self.state = "ABORT"

        elif self.state == "DONE":
            self.gb.cleanup()
            self.sm.cleanup()
            self.gb.blocking(False)
            if not self.safe_tool_change_request:
                self.spindle_cmd_rps = fp4_gearbox['spindle_cmd_rps']
                if (self.gb.gearbox_output_speed or 0) != 0:
                    self.spindle_cmd_rps_old = self.spindle_cmd_rps
                else:
                    self.spindle_cmd_rps_old = 0.0
                        
            self.state = "MOTOR_STOPPING"

        elif self.state == "ABORT":
            self.gb.abort()
            self.sm.abort()
            self.gb.blocking(True)
            if self.shift_attempts < self.max_shift_attempts:
                self.state = "MOTOR_STOPPING"
            else:
                self.state = "FAILED"

        elif self.state == "FAILED":
            c.display_msg('fp4_gearbox.py: Gearshift failed. Estop and Activate to reset')
            print("Gearshift FAILED after : " + str(self.shift_attempts) + " shift attempts")
            if self.sm_state.is_motor_active() is False:
                self.state = "INHIBIT"

        elif self.state == "SPINDLE_CCW_RUN":
            self.sm.set_vfd_analog_voltage(self.sm.target_rpm, False)
            self.get_spindle_speed_override()

            if self.sm_state.is_motor_active() is False:
                self.state = "INHIBIT"

            elif self.change_gears() or self.is_spindle_stop():
                self.state = "MOTOR_STOPPING"
            
            elif self.spindle_run_forwards():
                self.state = "SPINDLE_CW_RUN"

        elif self.state == "SPINDLE_CW_RUN":
            self.sm.set_vfd_analog_voltage(self.sm.target_rpm, True)
            self.get_spindle_speed_override()

            if self.sm_state.is_motor_active() is False:
                self.state = "INHIBIT"

            elif self.change_gears() or self.is_spindle_stop():
                self.state = "MOTOR_STOPPING"
            
            elif self.spindle_run_reverse():
                self.state = "SPINDLE_CCW_RUN"

    def update_output_pins(self):
        if self.state == "INHIBIT":
            fp4_gearbox['state_machine_state'] = 0.0

        elif self.state == "MOTOR_ZERO_SPEED":
            fp4_gearbox['state_machine_state'] = 1.0

        elif self.state == "SET_SHIFT_ACTIONS":
            fp4_gearbox['state_machine_state'] = 2.1

        elif self.state == "SHIFTING":
            fp4_gearbox['state_machine_state'] = 2.2

        elif self.state == "CHECK_SHIFT_STATUS":
            fp4_gearbox['state_machine_state'] = 2.3

        elif self.state == "SET_SPINDLE_MOTOR_SPEED":
            fp4_gearbox['state_machine_state'] = 2.4

        elif self.state == "DONE":
            fp4_gearbox['state_machine_state'] = 2.5

        elif self.state == "ABORT":
            fp4_gearbox['state_machine_state'] = 2.6

        elif self.state == "FAILED":
            fp4_gearbox['state_machine_state'] = 2.7

        elif self.state == "TOOL_CHANGE_HOLD":
            fp4_gearbox['state_machine_state'] = 2.8

        elif self.state == "SPINDLE_CW_RUN":
            fp4_gearbox['state_machine_state'] = 3.0

        elif self.state == "SPINDLE_CCW_RUN":
            fp4_gearbox['state_machine_state'] = 4.0

        elif self.state == "MOTOR_STOPPING":
            fp4_gearbox['state_machine_state'] = 5.0

        fp4_gearbox['spindle_cmd_rps_old'] = self.spindle_cmd_rps_old
        fp4_gearbox['spindle_speed_override'] = self.spindle_speed_override
        fp4_gearbox['gearshift_is_error'] = self.gb.gearshift_is_error
        fp4_gearbox['gearshift_error_code'] = self.gb.abort_error_code
        fp4_gearbox['gearshift_is_blocking'] = self.gb.is_blocking
        fp4_gearbox['gearshift_is_blocking_not'] = self.gb.is_blocking_not
        fp4_gearbox['spindle_vfd2_analog_nom'] = self.sm.analog_voltage
        fp4_gearbox['gear_ratio'] = self.gear_ratio
        if self.gb.gearbox_output_speed is None:
            fp4_gearbox['gearbox_output_speed'] = -1
        else:
            fp4_gearbox['gearbox_output_speed'] = self.gb.gearbox_output_speed
        
    def update_input_pins(self):
        self.safe_tool_change_request = fp4_gearbox['safe_tool_change_request']
        self.spindle_cw_run = fp4_gearbox['spindle_cw_run']
        self.spindle_ccw_run = fp4_gearbox['spindle_ccw_run']
        self.spindle_on = fp4_gearbox['spindle_on']
        self.spindle_speed_out_rps = fp4_gearbox['spindle_speed_out_rps']
        self.sm.spindle_actual_speed_rps = fp4_gearbox['spindle_actual_speed_rps']
        self.sm.jog_motor_frequency = fp4_gearbox['spindle_jog_motor_frequency']
        self.sm.jog_period = max(1.0, fp4_gearbox['spindle_jog_period'])
        self.gb.max_shift_time = fp4_gearbox['max_shift_time']
        self.gb.hirange_state = fp4_gearbox['gearbox_hirange_state']
        
# Main loop
        
# Instantiate the state machine        
sm_state = SpindleMotorState()
gbsm = GearboxStateMachine(sm_state)

try:
    while True:
        sm_state.update_input_pins()
        gbsm.update_input_pins()
        gbsm.update()
        gbsm.update_output_pins()
        time.sleep(0.1)
except KeyboardInterrupt:
    raise SystemExit
            
            

            







   
