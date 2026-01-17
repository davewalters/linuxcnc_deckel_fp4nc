#!usr/bin/env python3

import hal
import time

comp = hal.component("feed_override")
comp.newpin("mcp_analog", hal.HAL_FLOAT, hal.HAL_IN)
comp.newpin("setpoint", hal.HAL_S32, hal.HAL_OUT)
comp.ready()

lookup_table = [
    (2.05, 120),
    (4.05, 100),
    (5.85, 80),
    (7.60, 60),
    (9.40, 40),
    (11.25, 20),
    (13.20, 15),
    (15.20, 10),
    (17.25, 5),
    (19.60, 0)
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
        mcp_feedrate_override_analog = comp["mcp_analog"]
        setpoint = find_closest_lookup_value(mcp_feedrate_override_analog, lookup_table)
        comp["setpoint"] = setpoint

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
