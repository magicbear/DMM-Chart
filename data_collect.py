import visa
import time
import datetime
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.ticker import *
import numpy as np
import serial
import time
import threading
import sys
import os
import signal
import matplotlib.patheffects as path_effects
from matplotlib.backend_bases import NavigationToolbar2
import socket
import select
import matplotlib.ticker as ticker

cfg = {
    "file": "LTZ1000CH.csv",
    "realtime": False,
    "axis": [
        "Voltage",
        "34420A Voltage",
        "34470A Voltage",
        "Temperature"
    ],
    "devices": [
        {"type": "VISA", "port": "GPIB0::22::INSTR", "init_seq": ["END ALWAYS"], "cmd": " ", "field": "Voltage", "color": "#f4b775", "axis": 0, "ppm": True},
        {"type": "VISA", "port": "GPIB0::17::INSTR", "init_seq": ["DISP ON"], "cmd": "READ?", "field": "34420A Voltage", "color": "#5ca949", "axis": 1, "ppm": True},
        {"type": "VISA", "port": "TCPIP0::192.168.9.194::hislip0::INSTR", "init_seq": [], "cmd": "READ?", "field": "34470A Voltage", "color": "#4789bd", "axis": 2, "ppm": True},
        {"type": "JOY65_TCPIP", "port": "127.0.0.1:7777", "field": "Temperature", "field_temp": {"type": "JOY65_TEMP", "field": "Temperature_JOY65", "axis": 3, "color": "gray", "ppm": False}, "color": "gray", "axis": 3, "ppm": False, "raw": "joy65.log"}
    ]
}

def handle_exception(exc_type, exc_value, exc_traceback):
    # if issubclass(exc_type, KeyboardInterrupt):
    print("%d: %s %s" % (os.getpid(), str(exc_value), str(exc_traceback)))
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(0)
        # return

sys.excepthook = handle_exception


class CollectThread(threading.Thread):
    def __init__(self, devices):
        threading.Thread.__init__(self)
        self.devices = devices
        self.mutex = threading.Lock()
        self.is_waiting = False
        self.failed_list = []
        self.values = []

    def run(self):
        while True:
            if self.is_waiting:
                ignoreAllData = False
                self.values = []
                self.failed_list = []
                for i in range(0,len(self.devices)):
                    if self.devices[i]["cfg"]["type"] == "VISA":
                        try:
                            if self.devices[i]["dev"] is None:
                                self.devices[i]["dev"] = rm.open_resource(self.devices[i]["cfg"]["port"])
                                self.devices[i]["dev"].timeout = 8000
                                for seq in self.devices[i]["cfg"]["init_seq"]:
                                    self.devices[i]["dev"].write(seq)

                            self.devices[i]["dev"].write(self.devices[i]["cfg"]["cmd"])
                        except Exception as e:
                            print("Connect to VISA Devices %d Failed: %s" % (i, str(e)))
                            self.failed_list.append(i)
                            ignoreAllData = True
                            break

                if not ignoreAllData:
                    for i in range(0,len(self.devices)):
                        if self.devices[i]["cfg"]["type"] == "JOY65" or self.devices[i]["cfg"]["type"] == "JOY65_TCPIP" or self.devices[i]["cfg"]["type"] == "JOY65_TEMP":
                            value = None
                        elif self.devices[i]["cfg"]["type"] == "VISA":
                            try:
                                value = self.devices[i]["dev"].read()[:-1].strip()
                            except Exception as e:
                                print("Connect to VISA Devices %d Failed: %s" % (i, str(e)))
                                self.failed_list.append(i)
                                ignoreAllData = True
                                break

                        self.values.append(value)

                if ignoreAllData:
                    self.values = []
                self.mutex.acquire()
                self.is_waiting = False
                self.mutex.release()
            else:
                time.sleep(0.05)

print("Initalize GPIB")
rm = visa.ResourceManager(visa_library="C:\\Windows\\SysWOW64\\visa32.Agilent Technologies - Keysight Technologies.dll")
rm.list_resources()

