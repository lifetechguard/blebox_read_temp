import argparse
import json
import sys
import time
from datetime import datetime

import requests
import sqlite3

# values used as input
ANY_LITERAL = "ANY"
ASK_LITERAL = "ASK"

# extra variables
debug = False
debug_content = False
authenticated = False
http_session_blebox = requests.Session()
http_session_blebox.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'})

http_session_influx = requests.Session()

def show_debug(session_response):
    if session_response.status_code != 200 and session_response.status_code != 204:
        print("\t * ERR CODE: " + str(session_response.status_code))
        exit(1)
    if debug:
        if session_response.history:
            for histreq in session_response.history:
                print("\tPrevious status   :\t {}".format(histreq.status_code))
                print("\tPrevious URL      :\t {}".format(histreq.url))
                print("\tPrevious Headers  :\t {}".format(histreq.headers))
                if debug_content:
                    print("\tPrevious Content  :\t {}".format(histreq.text))
                print("\n")
        print("URL                    :\t {}".format(session_response.request.url))
        print("URL method             :\t {}".format(session_response.request.method))
        print("Request headers        :\t {}".format(session_response.request.headers))
        print("Previous status code   :\t {}".format(session_response.history))
        print("Current status code    :\t {}".format(session_response.status_code))
        print("Current http headers   :\t {}".format(session_response.headers))
        if debug_content:
            print("Page content           :\t {}".format(session_response.text))
        print("-------------------------------------------------------------------\n\n")

def authenticate(login, password):
    global authenticated
    if not authenticated:
        print("[INFO] Logging in...")

        # Open login page
        login_url = "https://portal.blebox.eu/auth/login/"
        login_parameters = {
            "userIdentifier":login ,
            "password": password
        }
        login_response = http_session_blebox.post(login_url,json=login_parameters)
        login_response.raise_for_status()
        show_debug(login_response)
        print("[INFO] Successfully logged in")
        authenticated = True

def list_devices(http_session_blebox):
    global authenticated
    if authenticated:
        devices_list_response = http_session_blebox.get("https://portal.blebox.eu/api/devices/")
        show_debug(devices_list_response)
        if devices_list_response.status_code == 200:
            print("[INF] Device listing")
            return devices_list_response.json()['devices']
        else:
            print("[ERROR] Device list error")
            authenticated = False
            return False
    else:
        print("[ERROR] Not authenticated")
        authenticated = False
        return False 

def get_sensor_data(http_session_blebox,device_id,device_location):
    global authenticated
    if authenticated and device_id:
        device_info_response = http_session_blebox.get("https://portal.blebox.eu/api/events/device/"+device_id+"/?limit=1")
        show_debug(device_info_response)
        if device_info_response.status_code == 200:
            print("[INF] Device information")
            dev_id = { 'device_id': device_id}
            dev_location = { 'device_location': device_location}
            temperature = { 'temperature': device_info_response.json()['events'][0]['payload']['text']['context'][0] }
        
            dt_obj = datetime.strptime(device_info_response.json()['events'][0]['occurredAt'],"%Y-%m-%dT%H:%M:%S.%f")
            measurements_ts = dt_obj.strftime("%s")
            date = {'date': measurements_ts}
            return { **dev_id, **dev_location, **temperature, **date }
        else:
            print("[ERROR] Device information error")
            authenticated = False
            return False
    else:
        print("[ERROR] Not authenticated")
        authenticated = False
        return False

def send_data_to_influx(http_session_influx,sensor_id,location,temperature,time):
    global authenticated
    if authenticated:
        insert_string = "temperature,sensor_id={},location={} value={} {}".format(sensor_id.replace(' ',"_"),location.replace(' ',"_"),temperature,time)
        influx_response = http_session_influx.post("http://192.168.100.195:8086/write?db=esbs_blebox", data=insert_string)
        show_debug(influx_response)
        if influx_response.status_code == 200 or influx_response.status_code == 204:
            return True

        if influx_response.status_code > 299:
            print("[ERROR] Exit code {}".format(influx_response.status_code))
            authenticated = False
            return False
    else:
        print("[ERROR] Not authenticated")
        authenticated = False
        return False
        

# Main program
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--login", help="Your Blebox login")
    parser.add_argument("--password", help="Your Blebox password")
    parser.add_argument("--check-interval", help="How frequent check temperatures")

    args = parser.parse_args()

    # enter main page and log in
    print("--------------------------------------------------")
    print("Log in to the systems...")
    authenticate(args.login, args.password)

    while True:
        all_devices_dictionary = list_devices(http_session_blebox)
        if all_devices_dictionary:
            for dev in all_devices_dictionary:
                sensor_data = get_sensor_data2(http_session_blebox,dev['id'],dev['name'])
        #        send_data_to_influx(http_session_influx,sensor_data['device_id'],sensor_data['device_location'],sensor_data['temperature'],sensor_data['date'])
        else:
            authenticate(args.login, args.password)
        time.sleep(int(args.check_interval)) 