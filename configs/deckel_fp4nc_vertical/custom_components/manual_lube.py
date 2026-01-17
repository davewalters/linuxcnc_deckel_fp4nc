#!usr/bin/env python3

import hal
import time

class PumpController:
    def __init__(self, min_runtime, max_runtime, rest_time):
        self.min_runtime = min_runtime
        self.max_runtime = max_runtime
        self.rest_time = rest_time
        self.start_time = None
        self.stop_time = None
        self.running = False

    def can_start_pump(self):
        if self.stop_time is None:
            return True
        return time.time() - self.stop_time >= self.rest_time

    def start_pump(self):
        if not self.running and self.can_start_pump():
            self.running = True
            self.start_time = time.time()
            print("Pump started")

    def check_pump(self, pressure_switch):
        if self.running:
            current_time = time.time()
            if current_time - self.start_time >= self.max_runtime:
                self.stop_pump("Max runtime reached")
            elif (current_time - self.start_time >= self.min_runtime) and pressure_switch:
                self.stop_pump("Min runtime reached and pressure switch activated")

    def stop_pump(self, reason):
        self.running = False
        self.stop_time = time.time()
        print(f"Pump stopped: {reason}")

# Create a new component
manual_lube = hal.component("manual_lube")

# Add a float pin for min and max runtime, and rest time
manual_lube.newpin("min_runtime", hal.HAL_FLOAT, hal.HAL_IN)
manual_lube.newpin("max_runtime", hal.HAL_FLOAT, hal.HAL_IN)
manual_lube.newpin("rest_time", hal.HAL_FLOAT, hal.HAL_IN)

# Add a bit pin for pressure switch, manual switch, and pump control
manual_lube.newpin("pressure_switch", hal.HAL_BIT, hal.HAL_IN)
manual_lube.newpin("lube_cycle_switch", hal.HAL_BIT, hal.HAL_IN)
manual_lube.newpin("lube_pump_on", hal.HAL_BIT, hal.HAL_OUT)

# Ready the component
manual_lube.ready()

# Initialize PumpController
pump_controller = PumpController(manual_lube['min_runtime'], manual_lube['max_runtime'], manual_lube['rest_time'])

# Main loop
try:
    while True:
        # Update pump controller with current min, max, and rest times
        pump_controller.min_runtime = manual_lube['min_runtime']
        pump_controller.max_runtime = manual_lube['max_runtime']
        pump_controller.rest_time = manual_lube['rest_time']

        # Check if manual switch is activated and start the pump if possible
        if manual_lube['lube_cycle_switch'] and not pump_controller.running:
            pump_controller.start_pump()

        # Update pump status based on pressure switch and runtime
        pump_controller.check_pump(manual_lube['pressure_switch'])

        # Update pump control pin
        manual_lube['lube_pump_on'] = pump_controller.running

        # Sleep for a short time to prevent high CPU usage
        time.sleep(0.5)
except KeyboardInterrupt:
    raise SystemExit

