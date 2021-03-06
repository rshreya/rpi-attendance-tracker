#!/usr/bin/env python

#################################################################################
# Import libraries
#################################################################################
# Universal imports
import time
import math
import Events
from os import environ as ENV
from pyfsm.EventListener import EventListener

# imports for when not in test mode
if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
   not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
    # Prod mode imports
    import evdev # lib for keyboard input event detection
    import RPi.GPIO as GPIO

#################################################################################
# Perform initializations
#################################################################################
KEY_STATE_DOWN = 1
KEY_STATE_UP = 0
VALID_KEY_HASH = {
    "KEY_0": 0,
    "KEY_1": 1,
    "KEY_2": 2,
    "KEY_3": 3,
    "KEY_4": 4,
    "KEY_5": 5,
    "KEY_6": 6,
    "KEY_7": 7,
    "KEY_8": 8,
    "KEY_9": 9
}

#################################################################################
# Class definitions
#################################################################################
class CardReadEventListener(EventListener):
    def __init__(self, device_name):
        EventListener.__init__(self)
        self.device_name = device_name

    def run_test(self):
        while True:
            time.sleep(10)
            self.eventQueue.put(Events.CardReadEvent({"id": 1234567}))

    def run_prod(self):
        while True:
            # scan for devices
            devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
            # find card reader device
            if (len(devices) > 0):
                print("Input event devices available ("
                        + str(len(devices)) + "). Devices are: ")
                # init card reader discovery bool
                discovered_card_reader = False
                # display input devices
                for i, device in enumerate(devices):
                    print("    " + str(i) + ") (" + device.fn + ", "
                            + device.name + ", " + device.phys + ")")
                    # search for card reader by its name, "HID c216:0180"
                    if str(device.name) == "HID c216:0180":
                        print("Discovered card reader..listening for events \
                                until test harness is closed.")
                        # rename device for readability
                        card_reader = device
                        # indefinitely listen for events
                        byte_count = 0
                        student_id = 0
                        for event in card_reader.read_loop():
                            if event.type == evdev.ecodes.EV_KEY:
                                event_key_state = evdev.util.categorize(event).keystate
                                keycode_str = evdev.util.categorize(event).keycode
                                if byte_count < 7:
                                    if event_key_state == KEY_STATE_DOWN and keycode_str in VALID_KEY_HASH:
                                        keycode_int = VALID_KEY_HASH[keycode_str]
                                        exponent = int(math.pow(10,(6-byte_count)))
                                        student_id += int(keycode_int) * exponent
                                        byte_count += 1
                                        # end of student id
                                        if byte_count == 7:
                                            self.eventQueue.put(Events.CardReadEvent({"id": student_id}))
                                            student_id = 0
                                if event_key_state == KEY_STATE_UP and keycode_str == "KEY_ENTER":
                                    # last byte in card, so reset byte count
                                    byte_count = 0

                # error out if unable to find card reader
                if not discovered_card_reader:
                    print("ERROR: Unable to find the card reader")
                    time.sleep(1) # delay until next attempt to connect

# TODO: make this use interrupts
# TODO: implement proper debouncing
class ShutdownEventListener(EventListener):
    def __init__(self):
        EventListener.__init__(self)
        self.shutdown_pin = 4
        # intialize pins
        if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
            GPIO.setwarnings(False) # ignore channel-open warnings
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.shutdown_pin, GPIO.IN)

    def run_test(self):
        while True:
            time.sleep(30)
            self.eventQueue.put(Events.ShutdownEvent())

    def run_prod(self):
        while True:
            # poll for actuation of button every 10th of a second
            # note that shutdown button is active-low
            if not GPIO.input(self.shutdown_pin):
                # shutdown pressed, debounce once for simplicity
                time.sleep(.1)
                if not GPIO.input(self.shutdown_pin):
                    # shutdown pressed for at least .1s, post the event
                    # note that this is very poor debouncing
                    self.eventQueue.put(Events.ShutdownEvent())
            time.sleep(.1)

#################################################################################
# House keeping..close interfaces and processes
#################################################################################
