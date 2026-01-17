#!usr/bin/env python3

#import hal
import time

class MicroSwitch:
    def __init__(self, id):
        self.id = id
        self.state = False

    def set_state(self, state):
        self.state = state
    
    def get_state(self):
        return self.state
    
    def get_id(self):
        return self.id

class Relay:
    def __init__(self,id):
        self.id = id
        self.state = False

    def activate(self):
        self.state = True
    
    def deactivate(self):
        self.state = False

class GearMotor:
    def __init__(self, id, switch_ids, run_relay_id, ccw_relay_id):
        self.id = id
        self.switches = [MicroSwitch(sid) for sid in switch_ids]
        self.run_relay = Relay(run_relay_id)
        self.ccw_relay = Relay(ccw_relay_id)
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
        if state:
            self.run_relay.activate()
        else:
            self.run_relay.deactivate()
        self.run_state = state

    def get_active_switch(self):
        self.active_switch_count = 0
        for switch in self.switches:
            #print("get_active_switch ...")
            #print("switch.id: " + str(switch.id))
            #print("switch.state: " + str(switch.state))
            if switch.state is True:
                self.active_switch_id = switch.id
                self.active_switch_count +=1
                self.last_known_switch_id = switch.id
            else:
                self.active_switch = None
    
    def get_direction(self):
        if self.last_known_switch_id == None:
            self.direction = "cw"
            #print("last_known_switch = None; defaulting to cw direction")
        else:
            ccw_distance = (self.target_switch_id - self.last_known_switch_id + 3) % 3
            cw_distance = 3 - ccw_distance
            #print("target_switch_id: " + str(self.target_switch_id))
            #print("last_known_switch_id: " + str(self.last_known_switch_id))
            #print("cw_distance: " + str(cw_distance))
            #print("ccw_distance: " + str(ccw_distance))
            if cw_distance < ccw_distance:
                self.direction = "cw"
            else:
                self.direction = "ccw"

    def set_position(self):
        self.fake_position_update()
        self.get_active_switch()
        if self.active_switch_count > 0 and self.active_switch_id == self.target_switch_id:
            print("Target switch is reached")
            self.set_run_state(False)
            self.on_target = True
        else:
            self.on_target = False
            self.get_direction()
            self.set_direction()
            self.set_run_state(True)

    def fake_position_update(self):
        if self.run_relay.state == True and self.ccw_relay.state == True:
            self.fake_position +=1
        elif self.run_relay.state == True and self.ccw_relay.state == False:
            self.fake_position -=1
        #bound to -180 to + 180 deg
        self.fake_position = self.fake_position % 360
        if self.fake_position > 180:
            self.fake_position -=360
        self.update_fake_switches()

    def update_fake_switches(self):
        if self.fake_position == 0:
            self.switches[0].set_state(True)
        else:
            self.switches[0].set_state(False) 

        if self.fake_position == 120:
            self.switches[1].set_state(True)
        else:
            self.switches[1].set_state(False)
            
        if self.fake_position == -120:
            self.switches[2].set_state(True)
        else:
            self.switches[2].set_state(False)
 
class SpindleMotor:
    def __init__(self, max_frequency, max_rpm, max_volts):
        self.max_frequency = max_frequency
        self.max_rpm = max_rpm
        self.max_volts = max_volts
        self.gain = self.max_volts / self.max_rpm       #V/rpm
    
    def set_spindle_motor_rpm(self, spindle_speed_setpoint, gearbox_output_speed, hi_range_ratio):
        #determine motor rpm to achieve spindle speed given hi-range ratio and gearbox output speed
        gearbox_setpoint = spindle_speed_setpoint / hi_range_ratio
        self.target_rpm = (gearbox_setpoint / gearbox_output_speed) * self.max_rpm
        self.target_rpm = int((max(0, min(self.target_rpm, self.max_rpm))))
        print("spindle motor rpm: " + str(self.target_rpm))
        return True

    def set_spindle_motor_frequency(self):
        self.target_frequency = (self.target_rpm / self.max_rpm) * self.max_frequency
        self.target_frequency = (max(0, min(self.target_frequency, self.max_frequency)))
        return True
    
    def reset_states(self):
        return True

