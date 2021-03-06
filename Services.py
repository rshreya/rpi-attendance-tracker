#!/usr/bin/env python

#################################################################################
# Import libraries
#################################################################################
from time import sleep
from os import environ as ENV
if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
       not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
    import RPi.GPIO as GPIO
from pyfsm.Service import Service
from LEDIndicator import LEDIndicator
from Piezo import Piezo
from slackclient import SlackClient

#################################################################################
# Perform initializations
#################################################################################

#################################################################################
# Class definitions
#################################################################################
# Default services
# @desc A lightweight state machine to drive the LED Indicator by listening for
#       new LED requests from the LEDQueue
# @param LEDQueue A reference to an instance of a queue that will contain new
#        requests for the LED color and the blink number (code)
# @note The LED state does not correspond to the FSM state, LED indicator states
#       are listed in Jobs.py
class LEDIndicatorService(Service):
    def __init__(self, LEDQueue):
        Service.__init__(self)
        # self.concurrency_limit = concurrency_limit
        # thread-safe queue
        self.LEDQueue = LEDQueue
        self.current_color_pin = None
        self.current_blinks = 0 # default to solid
        self.fsm_iterator = 0
        # intialize pins
        if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
            GPIO.setwarnings(False) # ignore channel-open warnings
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(LEDIndicator.RLED_PIN, GPIO.OUT)
            GPIO.setup(LEDIndicator.GLED_PIN, GPIO.OUT)
            GPIO.setup(LEDIndicator.BLED_PIN, GPIO.OUT)

    # lifetime of the event listener
    def run_prod(self):
        current_state = "init"
        led_type = None
        while True:
            # TODO: remove redunancies in the following two blocks
            # reset with new vals if a new LED Indicator state is requested
            if not self.LEDQueue.empty():
                led_type = self.LEDQueue.get(False)
                self.current_color_pin = led_type["color"]
                self.current_blinks = led_type["blinks"]
                current_state = "init"

            # if the LED Indicator has never received a type, block until it does
            if led_type == None:
                if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                        not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                    print("LEDIndicator: Blocking LED Indicator thread until receiving the first type")
                led_type = self.LEDQueue.get(True)
                self.current_color_pin = led_type["color"]
                self.current_blinks = led_type["blinks"]
                current_state = "init"

            # execute next iteration of LED state
            next_state = self.run_state(current_state)
            current_state = next_state

    def run_state(self, current_state):
        # init next state
        next_state = None
        # service function of current state and return next state
        if current_state == "init":
            self.fsm_iterator = 0
            # set all LEDs to HIGH
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                for colorPin in [LEDIndicator.RED, LEDIndicator.GREEN, LEDIndicator.BLUE]:
                    GPIO.output(colorPin, GPIO.HIGH)
            else:
                print("LEDIndicator: Turning all LEDs off")
            # transition to off state
            next_state = "on"
        elif current_state == "waiting":
            # 1s between .2s blinks where blink number is greater than 1
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                print("LEDIndicator: Waiting...")
            sleep(.2)
            next_state = "on"
        elif current_state == "on":
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                GPIO.output(self.current_color_pin, GPIO.LOW)
            if self.current_blinks == 0:
                # always stay ON if blinks == 0
                next_state = "on"
            else:
                next_state = "off"
            sleep(.2)
        elif current_state == "off":
            # inc iterator
            self.fsm_iterator += 1
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                GPIO.output(self.current_color_pin, GPIO.HIGH)
            if self.fsm_iterator < self.current_blinks:
                next_state = "on"
            elif self.current_blinks == 1:
                # always cycle between .2s OFF/ON for blinks == 1
                self.fsm_iterator = 0
                next_state = "on"
            else:
                # perform .2s OFF/ON, then 1s wait for blinks > 1
                self.fsm_iterator = 0
                next_state = "waiting"
            sleep(.2)
        else:
            print("LEDIndicator: ERROR: Invalid state passed as current_state ->" + str(current_state))
            sleep(.2)

        return next_state

    # close all used GPIO ports
    def __del__(self):
        if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
            print("LEDIndicator: Cleaning up GPIO")
            GPIO.cleanup()

