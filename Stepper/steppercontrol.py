import RPi.GPIO as GPIO
import time
from .DRV8825 import DRV8825

class StepperControl(object):
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.motor = DRV8825(dir_pin=13, step_pin=19, enable_pin=12, mode_pins=(16, 17, 20))
        self.motor.SetMicroStep('softward','fullstep')
        
    def rotate(self, direction, duration, speed):
        if not self.enabled:
            return
        
        dir = "forward" if direction > 0 else "backward"
        self.motor.TurnStep(Dir=dir, steps=duration, stepdelay = speed)
        
    def stop(self):
        if  self.enabled:
            self.motor.Stop()
