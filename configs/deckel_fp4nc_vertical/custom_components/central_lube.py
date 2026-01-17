#!usr/bin/env python3

import hal
import time

# Create a new component
central_lube = hal.component("central_lube")

# Add a float pin for min and max runtime, and rest time
central_lube.newpin("min_runtime", hal.HAL_FLOAT, hal.HAL_IN)
central_lube.newpin("max_runtime", hal.HAL_FLOAT, hal.HAL_IN)
central_lube.newpin("auto_lube_rest_time", hal.HAL_FLOAT, hal.HAL_IN)
central_lube.newpin("man_lube_rest_time", hal.HAL_FLOAT, hal.HAL_IN)
central_lube.newpin("motion_time", hal.HAL_FLOAT, hal.HAL_OUT)

# Add a bit pin for pressure switch, manual switch, and pump control
central_lube.newpin("pressure_switch", hal.HAL_BIT, hal.HAL_IN)
central_lube.newpin("lube_cycle_switch", hal.HAL_BIT, hal.HAL_IN)
central_lube.newpin("central_lube_pump_on", hal.HAL_BIT, hal.HAL_OUT)

# Add an S32 (signed) pin for in_motion_type and number of lube cycles
central_lube.newpin("in_motion_type", hal.HAL_S32, hal.HAL_IN)
central_lube.newpin("central_lube_cycles", hal.HAL_S32, hal.HAL_OUT)

# Ready the component
central_lube.ready()

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
            print("central lube pump started")

    def check_pump(self, pressure_switch):
        if self.running:
            current_time = time.time()
            if current_time - self.start_time >= self.max_runtime:
                self.stop_pump("max runtime reached")
            elif (current_time - self.start_time >= self.min_runtime) and pressure_switch:
                self.stop_pump("min runtime reached and pressure switch activated")

    def stop_pump(self, reason):
        self.running = False
        self.stop_time = time.time()
        print(f"pump stopped: {reason}")

    def update_motion_time(self, motion_type, interval):
        # Assuming motion types 1, 2, and 3 indicate motion
        if motion_type in [1, 2, 3]:
            self.motion_time += interval
            if self.motion_time >= (self.auto_lube_rest_time + self.max_runtime):
                rest_time = self.auto_lube_rest_time
                self.start_pump(rest_time)
                self.motion_time = 0  # Reset motion time after starting pump


# Initialize PumpController
pump_controller = PumpController(central_lube['min_runtime'], central_lube['max_runtime'], central_lube['auto_lube_rest_time'], central_lube['man_lube_rest_time'])


# Main loop
try:
    while True:
        # Update pump controller with current min, max, and rest times
        pump_controller.min_runtime = central_lube['min_runtime']
        pump_controller.max_runtime = central_lube['max_runtime']
        pump_controller.auto_lube_rest_time = central_lube['auto_lube_rest_time']
        pump_controller.man_lube_rest_time = central_lube['man_lube_rest_time']

        # Check if manual switch is activated and start the pump if possible
        if central_lube['lube_cycle_switch'] and not pump_controller.running:
            rest_time = pump_controller.man_lube_rest_time
            pump_controller.start_pump(rest_time)

        # Update pump status based on pressure switch and runtime
        pump_controller.check_pump(central_lube['pressure_switch'])

        # Update pump control pin
        central_lube['central_lube_pump_on'] = pump_controller.running

        #Update lube cycles count
        central_lube["central_lube_cycles"] = pump_controller.lube_cycles

        # Check motion type and update motion time for automatic lube cycle
        # Pump will start if enough motion_time has elapsed
        motion_type = central_lube['in_motion_type']
        pump_controller.update_motion_time(motion_type, interval=0.5)
        central_lube["motion_time"] = pump_controller.motion_time

        # Sleep for a short time to prevent high CPU usage
        time.sleep(0.5)

except KeyboardInterrupt:
    raise SystemExit


