import linuxcnc
import datetime
import time

stat = linuxcnc.stat()

with open("position-log.csv", "w") as outfile:
    while True:
       dt = datetime.datetime.now()
       stat.poll()
       x,y,z,a,b,c,u,v,w = stat.actual_position
       outfile.write("{},{:.4f},{:.4f},{:.4f}\n".format(dt.isoformat(), x, y, z))
       time.sleep(0.001)