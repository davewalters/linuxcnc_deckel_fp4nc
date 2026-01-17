#!usr/bin/env python3

import hal
import time

# Create a new HAL component
servo_open_loop_tuning = hal.component("servo_open_loop_tuning")

# Add pins for configuration and control
servo_open_loop_tuning.newpin("target_velocity_mm_s", hal.HAL_FLOAT, hal.HAL_IN)
servo_open_loop_tuning.newpin("acceleration_mm_s2", hal.HAL_FLOAT, hal.HAL_IN)
servo_open_loop_tuning.newpin("travel_distance_mm", hal.HAL_FLOAT, hal.HAL_IN)
servo_open_loop_tuning.newpin("num_cycles", hal.HAL_S32, hal.HAL_IN)
servo_open_loop_tuning.newpin("velocity_signal", hal.HAL_FLOAT, hal.HAL_OUT)
servo_open_loop_tuning.newpin("brake_release_relay", hal.HAL_BIT, hal.HAL_OUT)
servo_open_loop_tuning.newpin("cycle_start", hal.HAL_BIT, hal.HAL_IN)

# Add feedback pins
#servo_open_loop_tuning.newpin("position_feedback_mm", hal.HAL_FLOAT, hal.HAL_IN)
servo_open_loop_tuning.newpin("drive_health_status", hal.HAL_BIT, hal.HAL_IN)
servo_open_loop_tuning.newpin("integrated_position", hal.HAL_FLOAT, hal.HAL_OUT)

#Set loop rate
servo_open_loop_tuning.newpin("loop_period_s", hal.HAL_FLOAT, hal.HAL_IN) 

# Register the servo_open_loop_tuning component
servo_open_loop_tuning.ready()

def ramp_time(target_velocity, acceleration, travel_distance):
    if acceleration == 0:
        t1 = 0
    else:
        t1 = target_velocity / abs(acceleration)
    
    if target_velocity == 0:
        t2 = 0
    else:
        t2 = travel_distance / target_velocity
    return min(t1, t2)

def constant_velocity_time(ramp_time, target_velocity, travel_distance):
    d1 = (travel_distance / 2) - (0.5 * target_velocity * ramp_time)
    
    if target_velocity == 0:
        t1 = 0
    else:
        t1 = d1 / target_velocity
    return max (0, t1)

def ramp_velocity(current_time, target_velocity, acceleration):
    ramped_velocity = acceleration * current_time
    return max(0, min(ramped_velocity, target_velocity))

try:
    #max_velocity = servo_open_loop_tuning["target_velocity_mm_s"]
    #acceleration = servo_open_loop_tuning["acceleration_mm_s2"]
    #travel_distance = servo_open_loop_tuning["travel_distance_mm"]
    
    integrated_position = 0.0
    cycle_count = 0.0
    moving_forward = True
    ramping_up = True
    motion_active = False
    cycles_done = False
    servo_open_loop_tuning["velocity_signal"] = 0
    servo_open_loop_tuning["brake_release_relay"] = False
    
       
    
    while True:
        #if not servo_open_loop_tuning["cycle_start"]:
        #    motion_active = False
        #    continue
        
        if servo_open_loop_tuning["cycle_start"] and not motion_active and not cycles_done:
            start_time = time.time()
            integrated_position = 0.0
            num_cycles = servo_open_loop_tuning["num_cycles"]
            moving_forward = True
            motion_active = True
            ramping_up = True
            time_1 = ramp_time(servo_open_loop_tuning["target_velocity_mm_s"], servo_open_loop_tuning["acceleration_mm_s2"], servo_open_loop_tuning["travel_distance_mm"])
            time_2 = constant_velocity_time(time_1, servo_open_loop_tuning["target_velocity_mm_s"], servo_open_loop_tuning["travel_distance_mm"])
            half_time = time_1 + time_2
            servo_open_loop_tuning["brake_release_relay"] = True
            continue

        if motion_active and not cycles_done:
            current_time = time.time() - start_time
            if current_time > half_time:
                ramping_up = False

            if current_time < half_time:
                speed = ramp_velocity(current_time, servo_open_loop_tuning["target_velocity_mm_s"], servo_open_loop_tuning["acceleration_mm_s2"])
            else:
                speed = ramp_velocity((2 * half_time) - current_time, servo_open_loop_tuning["target_velocity_mm_s"], servo_open_loop_tuning["acceleration_mm_s2"])
            
            # Correct velocity sign
            if moving_forward:
                velocity = speed
            else:
                velocity = -speed
            
            servo_open_loop_tuning["velocity_signal"] = velocity

            # Integrate commanded velocity to calculate expected position
            integrated_position += velocity * servo_open_loop_tuning["loop_period_s"]
            servo_open_loop_tuning["integrated_position"] = integrated_position

            # Reverse direction, reset timer and increment cycle count
            if current_time >= 2 * half_time:
                if moving_forward:
                    moving_forward = False
                else:
                    moving_forward = True
                cycle_count += 0.5
                start_time = time.time()
                ramping_up = True
                if cycle_count >= num_cycles:
                    cycles_done = True
                    cycle_count = 0
                    motion_active = False
                    servo_open_loop_tuning["velocity_signal"] = 0
                    servo_open_loop_tuning["brake_release_relay"] = False
            time.sleep(servo_open_loop_tuning["loop_period_s"])

        else:
            servo_open_loop_tuning["velocity_signal"] = 0
            servo_open_loop_tuning["brake_release_relay"] = False
            time.sleep(servo_open_loop_tuning["loop_period_s"])

except KeyboardInterrupt:
    servo_open_loop_tuning["velocity_signal"] = 0
    servo_open_loop_tuning["brake_release_relay"] = False
    servo_open_loop_tuning.cleanup()
