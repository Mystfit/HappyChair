import lgpio
import time

MotorDir = [
    'forward',
    'backward',
]

ControlMode = [
    'hardward',
    'softward',
]

class DRV8825():
    def __init__(self, dir_pin, step_pin, enable_pin, mode_pins, gpio_handle=None):
        self.dir_pin = dir_pin
        self.step_pin = step_pin        
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        
        # GPIO handle management
        self.gpio_handle = gpio_handle
        self.owns_handle = False
        
        # Initialize GPIO
        if self.gpio_handle is None:
            # Create our own handle if none provided
            self.gpio_handle = lgpio.gpiochip_open(0)
            self.owns_handle = True
        
        # Setup pins as outputs
        try:
            lgpio.gpio_claim_output(self.gpio_handle, self.dir_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.step_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.enable_pin)
            
            # Setup mode pins
            for pin in self.mode_pins:
                lgpio.gpio_claim_output(self.gpio_handle, pin)
                
        except Exception as e:
            print(f"DRV8825: Error setting up GPIO pins: {e}")
            if self.owns_handle:
                lgpio.gpiochip_close(self.gpio_handle)
            raise
        
    def digital_write(self, pin, value):
        """Write digital value to pin using lgpio"""
        try:
            if isinstance(pin, (list, tuple)):
                # Handle multiple pins (for mode pins)
                for i, p in enumerate(pin):
                    if i < len(value):
                        lgpio.gpio_write(self.gpio_handle, p, int(value[i]))
            else:
                # Single pin
                lgpio.gpio_write(self.gpio_handle, pin, int(value))
        except Exception as e:
            print(f"DRV8825: Error writing to pin {pin}: {e}")
        
    def Stop(self):
        self.digital_write(self.enable_pin, 0)
    
    def SetMicroStep(self, mode, stepformat):
        """
        (1) mode
            'hardward' :    Use the switch on the module to control the microstep
            'software' :    Use software to control microstep pin levels
                Need to put the All switch to 0
        (2) stepformat
            ('fullstep', 'halfstep', '1/4step', '1/8step', '1/16step', '1/32step')
        """
        microstep = {'fullstep': (0, 0, 0),
                     'halfstep': (1, 0, 0),
                     '1/4step': (0, 1, 0),
                     '1/8step': (1, 1, 0),
                     '1/16step': (0, 0, 1),
                     '1/32step': (1, 0, 1)}

        print("Control mode:",mode)
        if (mode == ControlMode[1]):
            print("set pins")
            self.digital_write(self.mode_pins, microstep[stepformat])
        
    def TurnStep(self, Dir, steps, stepdelay=0.005):
        if (Dir == MotorDir[0]):
            # print("forward")
            self.digital_write(self.enable_pin, 1)
            self.digital_write(self.dir_pin, 0)
        elif (Dir == MotorDir[1]):
            # print("backward")
            self.digital_write(self.enable_pin, 1)
            self.digital_write(self.dir_pin, 1)
        else:
            print("the dir must be : 'forward' or 'backward'")
            self.digital_write(self.enable_pin, 0)
            return

        if (steps == 0):
            return
            
        # print("turn step:",steps)
        for i in range(steps):
            self.digital_write(self.step_pin, True)
            time.sleep(stepdelay)
            self.digital_write(self.step_pin, False)
            time.sleep(stepdelay)
            self.start_time = time.time()
    def cleanup(self):
        """Cleanup GPIO resources"""
        try:
            if self.gpio_handle is not None:
                # Free the pins we claimed
                lgpio.gpio_free(self.gpio_handle, self.dir_pin)
                lgpio.gpio_free(self.gpio_handle, self.step_pin)
                lgpio.gpio_free(self.gpio_handle, self.enable_pin)
                
                for pin in self.mode_pins:
                    lgpio.gpio_free(self.gpio_handle, pin)
                
                # Close handle only if we own it
                if self.owns_handle:
                    lgpio.gpiochip_close(self.gpio_handle)
                    self.gpio_handle = None
                    
        except Exception as e:
            print(f"DRV8825: Error during cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