class PiezoService(Service):
    def __init__(self, PiezoQueue):
        Service.__init__(self)
        # self.concurrency_limit = concurrency_limit
        # thread-safe queue
        self.PiezoQueue = PiezoQueue
        self.current_beeps = 0 # default to zero beeps
        self.fsm_iterator = 0
        # intialize pins
        if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
            GPIO.setwarnings(False) # ignore channel-open warnings
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(Piezo.PIEZO_PIN, GPIO.OUT)
        print("Initing piezo service")

    # lifetime of the event listener
    def run_prod(self):
        current_state = "init"
        beep_type = None
        while True:
            # TODO: remove redunancies in the following two blocks
            # reset with new vals if a new Piezo buzzer state is requested
            if not self.PiezoQueue.empty():
                beep_type = self.PiezoQueue.get(False) # non-blocking
                self.current_beeps = beep_type["beeps"]
                print("Piezo: checking for new type")
                current_state = "init"

            # if the Piezo has never received a beep type, block until it does
            if beep_type == None:
                print("Piezo: Blocking Piezo thread until receiving the first type")
                beep_type = self.PiezoQueue.get(True) # blocking
                self.current_beeps = beep_type["beeps"]
                current_state = "init"

            # execute next iteration of Piezo state
            next_state = self.run_state(current_state)
            if next_state == None:
                print("Piezo: Done with beep")
                # stopping beeping if FSM returned None (indicating it's done)
                beep_type = None
            else:
                # continue running FSM otherwise
                current_state = next_state

    def run_state(self, current_state):
        # init next state
        next_state = None
        # service function of current state and return next state
        if current_state == "init":
            self.fsm_iterator = 0
            # turn off Piezo
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                GPIO.output(Piezo.PIEZO_PIN, GPIO.LOW)
                print("Piezo: In INIT state")
            else:
                print("Turning off Piezo buzzer")
            # transition to off state
            next_state = "on"

        elif current_state == "on":
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                GPIO.output(Piezo.PIEZO_PIN, GPIO.HIGH)
                print("Piezo: In ON state")
            else:
                print("Piezo: Turning on Piezo with beeps == " + str(self.current_beeps))
            # wait .1 until transitioning to off
            sleep(.8)
            next_state = "off"

        elif current_state == "off":
            # inc iterator
            self.fsm_iterator += 1
            if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                    not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
                print("Piezo: In OFF state")
                GPIO.output(Piezo.PIEZO_PIN, GPIO.LOW)
            else:
                print("Piezo: Turning the Piezo off")

            if self.fsm_iterator < self.current_beeps:
                next_state = "on"
            else:
                # beep'd enough, go to sleep until next beep request
                self.fsm_iterator = 0
                next_state = None
            sleep(.8) # always wait .1 incase beep requests are spammed

        else:
            print("Piezo: ERROR: Invalid state passed as current_state ->" + str(current_state))
            sleep(.8)

        return next_state

    # close all used GPIO ports
    def __del__(self):
        if not 'ATTENDANCE_TRACKER_TEST' in ENV or \
                not int(ENV['ATTENDANCE_TRACKER_TEST']) == 1:
            print("Piezo: Cleaning up GPIO")
            GPIO.cleanup()

class LabStatusService(Service):
    def __init__(self, auth_token, channel_id, membersQueue):
        Service.__init__(self)
        self.auth_token = auth_token
        self.channel_id = channel_id
        self.slack_client = SlackClient(self.auth_token)
        self.members_in_lab = 0
        self.membersQueue = membersQueue
        print("LabStatusService: Finished initializing")

    # lifetime of the event listener
    def run_prod(self):
        while True:
            # block until a new member event can be fetched
            new_member_event = self.membersQueue.get(True)
            # increment or decrement the number of members based on the swipe polarity
            if new_member_event == "INCREMENT":
                # incrementing
                # check if crossing 0->1 threshold
                if self.members_in_lab == 0:
                    # crossing threshold, post lab open
                    self.changeTopic("LAB OPEN")
                    print("LabStatusService: Changing lab status to OPEN")
                self.members_in_lab += 1
            else:
                # decrementing
                # check if crossing 1->0 threshold
                if self.members_in_lab == 1:
                    # crossing threshold, post lab closed
                    self.changeTopic("LAB CLOSED")
                    print("LabStatusService: Changing lab status to CLOSED")
                self.members_in_lab -= 1
        
    def changeTopic(self, message):
        self.slack_client.api_call(
            "channels.setTopic",
            token=self.auth_token,
            channel=self.channel_id,
            topic=message
        )
        # 'xoxp-6044688833-126852609376-152389424672-d7934b0e899443e22b0d23051863c5cf'
        #  'xoxp-6044688833-6367767126-149775464486-509594e99b4ff1bd4bce030034de07ea',


#################################################################################
# House keeping..close interfaces and processes
#################################################################################
