import RPi.GPIO as GPIO
import time
from .DRV8825 import DRV8825

class StepperControl(object):
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.motor = DRV8825(dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27))
        self.motor.SetMicroStep('softward','fullstep')
        
    def rotate(self, direction, duration, speed):
        if not self.enabled:
            return
        
        dir = "forward" if direction > 0 else "backward"
        self.motor.TurnStep(Dir=dir, steps=duration, stepdelay = speed)
        
    def stop(self):
        if  self.enabled:
            self.motor.Stop()
            
if __name__ == "__main_":
        stepper = StepperControl()
        stepper.rotate(1, 240, 0.003)
        time.sleep(3)
        stepper.stop()
