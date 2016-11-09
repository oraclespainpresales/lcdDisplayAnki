import pifacecad
import sys
import subprocess
import time
import requests
import json
import pprint
import os

SETUP=False

INIT=0
WIFI=1
SNIFFERS=2
IOTPROXY=3
REVERSEPORTS=4
RACE=5
#LAPS=5
currentInfoDisplay=0
maxInfoDisplay=5
buttonWaitingForConfirmation=-1

BUTTON1=0
BUTTON2=1
BUTTON3=2
BUTTON4=3
BUTTON5=4
BUTTONMIDDLE=5
BUTTONLEFT=6
BUTTONRIGHT=7

GET_IP_CMD = "hostname --all-ip-addresses"
GET_WIFI_CMD = "sudo iwconfig wlan0 | grep ESSID | awk -F\":\" '{print $2}' | awk -F'\"' '{print $2}'"
RESET_WIFI_CMD = "sudo ifdown wlan0;sleep 5;sudo ifup wlan0"
CHECK_INTERNET_CMD = "sudo ping -q -w 1 -c 1 8.8.8.8 > /dev/null 2>&1 && echo U || echo D"
CHECK_IOTPROXY_CMD = "[ `ps -ef | grep -v grep | grep iotcswrapper| grep -v forever  | wc -l` -eq 1 ] && echo UP || echo DOWN"
CHECK_IOTPROXY_STATUS_CMD = "curl http://localhost:8888/iot/status 2> /dev/null || echo ERROR"
RESET_CURRENT_SPEED_DATA_CMD = "curl -i -X POST http://oc-129-152-131-150.compute.oraclecloud.com:8001/BAMHelper/ResetCurrentSpeedService/anki/reset/speed/MADRID 2>/dev/null | grep HTTP | awk '{print $2}'"
UPDATE_CURRENT_RACE_CMD = "curl -i -X POST http://oc-129-152-131-150.compute.oraclecloud.com:8001/BAMHelper/UpdateCurrentRaceService/anki/event/currentrace/MADRID/{RACEID} 2>/dev/null | grep HTTP | awk '{print $2}'"
RESET_RACE_DATA_CMD = "curl -i -X POST http://oc-129-152-131-150.compute.oraclecloud.com:8001/BAMHelper/ResetBAMDataService/anki/reset/bam/MADRID 2>/dev/null | grep HTTP | awk '{print $2}'"
CHECK_REVERSEPROXY_CMD = "ssh -i /home/pi/.ssh/anki_drone $reverseProxy \"netstat -ant | grep LISTEN | grep $DRONEPORT | wc -l\""
CHECK_NODEUP_CMD = "wget -q -T 5 --tries 2 -O - http://$reverseProxy:$DRONEPORT/drone > /dev/null && echo OK || echo NOK"
CHECK_WEBSOCKET_CMD = "wget -q -T 5 --tries 1 -O - http://$reverseProxy:$DRONEPORT/drone/ping > /dev/null && echo OK || echo NOK"
RESET_AUTOSSH_CMD = "pkill autossh;/home/pi/bin/setupReverseSSHPorts.sh /home/pi/bin/redirects"
RESET_NODEJS_CMD = "forever stop drone;forever start --uid drone --append /home/pi/node/dronecontrol/server.js"
USB_PORTS_CMD = "ls -1 /dev/ttyU* 2>/dev/null | wc -l"
SNIFFERS_RUNNING_CMD = "ps -ef | grep -v grep | grep  ttyUSB | wc -l"
REBOOT_CMD = "sudo reboot"
POWEROFF_CMD = "sudo poweroff"
KILL_SNIFFER_CMD = "/home/pi/ankiEventSniffer/killSniffer.sh"
KILL_SNIFFERS_CMD = "/home/pi/ankiEventSniffer/killSniffers.sh"
RESET_IOTPROXY_CMD = "forever stop iot;forever start --uid iot --append /home/pi/node/iotcswrapper/server.js /home/pi/node/iotcswrapper/AAAAAARXSIIA-AE.json"
piusergroup=1000

