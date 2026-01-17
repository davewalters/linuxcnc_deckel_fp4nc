#!usr/bin/env python3

import hal
import time

comp = hal.component("manual_spindle_speed_setpoint")
comp.newpin("mcp_spindle_speed_analog", hal.HAL_FLOAT, hal.HAL_OUT)
comp.newpin("setpoint", hal.HAL_FLOAT, hal.HAL_OUT)
comp.ready()

lookup_table = [
    (2.50, 3150),
    (3.55, 2500),
    (4.55, 2000),
    (5.40, 1600),
    (6.25, 1250),
    (7.10, 1000),
    (7.95, 800),
    (8.85, 630),
    (9.80, 500),
    (10.75, 400),
    (11.65, 315),
    (12.60, 250),
    (13.60, 200),
    (14.65, 150),
    (15.75, 125),
    (16.85, 100),
    (17.95, 80),
    (19.15, 63),
    (20.50, 0)
]

def find_closest_lookup_value(input_value, lookup_table):

    if input_value <= lookup_table[0][0]:
        return lookup_table[0][1]
    elif input_value >= lookup_table[-1][0]:
        return lookup_table[-1][1]

    for i in range(len(lookup_table) - 1):
        if lookup_table[i][0] <= input_value <= lookup_table[i + 1][0]:
            return lookup_table[i][1] if (input_value - lookup_table[i][0]) < (lookup_table[i + 1][0] - input_value) else lookup_table[i + 1][1]

try:
    while True:
        mcp_spindle_speed_analog = comp["mcp_spindle_speed_analog"]
        setpoint = find_closest_lookup_value(mcp_spindle_speed_analog, lookup_table)
        comp["setpoint"] = setpoint

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
