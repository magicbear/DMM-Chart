import visa
import time
import datetime
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.ticker import *
import numpy as np
import serial
import time

cfg = {
    "file": "mv.csv",
    "realtime": True,
    "axis": [
        "Voltage",
        "34420A Voltage",
        "34470A Voltage",
        "Temperature"
    ],
    "devices": [
        {"type": "VISA", "port": "GPIB0::22::INSTR", "init_seq": ["END ALWAYS"], "cmd": " ", "field": "Voltage", "color": "r-", "axis": 0, "ppm": True},
        {"type": "VISA", "port": "GPIB0::17::INSTR", "init_seq": ["DISP ON"], "cmd": "READ?", "field": "34420A Voltage", "color": "g-", "axis": 1, "ppm": True},
        {"type": "VISA", "port": "TCPIP0::192.168.9.194::hislip0::INSTR", "init_seq": [], "cmd": "READ?", "field": "34470A Voltage", "color": "b-", "axis": 2, "ppm": True},
        {"type": "JOY65", "port": "COM3", "field": "Temperature", "color": "#ffcc00", "axis": 3, "ppm": False}
    ]
}

print("Initalize GPIB")
rm = visa.ResourceManager(visa_library="C:\\Windows\\SysWOW64\\visa32.Agilent Technologies - Keysight Technologies.dll")
rm.list_resources()

axises = []
rt_axises = []
axis_count = 0
devices = []
for dev_cfg in cfg["devices"]:
    if dev_cfg["type"] == "JOY65":
        print("Initalize COM Port")
        ser = serial.Serial(dev_cfg["port"], baudrate=9600, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, rtscts=False, timeout=3)
        print("Send Command")
        ser.write(b"DISP ON\n")
        devices.append({ "dev": ser, "cfg": dev_cfg, "value":"0", "buf": "", "data": [], "ppm": [] })
    elif dev_cfg["type"] == "VISA":
        _dev = rm.open_resource(dev_cfg["port"])
        for seq in dev_cfg["init_seq"]:
            _dev.write(seq)

        devices.append({ "dev": _dev, "cfg": dev_cfg, "data": [], "ppm": [] })

print("Initalize Chart using backend: %s" % (matplotlib.get_backend()))

plt.ion() ## Note this correction
plt.show(False)

fig = plt.figure("Full Graphic")
host = fig.add_subplot(2,1,1)
fig.subplots_adjust(left=0.07, right=1-(0.05* len(cfg["axis"])))
nhost = fig.add_subplot(2,1,2)

if cfg["realtime"]:
    rt_fig = plt.figure("Realtime")
    rt_host = rt_fig.add_subplot(2,1,1)
    rt_fig.subplots_adjust(left=0.07, right=1-(0.05* len(cfg["axis"])))
    rt_nhost = rt_fig.add_subplot(2,1,2)
    rt_axises.append(rt_host)

# fig.canvas.manager.window.attributes('-topmost', 0)

if matplotlib.get_backend() == "TkAgg":
    wm = plt.get_current_fig_manager() 
    wm.window.attributes('-topmost', 0)

axises.append(host)

for i in range(0,len(cfg["axis"])):
    if i == 0:
        continue
    axises.append(host.twinx())
    if cfg["realtime"]:
        rt_axises.append(rt_host.twinx())

p1_x = []
p1_ts = []

host.set_xlabel("Time")

n = 0
p1_x_offset = np.arange(0,1000)

p1 = None
p2 = None
p3 = None

try:
    f = open(cfg["file"], "rb+")
    for line in f:
        arr = line.decode('utf-8')[:-1].split(",")
        if arr[0] == "\"Reading #\"":
            continue
        p1_x.append(n)
        # ts = datetime.datetime.strptime(arr[1], "%Y-%m-%d %H:%i:%s")
        p1_ts.append(int(arr[1][11:19].replace(":","")))
        for i in range(0,len(devices)):
            devices[i]["data"].append(float(arr[2+i]))
            if devices[i]["cfg"]["ppm"]:
                if len(devices[i]["data"]) > 20:
                    devices[i]["ppm"].append(np.std(devices[i]["data"][-100:])/np.average(devices[i]["data"][-100:])*1000000)
        n+=1

    f.close()
except Exception as e:
    pass

print("Initalize")
f = open(cfg["file"], "ab+")

f.write(b"\"Reading #\",\"Time\"")
for i in range(0,len(devices)):
    f.write((",\"%s\"" % (devices[i]["cfg"]["field"])).encode("utf-8"))
f.write(b"\n")