class Gearbox:
    def __init__(self):
        self.old_spindle_speed_setpoint = 0.0
        self.spindle_speed_setpoint = 0.0
        self.gearbox_output_speed = None
        self.switch_targets = None
        self.hirange_ratio = 1.0
        self.is_shifting_state = False
        self.shift_start_time = None
        self.max_shift_time = .5  #s
        self.abort_error_code = 0
        #gearmotor ID, microswitch ids (3), run relay, ccw relay        
        self.gearmotors = {
            5: GearMotor(5, range(36, 39), 13, 16),
            6: GearMotor(6, range(39, 42), 14, 16),
            7: GearMotor(7, range(42, 45), 15, 16)
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
    
    def sum_active_switch_count(self):
        self.active_switch_sum = 0
        for gearmotor in self.gearmotors.values():
            self.active_switch_sum += gearmotor.active_switch_count

    def set_hirange_ratio(self, hirange_state):
        if hirange_state:
            self.hirange_ratio = 2.0
        else:
            self.hirange_ratio = 1.0
    
    def get_gearbox_output_speed(self, spindle_speed_setpoint, hirange_ratio):
        #determine nominal gearbox speed at 50Hz = smallest speed >= spindle_speed
        #direction is dealt with outside gearbox by sign of spindle motor voltage
        print("spindle_speed_setpoint: " + str(spindle_speed_setpoint))
        print("hirange_ratio: " + str(hirange_ratio))

        gearbox_speed_setpoint = abs(spindle_speed_setpoint) / hirange_ratio
        gearbox_speed_setpoint = max(0, min(3150, gearbox_speed_setpoint))
        eligible_speeds = [speed for speed in self.speed_table if speed >= gearbox_speed_setpoint]
        self.gearbox_output_speed = min(eligible_speeds) if eligible_speeds else None

    def get_switch_targets(self):
        self.switch_targets = self.speed_table.get(self.gearbox_output_speed)
        self.gearmotors[5].target_switch_id = self.switch_targets[0]
        self.gearmotors[6].target_switch_id = self.switch_targets[1]
        self.gearmotors[7].target_switch_id = self.switch_targets[2]
        print("get_switch_targets: " + str(self.switch_targets[0]) + " " + str(self.switch_targets[1]) + " " + str(self.switch_targets[2]))
    
    def check_shift_status(self):
        shift_status = 0
        #self.update_switch_state()
        for gearmotor in self.gearmotors.values():
            gearmotor.update_fake_switches()
            gearmotor.get_active_switch()
            if gearmotor.active_switch_id == gearmotor.target_switch_id:
                shift_status +=1
        if shift_status > 2:
            return True
        else:
            self.abort_error_code +=4
            return False
        
    def update_switch_state(self):
        self.gearmotors[5].switches[36].set_state(fp4_gearbox['gearbox_microswitch_S36'])
        self.gearmotors[5].switches[37].set_state(fp4_gearbox['gearbox_microswitch_S37'])
        self.gearmotors[5].switches[38].set_state(fp4_gearbox['gearbox_microswitch_S38'])
        self.gearmotors[6].switches[39].set_state(fp4_gearbox['gearbox_microswitch_S39'])
        self.gearmotors[6].switches[40].set_state(fp4_gearbox['gearbox_microswitch_S40'])
        self.gearmotors[6].switches[41].set_state(fp4_gearbox['gearbox_microswitch_S41'])
        self.gearmotors[7].switches[42].set_state(fp4_gearbox['gearbox_microswitch_S42'])
        self.gearmotors[7].switches[43].set_state(fp4_gearbox['gearbox_microswitch_S43'])
        self.gearmotors[7].switches[44].set_state(fp4_gearbox['gearbox_microswitch_S44'])

    def request_shift(self):
        self.spindle_speed_setpoint = fp4_gearbox['spindle_speed_setpoint']
        if self.spindle_speed_setpoint != self.old_spindle_speed_setpoint:
            self.update_switch_state()
            self.set_hirange_ratio(fp4_gearbox['gearbox_hirange_state'])
            for gearmotor in self.gearmotors.values():
                gearmotor.get_active_switch() 
            return True
        else:
            return False
        
    def request_fake_shift(self):
        self.spindle_speed_setpoint = fp4_gearbox.spindle_speed_setpoint
        if self.spindle_speed_setpoint != self.old_spindle_speed_setpoint:
            self.set_hirange_ratio(fp4_gearbox.gearbox_hirange_state)
            for gearmotor in self.gearmotors.values():
                gearmotor.update_fake_switches()
            print("spindle_speed_setpoint: " + str(self.spindle_speed_setpoint))
            print("hirange_ratio: " + str(self.hirange_ratio))
            return True
        else:
            return False
        
    def is_indeterminate(self):
        self.gearmotors[5].get_active_switch()
        self.gearmotors[6].get_active_switch()
        self.gearmotors[7].get_active_switch()
        self.sum_active_switch_count()
        if self.active_switch_sum < 2:
            return True
        
    def set_shift_sequence(self):
        # If there is one motor in an indeterminate state, we should shift that one first
        # Could occur after an e-stop or a failed shift attempt
        self.gearmotors[6].get_active_switch()
        self.gearmotors[7].get_active_switch()
        if self.gearmotors[6].active_switch_id == None:
            self.shift_sequence = [6, 5, 7]
        elif self.gearmotors[7].active_switch_id == None:
            self.shift_sequence = [7, 5, 6]
        else:
            self.shift_sequence = [5, 6, 7]
        print("shift sequence: " + str(self.shift_sequence))
           
    def set_shift_actions(self):
        # determine the gearbox output speed and switch target positions
        self.get_gearbox_output_speed(self.spindle_speed_setpoint, self.hirange_ratio)
        self.get_switch_targets()
        # If the gearbox is in an indeterminate state, don't shift
        if self.is_indeterminate():
            self.is_shifting_state = False
            print("gearbox state indeterminate - shifting aborted")
            self.abort_error_code +=1
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
        gearmotor_id = self.shift_sequence[self.shift_sequence_index]
        #print("gearmotor_id = " + str(gearmotor_id))
        self.gearmotors[gearmotor_id].set_position()
        self.elapsed_shift_time = time.time() - self.shift_start_time
        if self.gearmotors[gearmotor_id].on_target is True:
            self.shift_sequence_index +=1
            self.shift_start_time = time.time()
            print("Gearmotor M5 position: " + str(gbsm.gb.gearmotors[5].fake_position))
            print("Gearmotor M6 position: " + str(gbsm.gb.gearmotors[6].fake_position))
            print("Gearmotor M7 position: " + str(gbsm.gb.gearmotors[7].fake_position))
        if self.shift_sequence_index > 2:
            self.is_shifting_state = False
            self.abort_error_code = 0
            self.shift_sequence_index = 0
            self.elapsed_shift_time = 0
        if self.elapsed_shift_time > self.max_shift_time:
            self.abort_error_code += 2
            self.is_shifting_state = False
        
    def reset_states(self):
        self.old_spindle_speed_setpoint = self.spindle_speed_setpoint
        for gearmotor in self.gearmotors.values():
            gearmotor.set_run_state(False)

        print("Gearmotor M5 position: " + str(gbsm.gb.gearmotors[5].fake_position))
        print("Gearmotor M6 position: " + str(gbsm.gb.gearmotors[6].fake_position))
        print("Gearmotor M7 position: " + str(gbsm.gb.gearmotors[7].fake_position))
        return True
        
    def abort(self):
        self.old_spindle_speed_setpoint = self.spindle_speed_setpoint
        for gearmotor in self.gearmotors.values():
            gearmotor.set_run_state(False)
        print("Abort error code: " + str(self.abort_error_code))
        self.abort_error_code = 0

    

class GearboxStateMachine:
    def __init__(self):
        self.state = "IDLE"
        # Instantiate Gearbox and Spindle Motor Objects
        self.gb = Gearbox()
        self.sm = SpindleMotor(50, 2900, 10)
        
    def update(self):
        if self.state == "IDLE":
            print("IDLE State")
            #if self.gb.request_shift():
            if self.gb.request_fake_shift():
                self.state = "SET_SHIFT_ACTIONS"
        
        elif self.state == "SET_SHIFT_ACTIONS":
            print("SET_SHIFT_ACTIONS State")
            if self.gb.set_shift_actions():
                self.state = "SHIFTING"
            else:
                self.state = "ABORT"

        elif self.state == "SHIFTING":
            #print("SHIFTING State")
            if self.gb.is_shifting():
                #print("continue shift ...")
                self.gb.continue_shifting()
            else:
                self.state = "CHECK_SHIFT_STATUS"

        elif self.state == "CHECK_SHIFT_STATUS":
            print("CHECK_SHIFT_STATUS State")
            if self.gb.check_shift_status():
                self.state = "SET_SPINDLE_MOTOR_SPEED"
            else:
                self.state = "ABORT"
        
        elif self.state == "SET_SPINDLE_MOTOR_SPEED":
            print("SET_SPINDLE_MOTOR_SPEED State")
            if self.sm.set_spindle_motor_rpm(self.gb.spindle_speed_setpoint, self.gb.gearbox_output_speed, self.gb.hirange_ratio) and self.sm.set_spindle_motor_frequency():
                self.state = "DONE"
        
        elif self.state == "DONE":
            print("DONE State")
            self.gb.reset_states()
            self.sm.reset_states()
            self.state = "IDLE"

        elif self.state == "ABORT":
            print ("ABORT STATE")
            self.gb.abort()
            self.sm.reset_states()
            self.state = "IDLE"

class HAL:
    def __init__(self):
        self.spindle_speed_setpoint = 0
        self.gearbox_hirange_state = False
        self.gearbox_microswitch_S36 = False
        self.gearbox_microswitch_S37 = False
        #self.gearbox_microswitch_S38 = False
        self.gearbox_microswitch_S39 = False
        #self.gearbox_microswitch_S40 = False
        self.gearbox_microswitch_S41 = False
        self.gearbox_microswitch_S42 = False
        #self.gearbox_microswitch_S43 = False
        self.gearbox_microswitch_S44 = False

        #test setpoints and initial conditions
        self.spindle_speed_setpoint = 800
        self.gearbox_hirange_state = False
        #set switches to 125 rpm
        self.gearbox_microswitch_S38 = True
        self.gearbox_microswitch_S40 = True
        self.gearbox_microswitch_S43 = True


# Main loop
# Instantiate the state machine
gbsm = GearboxStateMachine()
fp4_gearbox = HAL()

#initialise fake switch states and gearmotor fake positions
gbsm.gb.gearmotors[5].switches[0].set_state(fp4_gearbox.gearbox_microswitch_S36)
gbsm.gb.gearmotors[5].switches[1].set_state(fp4_gearbox.gearbox_microswitch_S37)
gbsm.gb.gearmotors[5].switches[2].set_state(fp4_gearbox.gearbox_microswitch_S38)

gbsm.gb.gearmotors[6].switches[0].set_state(fp4_gearbox.gearbox_microswitch_S39)
gbsm.gb.gearmotors[6].switches[1].set_state(fp4_gearbox.gearbox_microswitch_S40)
gbsm.gb.gearmotors[6].switches[2].set_state(fp4_gearbox.gearbox_microswitch_S41)

gbsm.gb.gearmotors[7].switches[0].set_state(fp4_gearbox.gearbox_microswitch_S42)
gbsm.gb.gearmotors[7].switches[1].set_state(fp4_gearbox.gearbox_microswitch_S43)
gbsm.gb.gearmotors[7].switches[2].set_state(fp4_gearbox.gearbox_microswitch_S44)

#S38 True
gbsm.gb.gearmotors[5].fake_position = -120
#S39 True
gbsm.gb.gearmotors[6].fake_position = 120
#S42 True
gbsm.gb.gearmotors[7].fake_position = 120

print("S36: " + str(gbsm.gb.gearmotors[5].switches[0].state))
print("S37: " + str(gbsm.gb.gearmotors[5].switches[1].state))
print("S38: " + str(gbsm.gb.gearmotors[5].switches[2].state))
print("S39: " + str(gbsm.gb.gearmotors[6].switches[0].state))
print("S40: " + str(gbsm.gb.gearmotors[6].switches[1].state))
print("S41: " + str(gbsm.gb.gearmotors[6].switches[2].state))
print("S42: " + str(gbsm.gb.gearmotors[7].switches[0].state))
print("S43: " + str(gbsm.gb.gearmotors[7].switches[1].state))
print("S44: " + str(gbsm.gb.gearmotors[7].switches[2].state))

for _ in range(2000):
    gbsm.update()
    time.sleep(0.01)



            
            

            







   
