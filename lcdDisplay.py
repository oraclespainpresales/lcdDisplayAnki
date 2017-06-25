import pifacecad
import sys
import subprocess
import time
import requests
import json
import pprint
import os
import glob
import shutil
#import threading

pi_home="/home/pi"
setup_home="/setup"

SETUP=False
SETUPSTEP=0
EVENTSCHEDULED=False
demozone=""
proxyport=-1
SETUP_demozone_file=pi_home+setup_home+"/demozone.TOSETUP"
SETUP_redirects_file=pi_home+setup_home+"/redirects.TOSETUP"

DBSERVER=os.environ['DBSERVER']
PROXYSERVER=os.environ['PROXYSERVER']
SOASERVER=os.environ['SOASERVER']

INIT=0
WIFI=1
EVENT=2
SNIFFERS=3
IOTPROXY=4
REVERSEPORTS=5
RACE=6
currentInfoDisplay=0
maxInfoDisplay=6
rightMaxInfoDisplay=maxInfoDisplay
buttonWaitingForConfirmation=-1

BUTTON1=0
BUTTON2=1
BUTTON3=2
BUTTON4=3
BUTTON5=4
BUTTONMIDDLE=5
BUTTONLEFT=6
BUTTONRIGHT=7

pi_img_version_file=pi_home+setup_home+"/PiImgVersion.dat"
pi_id_file=pi_home+setup_home+"/PiId.dat"
demozone_file=pi_home+setup_home+"/demozone.dat"
drone_port_file=pi_home+setup_home+"/drone_port.dat"
redirects_file=pi_home+setup_home+"/redirects"
race_status_file=pi_home+setup_home+"/race_status.dat"
race_count_file=pi_home+setup_home+"/race_count.dat"
race_lap_Thermo_file=pi_home+setup_home+"/race_lap_Thermo.dat"
race_lap_GroundShock_file=pi_home+setup_home+"/race_lap_Ground Shock.dat"
race_lap_Skull_file=pi_home+setup_home+"/race_lap_Skull.dat"
race_lap_Guardian_file=pi_home+setup_home+"/race_lap_Guardian.dat"
race_lap_file=pi_home+setup_home+"/race_lap_%s.dat"
dbcs_host_file=pi_home+setup_home+"/dbcs.dat"

eventserver = "http://" + PROXYSERVER + ":10001"
EVENTURI = "/event/race"

GET_IP_CMD = "hostname --all-ip-addresses"
GET_WIFI_CMD = "sudo iwconfig wlan0 | grep ESSID | awk -F\":\" '{print $2}' | awk -F'\"' '{print $2}'"
RESET_WIFI_CMD = "sudo ifdown wlan0;sleep 5;sudo ifup wlan0"
CHECK_INTERNET_CMD = "sudo ping -q -w 1 -c 1 8.8.8.8 > /dev/null 2>&1 && echo U || echo D"
CHECK_IOTPROXY_CMD = "[ `ps -ef | grep -v grep | grep iotcswrapper| grep -v forever  | wc -l` -eq 1 ] && echo UP || echo DOWN"
CHECK_IOTPROXY_STATUS_CMD = "curl http://localhost:8888/iot/status 2> /dev/null || echo ERROR"
RESET_CURRENT_SPEED_DATA_CMD = "curl -i -m 5 -X POST http://" + SOASERVER + ":8001/BAMHelper/ResetCurrentSpeedService/anki/reset/speed/{DEMOZONE} 2>/dev/null | grep HTTP | awk '{print $2}'"
UPDATE_CURRENT_RACE_CMD = "curl -i -m 5 -X POST http://" + SOASERVER + ":8001/BAMHelper/UpdateCurrentRaceService/anki/event/currentrace/{DEMOZONE}/{RACEID} 2>/dev/null | grep HTTP | awk '{print $2}'"
RESET_RACE_DATA_CMD = "curl -i -m 5 -X POST http://" + SOASERVER + ":8001/BAMHelper/ResetBAMDataService/anki/reset/bam/{DEMOZONE} 2>/dev/null | grep HTTP | awk '{print $2}'"
CHECK_REVERSEPROXY_CMD = "ssh -i /home/pi/.ssh/anki_drone $reverseProxy \"netstat -ant | grep LISTEN | grep {DRONEPORT} | wc -l\""
KILL_REVERSEPROXY_CMD = "ssh -i /home/pi/.ssh/anki_drone $reverseProxy \"/home/opc/killsshd.sh {PORT}\""
CHECK_NODEUP_CMD = "wget -q -T 5 --tries 2 -O - http://$reverseProxy:{DRONEPORT}/drone > /dev/null && echo OK || echo NOK"
CHECK_WEBSOCKET_CMD = "wget -q -T 5 --tries 1 -O - http://$reverseProxy:{DRONEPORT}/drone/ping > /dev/null && echo OK || echo NOK"
RESET_AUTOSSH_CMD = "pkill autossh;/home/pi/bin/setupReverseSSHPorts.sh " + redirects_file
RESET_NODEJS_CMD = "forever stop drone;forever start --uid drone --append /home/pi/node/dronecontrol/server.js"
USB_PORTS_CMD = "ls -1 /dev/ttyU* 2>/dev/null | wc -l"
SNIFFERS_RUNNING_CMD = "ps -ef | grep -v grep | grep  ttyUSB | wc -l"
REBOOT_CMD = "sudo reboot"
POWEROFF_CMD = "sudo poweroff"
KILL_SNIFFER_CMD = "/home/pi/ankiEventSniffer/killSniffer.sh"
KILL_SNIFFERS_CMD = "/home/pi/ankiEventSniffer/killSniffers.sh"
RESET_IOTPROXY_CMD = "forever stop iot;forever start --uid iot --append /home/pi/node/iotcswrapper/server.js -d /home/pi/node/iotcswrapper/current-device.conf"
CREATE_DEVICE_LINK = "ln -s /home/pi/node/iotcswrapper/{DEVICEFILE} /home/pi/node/iotcswrapper/current-device.conf"
piusergroup=1000