axises = []
rt_axises = []
axis_count = 0
devices = []
for dev_cfg in cfg["devices"]:
    fraw = None
    if "raw" in dev_cfg:
        fraw = open(dev_cfg["raw"], "ab+")
    if dev_cfg["type"] == "JOY65":
        print("Initalize COM Port")
        ser = serial.Serial(dev_cfg["port"], baudrate=9600, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, rtscts=False, timeout=3)
        print("Send Command")
        ser.write(b"DISP ON\n")
        devices.append({ "dev": ser, "cfg": dev_cfg, "value":"0", "buf": "", "data": [], "ppm": [], "raw": fraw, "temperature":"0" })
    elif dev_cfg["type"] == "JOY65_TCPIP":
        devices.append({ "dev": None, "cfg": dev_cfg, "value":"0", "buf": "", "data": [], "ppm": [], "raw": fraw, "temperature":"0" })
        if "field_temp" in dev_cfg:
            dev_cfg["field_temp"]["type"] = "JOY65_TEMP"
            devices.append({ "dev": len(devices)-1, "cfg": dev_cfg["field_temp"], "value":"0", "data": [], "ppm": [], "raw": None, "temperature":"0" })
    elif dev_cfg["type"] == "VISA":
        devices.append({ "dev": None, "cfg": dev_cfg, "data": [], "ppm": [], "raw": fraw })

print("Initalize Chart using backend: %s" % (matplotlib.get_backend()))

plt.ion() ## Note this correction
home = NavigationToolbar2.home

default_xlim = None
default_ylim = None
save_xlim = None
save_ylim = None

def new_home(self, *args, **kwargs):
    global save_xlim, default_xlim
    print('Zoom Out')
    host.set_xlim(default_xlim)
    host.set_ylim(default_ylim)
    save_xlim = None
    save_ylim = None
    # home(self, *args, **kwargs)
NavigationToolbar2.home = new_home

# plt.show(False)

fig = plt.figure("Full Graphic")
# fig.set_title('Click on legend line to toggle line on/off')
host = fig.add_subplot(2,1,1,picker=True)
fig.subplots_adjust(left=0.07, right=1-(0.05* len(cfg["axis"])))
nhost = fig.add_subplot(2,1,2,picker=True)

if cfg["realtime"]:
    rt_fig = plt.figure("Realtime")
    rt_host = rt_fig.add_subplot(2,1,1)
    rt_fig.subplots_adjust(left=0.07, right=1-(0.05* len(cfg["axis"])))
    rt_nhost = rt_fig.add_subplot(2,1,2)
    rt_axises.append(rt_host)

# fig.canvas.manager.window.attributes('-topmost', 0)

# if matplotlib.get_backend() == "TkAgg":
#   wm = plt.get_current_fig_manager() 
#   wm.window.attributes('-topmost', 0)

axises.append(host)

graph = host.twinx()
ppm_graph = nhost.twinx()
graph.axes.get_yaxis().set_visible(False)
ppm_graph.axes.get_yaxis().set_visible(False)

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
        p1_ts.append(arr[1][11:19])
        for i in range(0,len(devices)):
            devices[i]["data"].append(float(arr[2+i]))
            if devices[i]["cfg"]["ppm"]:
                if len(devices[i]["data"]) > 20:
                    devices[i]["ppm"].append(np.std(devices[i]["data"][-100:])/np.average(devices[i]["data"][-100:])*1000000)
        n+=1

    f.close()
except Exception as e:
    pass

print("Initalize Data File")
f = open(cfg["file"], "ab+")

f.write(b"\"Reading #\",\"Time\"")
for i in range(0,len(devices)):
    f.write((",\"%s\"" % (devices[i]["cfg"]["field"])).encode("utf-8"))
f.write(b"\n")

joy65_temp = 0

print("Initalize CollectThread")
t_read = CollectThread(devices)
t_read.start()

enable_chart_update = True