demozone_file="/home/pi/setup/demozone.dat"
race_status_file="/home/pi/setup/race_status.dat"
race_count_file="/home/pi/setup/race_count.dat"
race_lap_Thermo_file="/home/pi/setup/race_lap_Thermo.dat"
race_lap_GroundShock_file="/home/pi/setup/race_lap_Ground Shock.dat"
race_lap_Skull_file="/home/pi/setup/race_lap_Skull.dat"
race_lap_Guardian_file="/home/pi/setup/race_lap_Guardian.dat"
race_lap_file="/home/pi/setup/race_lap_%s.dat"
demozone_file="/home/pi/setup/demozone.dat"
dbcs_host_file="/home/pi/setup/dbcs.dat"

def getRest(message, url):
  #data_json = json.dumps(message)
  #headers = {'Content-type': 'application/json'}
  #response = requests.get(url, data=data_json, headers=headers)
  response = requests.get(url, verify=False)
  return response;

def postRest(message, url):
  #data_json = json.dumps(message)
  #headers = {'Content-type': 'application/json'}
  #response = requests.post(url, data=data_json, headers=headers)
  #print "Posting to "+url
  response = requests.post(url, verify=False)
  return response;

def read_file(filename):
  try:
    with open(filename, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print "%s file not found!!!"
      return ""

def sync_bics():
  global demozone_file
  global dbcs_host_file

  dbcs = read_file(dbcs_host_file)
  demozone = read_file(demozone_file)
  dbcs = dbcs.rstrip()
  demozone = demozone.rstrip()
  url = dbcs + "/apex/pdb1/anki/iotcs/setup/" + demozone
  iotcs = getRest("", url)
  if iotcs.status_code == 200:
    data = json.loads(iotcs.content)
    hostname = data["items"][0]["hostname"]
    port = data["items"][0]["port"]
    username = data["items"][0]["username"]
    password = data["items"][0]["password"]
    applicationid = data["items"][0]["applicationid"]
    integrationid = data["items"][0]["integrationid"]
    url = "https://" + hostname + ":" + str(port) + "/iot/api/v2/apps/" + applicationid + "/integrations/" + integrationid + "/sync/now"
    resp = requests.post(url, auth=(username, password))
    if resp.status_code != 202:
        print "Error synchronizing BICS: " + resp.status_code
    return resp.status_code
  else:
    print "Error retrieving IoTCS setup from DBCS: " + iotcs.status_code
    return iotcs.status_code

def reset_current_speed():
  return run_cmd(RESET_CURRENT_SPEED_DATA_CMD)

def reset_race_data():
  return run_cmd(RESET_RACE_DATA_CMD)

def sync_race(raceid):
  URI = UPDATE_CURRENT_RACE_CMD
  URI = URI.replace("{RACEID}", str(raceid))
  #Substitute {raceid} with current raceid
  return run_cmd(URI)

def get_lap(car):
  global race_lap_file
  filename = race_lap_file % car
  try:
    with open(filename, 'r') as f:
      first_line = f.readline()
      return(int(first_line))
  except (IOError):
      print "%s file not found. Creating..." % filename
      with open(filename,"w+") as f:
        f.write("0")
      os.chown(filename, piusergroup, piusergroup)
      return 0

def displayInfoRotation(cad):
  global currentInfoDisplay
  if currentInfoDisplay == INIT:
    initDisplay(cad)
  elif currentInfoDisplay == WIFI:
    wifiDisplay(cad)
  elif currentInfoDisplay == SNIFFERS:
    sniffersDisplay(cad)
  elif currentInfoDisplay == IOTPROXY:
    iotproxyDisplay(cad)
  elif currentInfoDisplay == REVERSEPORTS:
    reversePortsDisplay(cad)
  elif currentInfoDisplay == RACE:
    raceDisplay(cad)
  else:
    print "No more pages"

def initDisplay(cad):
    cad.lcd.clear()
    cad.lcd.set_cursor(0, 0)
    if not SETUP:
        cad.lcd.write("PRESS RIGHT BTN")
        cad.lcd.set_cursor(0, 1)
        cad.lcd.write("TO START SETUP")
    else:
        cad.lcd.write("Pi Version:"+getPiVersion())
        cad.lcd.set_cursor(0, 1)
        cad.lcd.write(getPiName())

def wifiDisplay(cad):
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Wifi:"+get_my_wifi())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(get_my_ip())
  cad.lcd.set_cursor(15, 1)
  cad.lcd.write(check_internet())

def sniffersDisplay(cad):
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("USB PORTS:    %02d" % get_usb_ports())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("SNIF RUNNING: %02d" % get_sniffers_running())

def iotproxyDisplay(cad):
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("WRAPPER: %s" % get_iotproxy_run_status())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("STATUS: %s" % get_iotproxy_status())

def raceDisplay(cad):
  status=get_race_status()
  id=get_race_count()
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Race status:")
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(status)
  cad.lcd.write( " (%s)" % id)

def raceLapsDisplay(cad):
  lap_Thermo=get_lap("Thermo")
  lap_GroundShock=get_lap("Ground Shock")
  lap_Skull=get_lap("Skull")
  lap_Guardian=get_lap("Guardian")
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("RACE TH:%02d GS:%02d" % (lap_Thermo,lap_GroundShock))
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("LAPS SK:%02d GU:%02d" % (lap_Skull,lap_Guardian))

def resetSniffer(event,snifferNumber):
  event.chip.lcd.clear()
  event.chip.lcd.set_cursor(0, 0)
  event.chip.lcd.write("Resetting\nSniffer "+str(snifferNumber))
  msg = run_cmd(KILL_SNIFFER_CMD + " "+str(snifferNumber))
  event.chip.lcd.set_cursor(0, 1)
  event.chip.lcd.write(msg)
  time.sleep(5)
  displayInfoRotation(event.chip)

def resetSniffers(event):
  event.chip.lcd.clear()
  event.chip.lcd.set_cursor(0, 0)
  event.chip.lcd.write("Resetting\nAll Sniffers")
  msg = run_cmd(KILL_SNIFFERS_CMD)
  time.sleep(5)
  event.chip.lcd.clear()
  event.chip.lcd.set_cursor(0, 0)
  event.chip.lcd.write(msg)
  time.sleep(5)
  displayInfoRotation(event.chip)

def reversePortsDisplay(cad):
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Checking")
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("Please, wait...")
  prx_status=check_reverse_proxy()
  node_status=check_nodejs()
  websocket_status=check_websocket()
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("PROXY:"+prx_status)
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("NODE:"+node_status )
  cad.lcd.set_cursor(9, 1)
  cad.lcd.write(" WS:" + websocket_status)

def resetLapFile(file):
  try:
    with open(file, 'r+') as f:
      f.seek(0)
      f.write("0")
      f.truncate()
  except (IOError):
      print "%s file not found. Creating..." % file
      with open(file,"w+") as f:
        f.write("0")
      os.chown(file, piusergroup, piusergroup)

def start_race(event):
    status = get_race_status()
    if status == "RACING":
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race already")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("started.Ignoring")
      time.sleep(5)
      displayInfoRotation(event.chip)
    else:
      id=inc_race_count()
      resetLapFile(race_lap_Thermo_file)
      resetLapFile(race_lap_GroundShock_file)
      resetLapFile(race_lap_Skull_file)
      resetLapFile(race_lap_Guardian_file)
      set_race_status("RACING")
      result = sync_race(id)
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race started!!")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("ID: %s %s" % (id,str(result)))
      time.sleep(5)
      displayInfoRotation(event.chip)

def stop_race(event):
    status = get_race_status()
    if status == "STOPPED":
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race already")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("stopped.Ignoring")
      time.sleep(5)
      displayInfoRotation(event.chip)
    else:
      id=get_race_count()
      set_race_status("STOPPED")
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race stopped!!")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("ID: %s" % id)
      time.sleep(3)
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Sync BICS")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("Please, wait...")
      result = sync_bics()
      result_speed = reset_current_speed()
      result_reset_data = reset_race_data()
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Sync BICS")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("Result: %d %s" % (result,result_speed))
      time.sleep(5)
      displayInfoRotation(event.chip)

def handleButton(button, screen, event):
  global buttonWaitingForConfirmation
#  print "Button %s at screen %s" % (button,screen)
  if screen == INIT:
    # 1: REBOOT
    # 2: POWEROFF
    # 5: CONFIRM
    if buttonWaitingForConfirmation != -1 and button == BUTTON5:
	  # Confirmation to previous command
	  if buttonWaitingForConfirmation == BUTTON1:
	    # REBOOT
	    CMD = REBOOT_CMD
	    msg = "REBOOTING"
	  else:
	    # POWEROFF
	    CMD = POWEROFF_CMD
	    msg = "HALTING SYSTEM"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  run_cmd(CMD)
    if button == BUTTON1 or button == BUTTON2:
	  buttonWaitingForConfirmation = button
	  if button == BUTTON1:
	     msg = "REBOOT REQUEST"
	  else:
	     msg = "POWEROFF REQUEST"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("CONFIRM RIGHTBTN")
    else:
	  if buttonWaitingForConfirmation != -1:
	    displayInfoRotation(event.chip)
	    buttonWaitingForConfirmation = -1
  elif screen == WIFI:
    # 1: RESET WIFI
    # 5: CONFIRM
    if buttonWaitingForConfirmation != -1 and button == BUTTON5:
	  # Confirmation to previous command
	  buttonWaitingForConfirmation = -1
	  msg = "RESETING WIFI"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  run_cmd(RESET_WIFI_CMD)
	  displayInfoRotation(event.chip)
    if button == BUTTON1:
	  buttonWaitingForConfirmation = button
	  msg = "WIFI RST REQUEST"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("CONFIRM RIGHTBTN")
    else:
	  if buttonWaitingForConfirmation != -1:
	    displayInfoRotation(event.chip)
	    buttonWaitingForConfirmation = -1
  elif screen == SNIFFERS:
    # 1: RESET SNIFFER FOR THERMO
    # 2: RESET SNIFFER FOR GROUND SHOCK
    # 3: RESET SNIFFER FOR SKULL
    # 4: RESET SNIFFER FOR GUARDIAN
    # 5: RESET ALL
	if button >= BUTTON1 and button <= BUTTON4:
	  resetSniffer(event, button)
	else:
	  resetSniffers(event)
  elif screen == IOTPROXY:
    # 1: RESTART
    # 5: CONFIRM
    if buttonWaitingForConfirmation != -1 and button == BUTTON5:
	  # Confirmation to previous command
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write("RESTARTING")
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("IOT PROXY...")
	  run_cmd(RESET_IOTPROXY_CMD)
    if button == BUTTON1:
	  buttonWaitingForConfirmation = button
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write("RESTART REQUEST")
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("CONFIRM RIGHTBTN")
    else:
	  if buttonWaitingForConfirmation != -1:
	    displayInfoRotation(event.chip)
	    buttonWaitingForConfirmation = -1
  elif screen == REVERSEPORTS:
    # 1: RESTART AUTOSSH PROCESS
    # 2: RESTART NODEJS
    # 5: CONFIRM
    if buttonWaitingForConfirmation != -1 and button == BUTTON5:
	  # Confirmation to previous command
	  if buttonWaitingForConfirmation == BUTTON1:
	    # RESTART AUTOSSH PROCESS
	    CMD = RESET_AUTOSSH_CMD
	    msg = "RESTARTING SSH\nTUNNELING"
	  else:
	    # RESTART NODEJS
	    CMD = RESET_NODEJS_CMD
	    msg = "RESTARTING\nNODEJS"
	  buttonWaitingForConfirmation = -1
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  run_cmd(CMD)
	  displayInfoRotation(event.chip)
    if button == BUTTON1:
	  buttonWaitingForConfirmation = button
	  msg = "AUTOSSH RST REQ"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("CONFIRM RIGHTBTN")
    elif button == BUTTON2:
	  buttonWaitingForConfirmation = button
	  msg = "NODEJS RESET REQ"
	  cad.lcd.clear()
	  cad.lcd.set_cursor(0, 0)
	  cad.lcd.write(msg)
	  cad.lcd.set_cursor(0, 1)
	  cad.lcd.write("CONFIRM RIGHTBTN")
    else:
	  if buttonWaitingForConfirmation != -1:
	    displayInfoRotation(event.chip)
	    buttonWaitingForConfirmation = -1
  elif screen == RACE:
    # 1: START RACE
    # 2: STOP RACE
    if button == BUTTON1:
	  start_race(event)
    elif button == BUTTON2:
	  stop_race(event)
  else:
    print "UNKNOWN SCREEN: %s" % screen

def buttonPressed(event):
#  print "Event: "+str(event.pin_num)
  global currentInfoDisplay

  if event.pin_num == BUTTONLEFT:
    if currentInfoDisplay > 0:
      currentInfoDisplay=currentInfoDisplay-1
    else:
      currentInfoDisplay=maxInfoDisplay
    displayInfoRotation(event.chip)
    buttonWaitingForConfirmation = -1
  elif event.pin_num == BUTTONRIGHT:
    if currentInfoDisplay < maxInfoDisplay:
      currentInfoDisplay=currentInfoDisplay+1
    else:
      currentInfoDisplay=0
    displayInfoRotation(event.chip)
    buttonWaitingForConfirmation = -1
  elif event.pin_num == BUTTONMIDDLE:
    displayInfoRotation(event.chip)
    buttonWaitingForConfirmation = -1
  elif event.pin_num >= BUTTON1 and event.pin_num <= BUTTON5:
    handleButton(event.pin_num,currentInfoDisplay, event)
  else:
    event.chip.lcd.set_cursor(0, 14)
    event.chip.lcd.write(str(event.pin_num))

def get_race_status():
  try:
    with open(race_status_file, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print "%s file not found. Creating..." % race_status_file
      with open(race_status_file,"w+") as f:
        f.write("UNKNOWN")
      os.chown(race_status_file, piusergroup, piusergroup)
      return "UNKNOWN"

def get_race_count():
  try:
    with open(race_count_file, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print "%s file not found. Creating..." % race_count_file
      with open(race_count_file,"w+") as f:
        f.write("0")
      os.chown(race_count_file, piusergroup, piusergroup)
      return "0"

def set_race_status(status):
  try:
    with open(race_status_file, 'r+') as f:
      f.seek(0)
      f.write(status)
      f.truncate()
  except (IOError):
      print "%s file not found. Creating..." % race_status_file
      with open(race_status_file,"w+") as f:
        f.write(status)
      os.chown(race_status_file, piusergroup, piusergroup)

def set_race_count(count):
  try:
    with open(race_count_file, 'r+') as f:
      f.seek(0)
      f.write("%s" % count)
      f.truncate()
  except (IOError):
      print "%s file not found. Creating..." % race_count_file
      with open(race_count_file,"w+") as f:
        f.write(count)
      os.chown(race_count_file, piusergroup, piusergroup)

def inc_race_count():
  c=int(get_race_count())
  c=c+1
  set_race_count(c)
  return c

def run_cmd(cmd):
  msg = subprocess.check_output(cmd, shell=True).decode('utf-8')
  return msg

def get_usb_ports():
  return int(run_cmd(USB_PORTS_CMD))

def get_sniffers_running():
  return int(run_cmd(SNIFFERS_RUNNING_CMD))

def get_iotproxy_run_status():
  return run_cmd(CHECK_IOTPROXY_CMD)

def get_iotproxy_status():
  return run_cmd(CHECK_IOTPROXY_STATUS_CMD)

def get_my_wifi():
  ssid = run_cmd(GET_WIFI_CMD)[:-1]
  l = len(ssid)
  if l > 11:
      wifi = ssid[:4] + ".." + ssid[len(ssid)-5:]
  else:
      wifi = ssid
  return wifi

def get_my_ip():
  return run_cmd(GET_IP_CMD)[:-1]

def check_internet():
  return run_cmd(CHECK_INTERNET_CMD)

def check_reverse_proxy():
  listeners=int(run_cmd(CHECK_REVERSEPROXY_CMD))
  if listeners > 0:
     return "OK"
  else:
     return "NOK"

def check_nodejs():
   return run_cmd(CHECK_NODEUP_CMD)

def check_websocket():
   return run_cmd(CHECK_WEBSOCKET_CMD)

def getPiName():
  with open(demozone_file, 'r') as f:
    return(f.readline())

def getPiVersion():
  with open('/home/pi/piImgVersion.txt', 'r') as f:
    first_line = f.readline()
    return(first_line)

def getPiId():
  with open('/home/pi/PiId.txt', 'r') as f:
    first_line = f.readline().rstrip()
    return(first_line)

cad = pifacecad.PiFaceCAD()
cad.lcd.backlight_on()
cad.lcd.blink_off()
cad.lcd.cursor_off()

SETUP = os.path.isfile(demozone_file)
if not SETUP:
    maxInfoDisplay = 1

initDisplay(cad)
listener = pifacecad.SwitchEventListener(chip=cad)
for i in range(8):
  listener.register(i, pifacecad.IODIR_FALLING_EDGE, buttonPressed)
listener.activate()