#barrier = threading.Barrier(4)

def getRest(message, url):
  #data_json = json.dumps(message)
  #headers = {'Content-type': 'application/json'}
  #response = requests.get(url, data=data_json, headers=headers)
  try:
    response = requests.get(url, verify=False, timeout=5)
    return response;
  except requests.exceptions.Timeout:
    dummy = requests.Response()
    dummy.status_code=408
    return dummy;

def postRest(message, url):
  data_json = json.dumps(message)
  headers = {'Content-type': 'application/json'}
  try:
      response = requests.post(url, data=data_json, headers=headers, verify=False, timeout=1)
      return response;
  except:
      dummy = requests.Response()
      dummy.status_code = 500
      return dummy;

def read_file(filename):
  try:
    with open(filename, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print ("%s file not found!!!")
      return ""

def get_demozone():
  global demozone_file
  d = read_file(demozone_file)
  return(d.rstrip())

def get_device_conf(_demozone):
  global DBSERVER
  url = "https://" + DBSERVER + "/ords/pdb1/anki/device/" + _demozone
  device = getRest("", url)
  if device.status_code == 200:
    data = json.loads(device.content)
    if len(data["items"]) == 0:
        # Demozone's device is not present in the table
        return -1
    else:
        deviceid = data["items"][0]["deviceid"]
        devicedata = data["items"][0]["data"]
        devicefilename = _demozone + "_" + deviceid + ".conf"
        with open("/home/pi/node/iotcswrapper/" + devicefilename,'w+') as f:
            f.write(devicedata)
        CMD = CREATE_DEVICE_LINK.replace("{DEVICEFILE}", devicefilename)
        run_cmd(CMD)
        return 0
  else:
    return -2

def sync_bics():
  global DBSERVER
  url = "https://" + DBSERVER + "/ords/pdb1/anki/iotcs/setup/" + get_demozone()
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
    try:
        resp = requests.post(url, verify=False, auth=(username, password))
        if resp.status_code != 202:
            print ("Error synchronizing BICS: " + str(resp.status_code))
        return resp.status_code
    except requests.exceptions.Timeout:
        print ("Error synchronizing BICS: timeout")
        return 408
  else:
    print ("Error retrieving IoTCS setup from DBCS: " + str(iotcs.status_code))
    return iotcs.status_code

def get_current_event():
  global EVENTSCHEDULED
  global maxInfoDisplay
  global rightMaxInfoDisplay
  global DBSERVER

  EVENTSCHEDULED = False
  maxInfoDisplay = 2
  currentdate = time.strftime("%m-%d-%Y")
  url = "https://" + DBSERVER + "/ords/pdb1/anki/events/" + get_demozone() + "/" + currentdate
  try:
    currentevent = getRest("", url)
    if currentevent.status_code == 200:
      data = json.loads(currentevent.content)
      if len(data["items"]) == 0:
        return 404
      else:
        EVENTSCHEDULED = True
        maxInfoDisplay = rightMaxInfoDisplay
        return 200
    else:
      print ("Error retrieving current registered event from DBCS: " + str(currentevent.status_code))
      return currentevent.status_code
  except:
    print ("Error retrieving event information")
    return 500

def get_lap(car):
  global race_lap_file
  filename = race_lap_file % car
  try:
    with open(filename, 'r') as f:
      first_line = f.readline()
      return(int(first_line))
  except (IOError):
      print ("%s file not found. Creating..." % filename)
      with open(filename,"w+") as f:
        f.write("0")
      os.chown(filename, piusergroup, piusergroup)
      return 0

def displayInfoRotation():
  global currentInfoDisplay
  global cad
#  global barrier
#  barrier.wait() # makes the listener to deactivate itself
  if currentInfoDisplay == INIT:
    initDisplay(cad)
  elif currentInfoDisplay == WIFI:
    wifiDisplay(cad)
  elif currentInfoDisplay == EVENT:
    eventDisplay(cad)
  elif currentInfoDisplay == SNIFFERS:
    sniffersDisplay(cad)
  elif currentInfoDisplay == IOTPROXY:
    iotproxyDisplay(cad)
  elif currentInfoDisplay == REVERSEPORTS:
    reversePortsDisplay(cad)
  elif currentInfoDisplay == RACE:
    raceDisplay(cad)
  else:
    print ("No more pages")
#  barrier.wait() # makes the listener to activate itself again

def initDisplay():
    global cad
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

def wifiDisplay():
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Wifi:"+get_my_wifi())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(get_my_ip())
  cad.lcd.set_cursor(15, 1)
  cad.lcd.write(check_internet())

def eventDisplay():
  global cad
  today = time.strftime("%d-%b-%y")
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Today: " + today)
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("PLEASE WAIT...")
  e = get_current_event()
  if e == 200:
      msg = "DEMO SCHEDULED"
  elif e == 500:
      msg = "ERROR.CHK NETWRK"
  else:
      msg = "NODEMO SCHEDULED"
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(msg)

def sniffersDisplay(cad):
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("USB PORTS:    %02d" % get_usb_ports())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("SNIF RUNNING: %02d" % get_sniffers_running())

def iotproxyDisplay(cad):
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("WRAPPER: %s" % get_iotproxy_run_status())
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("STATUS: %s" % get_iotproxy_status())

def raceDisplay(cad):
  global cad
  status=get_race_status()
  id=get_race_count()
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Race status:")
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(status)
  cad.lcd.write( " (%s)" % id)

def raceLapsDisplay(cad):
  global cad
  lap_Thermo=get_lap("Thermo")
  lap_GroundShock=get_lap("Ground Shock")
  lap_Skull=get_lap("Skull")
  lap_Guardian=get_lap("Guardian")
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("RACE TH:%02d GS:%02d" % (lap_Thermo,lap_GroundShock))
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("LAPS SK:%02d GU:%02d" % (lap_Skull,lap_Guardian))

def resetSniffer(snifferNumber):
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Resetting\nSniffer "+str(snifferNumber))
  msg = run_cmd(KILL_SNIFFER_CMD + " "+str(snifferNumber))
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write(msg)
  time.sleep(5)
  displayInfoRotation()

def resetSniffers():
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Resetting\nAll Sniffers")
  msg = run_cmd(KILL_SNIFFERS_CMD)
  time.sleep(5)
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write(msg)
  time.sleep(5)
  displayInfoRotation()

def reversePortsDisplay():
  global cad
  cad.lcd.clear()
  cad.lcd.set_cursor(0, 0)
  cad.lcd.write("Checking")
  cad.lcd.set_cursor(0, 1)
  cad.lcd.write("Please, wait.")
  prx_status=check_reverse_proxy()
  cad.lcd.write(".")
  node_status=check_nodejs()
  cad.lcd.write(".")
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
      print ("%s file not found. Creating..." % file)
      with open(file,"w+") as f:
        f.write("0")
      os.chown(file, piusergroup, piusergroup)

def start_race():
    global cad
    status = get_race_status()
    if status == "RACING":
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race already")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("started.Ignoring")
      time.sleep(5)
      displayInfoRotation()
    else:
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Starting race")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("Please, wait...")
      id=inc_race_count()
      resetLapFile(race_lap_Thermo_file)
      resetLapFile(race_lap_GroundShock_file)
      resetLapFile(race_lap_Skull_file)
      resetLapFile(race_lap_Guardian_file)

      jsonData = [{"payload":{"data":{"data_demozone": demozone.lower(),"raceId":id,"raceStatus":"RACING"}}}]
      postRest(jsonData, "%s%s" % (eventserver,EVENTURI) )

      set_race_status("RACING")
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race started!!")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("ID: %s" % id)
      time.sleep(5)
      displayInfoRotation()

def stop_race():
    global cad
    status = get_race_status()
    if status == "STOPPED":
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race already")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("stopped.Ignoring")
      time.sleep(5)
      displayInfoRotation()
    else:
      id=get_race_count()
      set_race_status("STOPPED")
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Race stopped!!")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("ID: %s" % id)

      jsonData = [{"payload":{"data":{"data_demozone": demozone.lower(),"raceId":int(id),"raceStatus":"STOPPED"}}}]
      postRest(jsonData, "%s%s" % (eventserver,EVENTURI) )

      time.sleep(3)
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Sync BICS")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("Please, wait...")
      result = sync_bics()
      cad.lcd.clear()
      cad.lcd.set_cursor(0, 0)
      cad.lcd.write("Sync BICS")
      cad.lcd.set_cursor(0, 1)
      cad.lcd.write("Result: %d" % result)
      time.sleep(5)
      displayInfoRotation()

def handleButton(button, screen):
    global cad
    global buttonWaitingForConfirmation
    global SETUPSTEP
    global dbcs
    global demozone
    global proxyport
    global DBSERVER
#  print "Button %s at screen %s" % (button,screen)
    if screen == INIT and SETUP:
        # 1: REBOOT
        # 2: POWEROFF
        # 3: RESET RPi
        # 5: CONFIRM
        if buttonWaitingForConfirmation != -1 and button == BUTTON5:
    	  # Confirmation to previous command
            if buttonWaitingForConfirmation == BUTTON1:
                # REBOOT
                CMD = REBOOT_CMD
                msg = "REBOOTING"
            elif buttonWaitingForConfirmation == BUTTON2:
        	    # POWEROFF
        	    CMD = POWEROFF_CMD
        	    msg = "HALTING SYSTEM"
            else:
                # RESET RPi
                set_race_count(0)
                os.remove(pi_id_file)
                os.remove(demozone_file)
                shutil.copy(SETUP_demozone_file + ".org", SETUP_demozone_file)
                os.remove(redirects_file)
                shutil.copy(SETUP_redirects_file + ".org", SETUP_redirects_file)
                setRaceCountToZero(race_lap_Thermo_file)
                setRaceCountToZero(race_lap_GroundShock_file)
                setRaceCountToZero(race_lap_Skull_file)
                setRaceCountToZero(race_lap_Guardian_file)
                # Remove any device file
                devicefiles = glob.glob("/home/pi/node/iotcswrapper/*.conf")
                for file in devicefiles:
                    os.remove(file)
                cad.lcd.clear()
                cad.lcd.set_cursor(0, 0)
                cad.lcd.write("RESET COMPLETE")
                cad.lcd.set_cursor(0, 1)
                cad.lcd.write("PLEASE REBOOT")
                return
            cad.lcd.clear()
            cad.lcd.set_cursor(0, 0)
            cad.lcd.write(msg)
            run_cmd(CMD)
        if button == BUTTON1 or button == BUTTON2 or button == BUTTON3:
            buttonWaitingForConfirmation = button
            if button == BUTTON1:
                msg = "REBOOT REQUEST"
            elif button == BUTTON2:
                msg = "POWEROFF REQUEST"
            else:
                msg = "RPi RESET RQUEST"
            cad.lcd.clear()
            cad.lcd.set_cursor(0, 0)
            cad.lcd.write(msg)
            cad.lcd.set_cursor(0, 1)
            cad.lcd.write("CONFIRM RIGHTBTN")
        else:
            if buttonWaitingForConfirmation != -1:
                displayInfoRotation()
                buttonWaitingForConfirmation = -1
    elif screen == WIFI and SETUP:
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
            displayInfoRotation()
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
                displayInfoRotation()
                buttonWaitingForConfirmation = -1
    elif not SETUP:
        if button == BUTTON1 or button == BUTTON2:
            if screen == INIT:
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
            elif screen == WIFI:
                if button == BUTTON1:
                    buttonWaitingForConfirmation = button
                    msg = "WIFI RST REQUEST"
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write(msg)
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("CONFIRM RIGHTBTN")
        elif button == BUTTON5:
            if buttonWaitingForConfirmation != -1:
                if screen == INIT:
                    if buttonWaitingForConfirmation == BUTTON1:
                        # REBOOT
                        CMD = REBOOT_CMD
                        msg = "REBOOTING"
                    else:
                        # POWEROFF
                        CMD = POWEROFF_CMD
                        msg = "HALTING SYSTEM"
                    buttonWaitingForConfirmation = -1
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write(msg)
                    run_cmd(CMD)
                elif screen == WIFI:
                    buttonWaitingForConfirmation = -1
                    msg = "RESETING WIFI"
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write(msg)
                    run_cmd(RESET_WIFI_CMD)
                    displayInfoRotation()
            else:
                # SETUP mode
                if SETUPSTEP == -1:
                    SETUPSTEP = SETUPSTEP + 1
                    initDisplay(cad)
                elif SETUPSTEP == 0:
                    SETUPSTEP = SETUPSTEP + 1
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write(getPiId())
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("RIGHTBTN TO CONT")
                elif SETUPSTEP == 1:
                    # Retrieving RPi data from DB
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write("RETRIEVING DATA")
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("FOR THIS RPi...")
                    url = "https://" + DBSERVER + "/ords/pdb1/anki/demozone/rpi/" + getPiId()
                    result = getRest("", url)
                    if result.status_code == 200:
                        SETUPSTEP = SETUPSTEP + 1
                        data = json.loads(result.content)
                        if len(data["items"]) > 0:
                            demozone = data["items"][0]["id"]
                            proxyport = data["items"][0]["proxyport"]
                            cad.lcd.clear()
                            cad.lcd.set_cursor(0, 0)
                            cad.lcd.write("ZONE:" + demozone)
                            cad.lcd.set_cursor(0, 1)
                            cad.lcd.write("RIGHTBTN TO CONT")
                        else:
                            SETUPSTEP = -1
                            cad.lcd.clear()
                            cad.lcd.set_cursor(0, 0)
                            cad.lcd.write("RPi NOT FOUND")
                            cad.lcd.set_cursor(0, 1)
                            cad.lcd.write("RIGHTBTN TO CONT")
                    else:
                        cad.lcd.clear()
                        cad.lcd.set_cursor(0, 0)
                        cad.lcd.write("ERROR: " + str(result.status_code))
                        cad.lcd.set_cursor(0, 1)
                        cad.lcd.write("RIGHTBTN TO RTRY")
                elif SETUPSTEP == 2:
                    # Retrieving device data from DB
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write("GETTING DEVICE")
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("FOR DEMOZONE...")
                    result = get_device_conf(demozone)
                    # -1: does not exist. -2: error. Other: OK
                    if result == -1:
                        cad.lcd.clear()
                        cad.lcd.set_cursor(0, 0)
                        cad.lcd.write("DEVICE NOT FOUND")
                        cad.lcd.set_cursor(0, 1)
                        cad.lcd.write("RIGHTBTN TO RTRY")
                    elif result == -2:
                        cad.lcd.clear()
                        cad.lcd.set_cursor(0, 0)
                        cad.lcd.write("ERROR GETTING DV")
                        cad.lcd.set_cursor(0, 1)
                        cad.lcd.write("RIGHTBTN TO RTRY")
                    else:
                        SETUPSTEP = SETUPSTEP + 1
                        cad.lcd.clear()
                        cad.lcd.set_cursor(0, 0)
                        cad.lcd.write("DEVICE SET OK")
                        cad.lcd.set_cursor(0, 1)
                        cad.lcd.write("RIGHTBTN TO CONT")
                elif SETUPSTEP == 3:
                    # Setting all files based on retrieved data
                    SETUPSTEP = SETUPSTEP + 1
                    setDemozoneFile(demozone)
                    setRedirectsFile(proxyport)
                    setDronePortFile(proxyport)
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write("SETUP COMPLETE")
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("PLEASE REBOOT")
                elif SETUPSTEP == 4:
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0, 0)
                    cad.lcd.write("SETUP COMPLETE")
                    cad.lcd.set_cursor(0, 1)
                    cad.lcd.write("PLEASE REBOOT")
    elif screen == SNIFFERS:
        # 1: RESET SNIFFER FOR THERMO
        # 2: RESET SNIFFER FOR GROUND SHOCK
        # 3: RESET SNIFFER FOR SKULL
        # 4: RESET SNIFFER FOR GUARDIAN
        # 5: RESET ALL
        if button >= BUTTON1 and button <= BUTTON4:
            resetSniffer(button)
    	else:
            resetSniffers()
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
                displayInfoRotation()
                buttonWaitingForConfirmation = -1
    elif screen == REVERSEPORTS:
        # 1: RESTART AUTOSSH PROCESS
        # 2: RESTART NODEJS
        # 5: CONFIRM
        if buttonWaitingForConfirmation != -1 and button == BUTTON5:
            # Confirmation to previous command
            cad.lcd.clear()
            cad.lcd.set_cursor(0, 0)
            if buttonWaitingForConfirmation == BUTTON1:
                # RESTART AUTOSSH PROCESS
                cad.lcd.write("RESTARTING SSH\nTUNNELING")
                subport = str(proxyport)[-2:]
                _KILL_REVERSEPROXY_CMD = KILL_REVERSEPROXY_CMD.replace("{PORT}", subport)
                print _KILL_REVERSEPROXY_CMD
                run_cmd(RESET_AUTOSSH_CMD)
                run_cmd(_KILL_REVERSEPROXY_CMD)
            else:
                # RESTART NODEJS
                cad.lcd.write("RESTARTING\nNODEJS")
                run_cmd(RESET_NODEJS_CMD)
            buttonWaitingForConfirmation = -1
            displayInfoRotation()
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
                displayInfoRotation()
                buttonWaitingForConfirmation = -1
    elif screen == RACE:
        # 1: START RACE
        # 2: STOP RACE
        if button == BUTTON1:
            start_race()
        elif button == BUTTON2:
            stop_race()
    else:
        print ("UNKNOWN SCREEN: %s" % screen)