# Declare and register callbacks
def on_xlims_change(axes):
    global default_xlim, default_ylim, save_xlim, save_ylim
    if default_xlim is None:
        default_xlim = host.get_xlim()
        default_ylim = host.get_ylim()
    
    # if enable_chart_update == False:
    else:
        save_xlim = axes.get_xlim()
        save_ylim = axes.get_ylim()

def format_date(x, pos=None):
    if x < 0 or x > len(p1_ts):
        return x
    return p1_ts[int(x)]

def line_hover(event):
    # if host is event.inaxes:
        # print("In AXIS")

    graph.clear()
    ppm_graph.clear()

    if event.inaxes is not None and event.inaxes.get_position().bounds == host.get_position().bounds and event.xdata is not None and int(event.xdata) < len(p1_x) and event.xdata >= 0:
        wstr = " %s\n" % (p1_ts[int(event.xdata)])
        for axis in axises:
            for line in axis.get_lines():
                wstr += " %s: %.06f\n" % (line.get_label(), line.get_ydata()[int(event.xdata)])
        graph.axvline(x=event.xdata, color="red")
        text = graph.text(x=event.xdata, y=0, s=wstr, ha='left', va='bottom', color="red")

    if event.inaxes is not None and event.inaxes.get_position().bounds == nhost.get_position().bounds and int(event.xdata) < len(p1_x) and event.xdata >= 20:
        ppm_wstr = " %s\n" % (p1_ts[int(event.xdata)])
        for i in range(0,len(devices)):
            if devices[i]["cfg"]["ppm"]:
                ppm_wstr += " %s: %.06f\n" % (devices[i]["cfg"]["field"], devices[i]["ppm"][int(event.xdata)-20])
        ppm_graph.axvline(x=event.xdata, color="red")
        ppm_graph.text(x=event.xdata, y=0.0, s=ppm_wstr, ha='left', va='bottom', color="red")

    # hasSelected = False
    # for axis in axises:
    #   # if event.inaxes == axis:
    #   for line in axis.get_lines():
    #       if line.contains(event)[0]:
    #           line.set_linewidth(3)
    #           line.set_alpha(1)
    #           hasSelected = True
    #           # axis.text(3,5, 'unicode: Institut für Festkörperphysik')
    #       else:
    #           line.set_linewidth(1.5)

    #   if hasSelected:
    #       for line in axis.get_lines():
    #           if not line.contains(event)[0]:
    #               line.set_alpha(0.3)
    #   else:
    #       for line in axis.get_lines():
    #           line.set_linewidth(1.5)
    #           line.set_alpha(1)

    event.canvas.draw_idle()
    # print(event, event.xdata, event.ydata)

def fig_enter(event):
    global enable_chart_update
    print("Fig Enter")
    enable_chart_update = False

def fig_leave(event):
    global enable_chart_update
    print("Fig Leave")
    enable_chart_update = True

# def on_pick(event):
#   print("Pick event", event.artist)
#   legline = event.artist

# class Workaround(object):
#   def __init__(self, artists):
#       self.artists = artists
#       artists[0].figure.canvas.mpl_connect('pick_event', self)

#   def __call__(self, event):
#       try:
#           if event.mouseevent.in_picking >= 3:
#               return
#           elif event.mouseevent.in_picking < 3:
#               pass
#       except Exception as e:
#           event.mouseevent.in_picking = 0
#           pass
#       print("  Picking ",event)
#       for artist in self.artists:
#           try:
#               event.mouseevent.in_picking += 1
#               artist.pick(event.mouseevent)
#           except Exception as e:
#               print("  Picking "+str(e)+" Failed")


# for axis in axises:
#   axis.figure.canvas.mpl_connect('pick_event', on_pick)

# fig.canvas.mpl_connect('pick_event', on_pick)
fig.canvas.mpl_connect('motion_notify_event', line_hover)
# fig.canvas.mpl_connect('figure_enter_event', fig_enter)
# fig.canvas.mpl_connect('figure_leave_event', fig_leave)
# Workaround(axises)