joy65_temp = 0

while True:
    ignoreAllData = False
    for i in range(0,len(devices)):
        if devices[i]["cfg"]["type"] == "JOY65":
            while devices[i]["dev"].in_waiting:
                rcv_data = devices[i]["dev"].read(devices[i]["dev"].in_waiting)
                devices[i]["buf"] += rcv_data.decode("utf-8")
            
            sp = devices[i]["buf"].split("\r\n")
            if sp[-1] != "":
                devices[i]["buf"] = sp[-1]

            if len(sp) >= 2:
                try:
                    joy65_data = sp[-2].split(",")
                    devices[i]["value"] = joy65_data[1]
                except Exception as e:
                    print(joy65_data)
                    continue
        elif devices[i]["cfg"]["type"] == "VISA":
            if devices[i]["dev"] is None:
                devices[i]["dev"] = rm.open_resource(devices[i]["cfg"]["port"])
            devices[i]["dev"].write(devices[i]["cfg"]["cmd"])

    for axis in axises:
        axis.clear()

    if cfg["realtime"]:
        for axis in rt_axises:
            axis.clear()

    for i in range(0,len(cfg["axis"])):
        axises[i].set_ylabel(cfg["axis"][i])
        if i >= 2:
            axises[i].spines["right"].set_position(("axes", 1 +(i-1)*0.1))
        if cfg["realtime"]:
            rt_axises[i].set_ylabel(cfg["axis"][i])
            if i >= 2:
                rt_axises[i].spines["right"].set_position(("axes", 1 +(i-1)*0.1))

    for i in range(0,len(devices)):
        axis_index = devices[i]["cfg"]["axis"]
        if len(p1_x) != len(devices[i]["data"]):
            print("ERROR: DEVICE %d VALUE UNMATCHED" % (i))
        pd, = axises[axis_index].plot(p1_x, devices[i]["data"], devices[i]["cfg"]["color"], alpha = 0.8)
        axises[axis_index].yaxis.label.set_color(pd.get_color())
        axises[axis_index].yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        if cfg["realtime"]:
            pd, = rt_axises[axis_index].plot(p1_x[-300:], devices[i]["data"][-300:], devices[i]["cfg"]["color"], alpha = 0.8)
            rt_axises[axis_index].yaxis.label.set_color(pd.get_color())
            rt_axises[axis_index].yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

    nhost.clear()
    nhost.set_ylabel("Std(ppm)")
    if cfg["realtime"]:
        rt_nhost.clear()
        rt_nhost.set_ylabel("Std(ppm)")
    
    for i in range(0,len(devices)):
        if devices[i]["cfg"]["ppm"]:
            p5, = nhost.plot(p1_x[20:], devices[i]["ppm"], devices[i]["cfg"]["color"], label="离散系数")
            if cfg["realtime"]:
                rt_nhost.plot(p1_x[-len(devices[i]["ppm"][-300:]):], devices[i]["ppm"][-300:], devices[i]["cfg"]["color"], label="离散系数")

    # fig.canvas.draw()
    plt.pause(0.01)

    write_str = "%d,%s"%(n,datetime.datetime.now())
    value_str = ""

    insert_data = []
    for i in range(0,len(devices)):
        if devices[i]["cfg"]["type"] == "JOY65":
            value = devices[i]["value"]
            if devices[i]["value"] == "0":
                ignoreAllData = True
        elif devices[i]["cfg"]["type"] == "VISA":
            try:
                value = devices[i]["dev"].read()[:-1].strip()
            except Exception as e:
                print("Connect to VISA Devices %d Failed" % (i))
                devices[i]["dev"] = None
                time.sleep(5)
                ignoreAllData = True

        insert_data.append(float(value))

        write_str += ",%s" % (value)
        value_str += "%s," % (value)
    
    if ignoreAllData:
        print("Ignore DATA")
        continue
    else:
        p1_x.append(n)
        ts = datetime.datetime.now()
        p1_ts.append(int("%d%d%d"%(ts.hour,ts.minute,ts.second)))

        for i in range(0,len(devices)):
            devices[i]["data"].append(insert_data[i])
            if devices[i]["cfg"]["ppm"]:
                if len(devices[i]["data"]) > 20:
                    devices[i]["ppm"].append(np.std(devices[i]["data"][-100:])/np.average(devices[i]["data"][-100:])*1000000)
    
    print("%d    Value: %s"%(n,value_str[:-1]))
    f.write((write_str + "\n").encode("utf-8"))
    f.flush()
    # time.sleep(300)
    n+= 1