def buttonPressed(buttonId):
#  print "Event: "+str(event.pin_num)
  global currentInfoDisplay

  if buttonId == BUTTONLEFT:
    if currentInfoDisplay > 0:
      currentInfoDisplay=currentInfoDisplay-1
    else:
      currentInfoDisplay=maxInfoDisplay
    displayInfoRotation()
    buttonWaitingForConfirmation = -1
  elif buttonId == BUTTONRIGHT:
    if currentInfoDisplay < maxInfoDisplay:
      currentInfoDisplay=currentInfoDisplay+1
    else:
      currentInfoDisplay=0
    displayInfoRotation()
    buttonWaitingForConfirmation = -1
  elif buttonId == BUTTONMIDDLE:
    displayInfoRotation()
    buttonWaitingForConfirmation = -1
  elif buttonId >= BUTTON1 and buttonId <= BUTTON5:
    handleButton(buttonId,currentInfoDisplay)
  else:
    cad.lcd.set_cursor(0, 14)
#    cad.lcd.write(str(event.pin_num))

def get_race_status():
  try:
    with open(race_status_file, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print ("%s file not found. Creating..." % race_status_file)
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
      print ("%s file not found. Creating..." % race_count_file)
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
      print ("%s file not found. Creating..." % race_status_file)
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
      print ("%s file not found. Creating..." % race_count_file)
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
  return run_cmd(GET_IP_CMD).split(" ")[0]

def check_internet():
  return run_cmd(CHECK_INTERNET_CMD)

def check_reverse_proxy():
  global proxyport
  URI = CHECK_REVERSEPROXY_CMD
  URI = URI.replace("{DRONEPORT}", proxyport)
  listeners=int(run_cmd(URI))
  if listeners > 0:
     return "OK"
  else:
     return "NOK"

def check_nodejs():
   global proxyport
   URI = CHECK_NODEUP_CMD
   URI = URI.replace("{DRONEPORT}", proxyport)
   return run_cmd(URI)

def check_websocket():
   global proxyport
   URI = CHECK_WEBSOCKET_CMD
   URI = URI.replace("{DRONEPORT}", proxyport)
   return run_cmd(URI)

def getPiName():
  with open(demozone_file, 'r') as f:
    return(f.readline())

def getPiVersion():
  with open(pi_img_version_file, 'r') as f:
    first_line = f.readline()
    return(first_line)

def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"
  return cpuserial

def getPiId():
  try:
    with open(pi_id_file, 'r') as f:
      first_line = f.readline().rstrip()
      return(first_line)
  except (IOError):
      print ("%s file not found. Creating..." % pi_id_file)
      serial = getserial()
      with open(pi_id_file,"w+") as f:
        f.write(serial)
      return(serial)

def setDemozoneFile(_demozone):
    with open(SETUP_demozone_file, 'r+') as f:
        f.seek(0)
        f.write(_demozone)
        f.truncate()
        f.close()
    os.rename(SETUP_demozone_file, demozone_file)

def setDronePortFile(_port):
    try:
        f = open(drone_port_file, 'r+')
    except IOError:
        f = open(drone_port_file, 'w')
    f.seek(0)
    f.write(str(_port))
    f.truncate()
    f.close()

def getDronePortFile():
  try:
    with open(drone_port_file, 'r') as f:
      first_line = f.readline()
      return(first_line)
  except (IOError):
      print ("%s file not found!!!" % drone_port_file)
      return "0"

def setRedirectsFile(_proxyport):
    with open(SETUP_redirects_file, 'r+') as f:
        data = f.read()
        data = data.replace("[DRONEPORT]", str(_proxyport))
        data = data.replace("[SSHPORT]", "22" + str(_proxyport)[-2:])
        data = data.replace("[ADMINPORT]", "89" + str(_proxyport)[-2:])
        f.seek(0)
        f.write(data)
        f.truncate()
        f.close()
    os.rename(SETUP_redirects_file, redirects_file)

def setRaceCountToZero(fName):
    with open(fName, 'r+') as f:
        f.seek(0)
        f.write("0")
        f.truncate()
        f.close()

cad = pifacecad.PiFaceCAD()
cad.lcd.backlight_on()
cad.lcd.blink_off()
cad.lcd.cursor_off()

SETUP = os.path.isfile(demozone_file)
if not SETUP:
    maxInfoDisplay = 1
    SETUPSTEP=0
else:
    demozone = get_demozone()
    proxyport = getDronePortFile()
    get_current_event()

initDisplay(cad)
#listener = pifacecad.SwitchEventListener(chip=cad)
#for i in range(8):
#  listener.register(i, pifacecad.IODIR_FALLING_EDGE, buttonPressed)
#  listener.register(i, pifacecad.IODIR_RISING_EDGE, buttonPressed)

#listener.activate()

FLAGS = [0,0,0,0,0,0,0,0]
OLDFLAGS = [0,0,0,0,0,0,0,0]

while True:
    time.sleep(0.1)
    for i,e in enumerate(FLAGS):
        FLAGS[i] = cad.switches[i].value
    #print FLAGS
    for i,e in enumerate(FLAGS):
        if OLDFLAGS[i] == 1 and FLAGS[i] == 0:
            OLDFLAGS[i] = 0
            print "PRESSED & UNPRESSED BUTTON #" + str(i)
            buttonPressed(i)
        else:
            OLDFLAGS[i] = FLAGS[i]

#while True:
#    listener.activate()
#    barrier.wait()
#    listener.deactivate()
#    barrier.wait()
#    barrier = threading.Barrier(4)