line_index = dict()
line_visible = [True] * len(devices)

print("Collection started")
while True:
    t_read.mutex.acquire()
    t_read.is_waiting = True
    t_read.mutex.release()

    ignoreAllData = False
    for i in range(0,len(devices)):
        if devices[i]["cfg"]["type"] == "JOY65" or devices[i]["cfg"]["type"] == "JOY65_TCPIP":
            if devices[i]["cfg"]["type"] == "JOY65":
                while devices[i]["dev"].in_waiting:
                    rcv_data = devices[i]["dev"].read(devices[i]["dev"].in_waiting)
                    devices[i]["buf"] += rcv_data.decode("utf-8")
                    if devices[i]["raw"] is not None:
                        devices[i]["raw"].write(rcv_data)
            elif devices[i]["cfg"]["type"] == "JOY65_TCPIP":
                if devices[i]["dev"] is None:
                    devices[i]["dev"] = socket.socket()
                    tg_host = devices[i]["cfg"]["port"].split(":")
                    devices[i]["dev"].connect((tg_host[0], int(tg_host[1])))
                    devices[i]["dev"].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    devices[i]["dev"].send(b"DISP ON\n")

                sel = select.select([devices[i]["dev"]], [], [],0)
                if len(sel) > 0:                    
                    rcv_data = devices[i]["dev"].recv(1024)
                    devices[i]["buf"] += rcv_data.decode("utf-8")
                    if devices[i]["raw"] is not None:
                        devices[i]["raw"].write(rcv_data)

            sp = devices[i]["buf"].split("\n")
            if sp[-1] != "":
                devices[i]["buf"] = sp[-1]

            if len(sp) >= 2:
                try:
                    joy65_data = sp[-2].split(",")
                    devices[i]["value"] = joy65_data[1]
                    devices[i]["temperature"] = joy65_data[6]
                except Exception as e:
                    print(joy65_data)
                    continue

    if cfg["realtime"]:
        for axis in rt_axises:
            axis.clear()
    lns = []

    if enable_chart_update:
        default_xlim = None
        default_ylim = None
        for axis in axises:
            axis.clear()
        
        host.callbacks.connect('xlim_changed', on_xlims_change)
        host.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))

    for i in range(0,len(cfg["axis"])):
        if enable_chart_update:
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

        if enable_chart_update:
            pd, = axises[axis_index].plot(p1_x, devices[i]["data"], devices[i]["cfg"]["color"], label=devices[i]["cfg"]["field"], picker=5)
            lns.append(pd)
            line_index[pd] = i
            # if i == 1:
            #   d = np.array(devices[i]["data"])
            #   pd, = axises[axis_index].plot(p1_x, d + (np.array(devices[3]["data"])-24)/1000000*25*d, devices[i]["cfg"]["color"], label=devices[i]["cfg"]["field"], alpha=0.5, linewidth=0.75)
            # if i == 2:
            #   d = np.array(devices[i]["data"])
            #   pd, = axises[axis_index].plot(p1_x, d + (np.array(devices[3]["data"])-24)/1000000*5*d, devices[i]["cfg"]["color"], label=devices[i]["cfg"]["field"], alpha=0.5, linewidth=0.75)
            axises[axis_index].yaxis.label.set_color(pd.get_color())
            axises[axis_index].yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        if cfg["realtime"]:
            pd, = rt_axises[axis_index].plot(p1_x[-300:], devices[i]["data"][-300:], devices[i]["cfg"]["color"], picker=5)
            rt_axises[axis_index].yaxis.label.set_color(pd.get_color())
            rt_axises[axis_index].yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

    if enable_chart_update:
        nhost.clear()
        nhost.set_ylabel("Std(ppm)")
    if cfg["realtime"]:
        rt_nhost.clear()
        rt_nhost.set_ylabel("Std(ppm)")

    for i in range(0,len(devices)):
        if devices[i]["cfg"]["ppm"]:
            if enable_chart_update:
                p5, = nhost.plot(p1_x[20:], devices[i]["ppm"], devices[i]["cfg"]["color"], label="%s离散系数" % (devices[i]["cfg"]["field"]))
            if cfg["realtime"] and len(devices[i]["ppm"])>0:
                rt_nhost.plot(p1_x[-len(devices[i]["ppm"][-300:]):], devices[i]["ppm"][-300:], devices[i]["cfg"]["color"], label="%s离散系数" % (devices[i]["cfg"]["field"]))

    if enable_chart_update:
        labs = [l.get_label() for l in lns]
        leg = fig.legend(lns, labs, loc='lower right', fancybox=True, shadow=True)
        lined = dict()
        for legline, origline in zip(leg.get_lines(), lns):
            legline.set_picker(5)
            lined[legline] = origline
            if line_visible[line_index[origline]] == False:
                origline.set_visible(False)
                legline.set_alpha(0.2)

        # leg.set_zorder(axises[len(axises)-1].get_zorder() + 1)
        def on_btn_place(event):
            for legline in leg.get_lines():
                c = legline.contains(event)
                if c[0]:
                    origline = lined[legline]
                    vis = not origline.get_visible()
                    origline.set_visible(vis)
                    line_visible[line_index[origline]] = vis
                    # Change the alpha on the line in the legend so we can see what lines
                    # have been toggled
                    if vis:
                        legline.set_alpha(1.0)
                    else:
                        legline.set_alpha(0.2)
                    
                    fig.canvas.draw_idle()

        leg.figure.canvas.mpl_connect('button_press_event', on_btn_place)
        # leg.draggable()

    if enable_chart_update and save_xlim is not None:
        host.set_xlim(save_xlim)
        host.set_ylim(save_ylim)

    fig.canvas.draw_idle()
    fig.canvas.start_event_loop(0.05)

    write_str = "%d,%s"%(n,datetime.datetime.now())
    value_str = ""

    insert_data = []

    while t_read.is_waiting:
        # plt.pause(0.05)
        fig.canvas.start_event_loop(0.05)
        # time.sleep(0.05)

    for i in t_read.failed_list:
        print("Connect to VISA Devices %d Failed" % (i))
        devices[i]["dev"] = None
        time.sleep(5)

    if len(t_read.values) != len(devices):
        print("Read Thread Data Invalid")
        continue

    for i in range(0,len(devices)):
        if devices[i]["cfg"]["type"] == "JOY65" or devices[i]["cfg"]["type"] == "JOY65_TCPIP":
            value = devices[i]["value"]
            if devices[i]["value"] == "0":
                print("JOY65 Data Invalid")
                ignoreAllData = True
        elif devices[i]["cfg"]["type"] == "JOY65_TEMP":
            value = devices[devices[i]["dev"]]["temperature"]
            if value == "0":
                print("JOY65 Temperature Data Invalid")
                ignoreAllData = True
        elif devices[i]["cfg"]["type"] == "VISA":
            value = t_read.values[i]
            if devices[i]["raw"] is not None:
                devices[i]["raw"].write(("%s\n" % (value)).encode("utf-8"))

        insert_data.append(float(value))

        write_str += ",%s" % (value)
        value_str += "%s," % (value)
    
    if ignoreAllData:
        print("Ignore DATA")
        continue
    else:
        p1_x.append(n)
        ts = datetime.datetime.now()
        p1_ts.append("%02d:%02d:%02d"%(ts.hour,ts.minute,ts.second))

        for i in range(0,len(devices)):
            devices[i]["data"].append(insert_data[i])
            if devices[i]["cfg"]["ppm"]:
                if len(devices[i]["data"]) > 20:
                    devices[i]["ppm"].append(np.std(devices[i]["data"][-100:])/np.average(devices[i]["data"][-100:])*1000000)
    
    print("%d   Value: %s"%(n,value_str[:-1]))
    f.write((write_str + "\n").encode("utf-8"))
    f.flush()
    n+= 1
