#!usr/bin/env python3

import hal
import time

# Create a new component
spindle_lube = hal.component("spindle_lube")

# Add a float pin for min and max runtime, and rest time
spindle_lube.newpin("min_runtime", hal.HAL_FLOAT, hal.HAL_IN)
spindle_lube.newpin("max_runtime", hal.HAL_FLOAT, hal.HAL_IN)
spindle_lube.newpin("auto_lube_rest_time", hal.HAL_FLOAT, hal.HAL_IN)
spindle_lube.newpin("man_lube_rest_time", hal.HAL_FLOAT, hal.HAL_IN)
spindle_lube.newpin("motion_time", hal.HAL_FLOAT, hal.HAL_OUT)

# Add a bit pin for spindle turning
spindle_lube.newpin("spindle_on", hal.HAL_BIT, hal.HAL_IN)
spindle_lube.newpin("lube_cycle_switch", hal.HAL_BIT, hal.HAL_IN)
spindle_lube.newpin("spindle_lube_pump_on", hal.HAL_BIT, hal.HAL_OUT)

# Add an S32 (signed) pin for number of lube cycles
spindle_lube.newpin("spindle_lube_cycles", hal.HAL_S32, hal.HAL_OUT)

# Ready the component
spindle_lube.ready()

class PumpController:
    def __init__(self, min_runtime, max_runtime, auto_lube_rest_time, man_lube_rest_time):
        self.min_runtime = min_runtime
        self.max_runtime = max_runtime
        self.auto_lube_rest_time = auto_lube_rest_time
        self.man_lube_rest_time = man_lube_rest_time
        self.lube_cycles = 0
        self.start_time = None
        self.stop_time = None
        self.motion_time = 0.95 * auto_lube_rest_time
        self.running = False

    def can_start_pump(self, rest_time):
        if self.stop_time is None:
            return True
        return time.time() - self.stop_time >= rest_time

    def start_pump(self, rest_time):
        if not self.running and self.can_start_pump(rest_time):
            self.running = True
            self.start_time = time.time()
            self.lube_cycles += 1
            print("Spindle Lube Pump started")

    def check_pump(self):
        if self.running:
            current_time = time.time()
            if current_time - self.start_time >= self.max_runtime:
                self.stop_pump("Max runtime reached")

    def stop_pump(self, reason):
        self.running = False
        self.stop_time = time.time()
        print(f"Spindle Lube Pump stopped: {reason}")

    def update_motion_time(self, spindle_on, interval):
        if spindle_on:
            self.motion_time += interval
            if self.motion_time >= (self.auto_lube_rest_time + self.max_runtime):
                rest_time = self.auto_lube_rest_time
                self.start_pump(rest_time)
                self.motion_time = 0  # Reset motion time after starting pump


# Initialize PumpController
pump_controller = PumpController(spindle_lube['min_runtime'], spindle_lube['max_runtime'], spindle_lube['auto_lube_rest_time'],spindle_lube['man_lube_rest_time'],)

# Main loop
try:
    while True:
        # Update pump controller with current min, max, and rest times
        pump_controller.min_runtime = spindle_lube['min_runtime']
        pump_controller.max_runtime = spindle_lube['max_runtime']
        pump_controller.auto_lube_rest_time = spindle_lube['auto_lube_rest_time']
        pump_controller.man_lube_rest_time = spindle_lube['man_lube_rest_time']

        # Check if manual switch is activated and start the pump if possible
        if spindle_lube['lube_cycle_switch'] and not pump_controller.running:
            rest_time = pump_controller.man_lube_rest_time
            pump_controller.start_pump(rest_time)

        # Update pump status based on runtime
        pump_controller.check_pump()

        # Update pump control pin
        spindle_lube['spindle_lube_pump_on'] = pump_controller.running

        #Update lube cycles count
        spindle_lube["spindle_lube_cycles"] = pump_controller.lube_cycles

        # Check motion and update motion time for automatic lube cycle
        is_running = spindle_lube['spindle_on']
        pump_controller.update_motion_time(is_running, interval=0.5)
        spindle_lube["motion_time"] = pump_controller.motion_time

        # Sleep for a short time to prevent high CPU usage
        time.sleep(0.5)

except KeyboardInterrupt:
    raise SystemExit


