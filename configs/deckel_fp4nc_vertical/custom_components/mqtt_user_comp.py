#!usr/bin/env python3

import hal
import time
import paho.mqtt.client as mqtt
import json

# Create a new component
mqtt_user_comp = hal.component("mqtt_user_comp")

#fp4_gearbox
mqtt_user_comp.newpin("gearbox_hirange_state", hal.HAL_BIT, hal.HAL_IN)
mqtt_user_comp.newpin("state_machine_state", hal.HAL_FLOAT, hal.HAL_IN)
mqtt_user_comp.newpin("gear_ratio", hal.HAL_FLOAT, hal.HAL_IN)

#central_lube
mqtt_user_comp.newpin("central_lube_pump_on", hal.HAL_BIT, hal.HAL_IN)
mqtt_user_comp.newpin("central_lube_cycles", hal.HAL_S32, hal.HAL_IN)

#spindle_lube
mqtt_user_comp.newpin("spindle_lube_pump_on", hal.HAL_BIT, hal.HAL_IN)
mqtt_user_comp.newpin("spindle_lube_cycles", hal.HAL_S32, hal.HAL_IN)

mqtt_user_comp.ready()

class MqttPublisher:
    def __init__(self):
        self.topic = "devices/linuxcnc/machine/mqtt_user_comp"
        self.client = mqtt.Client()
        #set username and password
        self.client.username_pw_set("username", "password")
        self.client.connect("192.168.1.210", 1883, 60)
        self.print_counter = 0

    def publish(self, pin_names, values):
        assert len(pin_names) == len(values)

        message = {pin_name : value for pin_name, value in zip(pin_names, values)}
        mqtt_message = json.dumps(message)
        self.client.publish(self.topic, mqtt_message)
        
        self.print_counter +=1
        if self.print_counter > 9:
            print(f"info: Publishing mqtt_message: ({self.topic}) {mqtt_message}")
            self.print_counter = 0
        

    def shutdown(self):
        self.client.disconnect()

class MqttUserComp:
    def __init__(self, pin_names):
        self.hal_comp = mqtt_user_comp
        #print(f"self.hal_comp type: {type(self.hal_comp)}")
        self.topic = "devices/linuxcnc/machine/mqtt_user_comp"
        self.pin_names = pin_names
        self.mqtt_publisher = MqttPublisher()

    def run(self):
        pin_values = [self.hal_comp[pin] for pin in self.pin_names]
        self.mqtt_publisher.publish(self.pin_names, pin_values)

    def shutdown(self):
        self.mqtt_publisher.shutdown()

mqtt = MqttUserComp(["gearbox_hirange_state",\
                    "state_machine_state",\
                    "gear_ratio",\
                    "central_lube_pump_on",\
                    "central_lube_cycles",\
                    "spindle_lube_pump_on",\
                    "spindle_lube_cycles"])

# Main loop
try:
    while True:
        mqtt.run()
        time.sleep(1.0)

except KeyboardInterrupt:
    mqtt.shutdown()
    raise SystemExit