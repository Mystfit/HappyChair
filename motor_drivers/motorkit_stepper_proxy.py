"""
MotorKit stepper driver proxy implementation that forwards commands to a subprocess.
Provides the same API as base MotorDriver but runs stepper control in isolation.
"""

import threading
import time
import multiprocessing
import atexit
from adafruit_motor import stepper
from .base_driver import MotorDriver
from .motorkit_stepper_process import run_motorkit_stepper_process


class MotorKitStepperProxy(MotorDriver):
    """
    Proxy driver that forwards commands to a MotorKitStepperProcess subprocess.
    Maintains the same interface as base MotorDriver while isolating I2C operations.
    """
    
    def __init__(self, stepper_num=1, io_controller=None, 
                 clutch_output_pin=None, forward_limit_pin=None, reverse_limit_pin=None):
        super().__init__()
        self.stepper_num = stepper_num
        self.stepping_style = stepper.SINGLE
        
        # Clutch control parameters
        self.io_controller = io_controller
        self.clutch_output_pin = clutch_output_pin
        self.forward_limit_pin = forward_limit_pin
        self.reverse_limit_pin = reverse_limit_pin
        
        # Clutch state management
        self.clutch_engaged = False
        self.clutch_locked = False  # Manual lock to prevent engagement
        self.forward_limit_active = False  # True when forward limit is reached
        self.reverse_limit_active = False  # True when reverse limit is reached
        self.clutch_lock = threading.Lock()
        
        # Subprocess management
        self.subprocess = None
        self.command_queue = None
        self.subprocess_lock = threading.Lock()
        
        # Local state cache (for API responses)
        self.cached_speed = 0.0
        self.cached_direction = "stopped"
        self.cached_frequency = 0
        self.cached_stepping_active = False
        
        # Speed mapping parameters (same as process)
        self.min_frequency = 50   # Hz
        self.max_frequency = 500  # Hz
        
        # State tracking
        self.state_lock = threading.Lock()
        
        # Initialize clutch system if parameters provided
        if self.io_controller and self.clutch_output_pin is not None:
            self._setup_clutch_system()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
        
        print("MotorKitStepperProxy: Initialized with clutch control")
    
    def start(self) -> bool:
        """
        Initialize and start the MotorKit stepper driver subprocess.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self.subprocess_lock:
            if self.subprocess and self.subprocess.is_alive():
                print("MotorKitStepperProxy: Subprocess already running")
                return True
            
            try:
                # Create command queue
                self.command_queue = multiprocessing.Queue()
                
                # Start subprocess
                self.subprocess = multiprocessing.Process(
                    target=run_motorkit_stepper_process,
                    args=(self.command_queue, self.stepper_num, self.stepping_style),
                    daemon=False  # Don't make it daemon so we can clean up properly
                )
                self.subprocess.start()
                
                # Give subprocess time to initialize
                time.sleep(0.1)
                
                # Send start command
                self._send_command('start')
                
                # Give hardware time to initialize
                time.sleep(0.2)
                
                self.enabled = True
                print(f"MotorKitStepperProxy: Subprocess started (PID: {self.subprocess.pid})")
                return True
                
            except Exception as e:
                print(f"MotorKitStepperProxy: Error starting subprocess: {e}")
                self._cleanup_subprocess()
                return False
    
    def stop(self):
        """
        Stop the stepper motor and cleanup subprocess.
        """
        print("MotorKitStepperProxy: Stopping stepper motor and subprocess...")
        
        # Stop any active transitions
        self.stop_transitions()
        
        # Disengage clutch before stopping
        self._disengage_clutch()
        
        # Send stop command to subprocess
        self._send_command('stop')
        
        # Update local state
        with self.state_lock:
            self.current_speed = 0.0
            self.current_direction = "stopped"
            self.cached_speed = 0.0
            self.cached_direction = "stopped"
            self.cached_frequency = 0
            self.cached_stepping_active = False
        
        # Cleanup subprocess
        self._cleanup_subprocess()
        
        self.enabled = False
        print("MotorKitStepperProxy: Stepper motor stopped and subprocess terminated")
    
    def _set_speed_immediate(self, direction: str, speed: float):
        """
        Set stepper direction and speed immediately by sending command to subprocess.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        if not self.enabled:
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        # Check if direction is blocked by limit switches
        if direction != "stopped" and self._is_direction_blocked(direction):
            print(f"MotorKitStepperProxy: Movement in {direction} direction blocked by limit switch")
            direction = "stopped"
            speed = 0.0
        
        # Handle clutch engagement/disengagement
        if direction == "stopped" or speed <= 0:
            # Motor stopping - disengage clutch
            self._disengage_clutch()
        else:
            # Motor starting - engage clutch
            if not self._engage_clutch():
                print("MotorKitStepperProxy: Failed to engage clutch, stopping motor")
                direction = "stopped"
                speed = 0.0
        
        # Send command to subprocess
        self._send_command('set_speed', {
            'direction': direction,
            'speed': speed
        })
        
        # Update local state cache
        with self.state_lock:
            self.current_speed = speed
            self.current_direction = direction
            self.cached_speed = speed
            self.cached_direction = direction
            
            # Calculate cached frequency for stats
            if direction == "stopped" or speed <= 0:
                self.cached_frequency = 0
                self.cached_stepping_active = False
            else:
                self.cached_frequency = self.min_frequency + (speed * (self.max_frequency - self.min_frequency))
                self.cached_stepping_active = True
        
        print(f"MotorKitStepperProxy: Sent command - direction={direction}, speed={speed:.3f}, frequency={self.cached_frequency:.1f}Hz")
    
    def _send_command(self, action, params=None):
        """Send a command to the subprocess"""
        if not self.command_queue:
            print("MotorKitStepperProxy: No command queue available")
            return
        
        command = {
            'action': action,
            'params': params or {}
        }
        
        try:
            self.command_queue.put(command, timeout=1.0)
        except Exception as e:
            print(f"MotorKitStepperProxy: Error sending command {action}: {e}")
    
    def _cleanup_subprocess(self):
        """Cleanup the subprocess and related resources"""
        with self.subprocess_lock:
            if self.subprocess:
                try:
                    # Send cleanup command
                    if self.command_queue:
                        try:
                            self._send_command('cleanup')
                            time.sleep(0.1)  # Give subprocess time to process cleanup
                        except:
                            pass  # Ignore errors during cleanup
                    
                    # Terminate subprocess if still alive
                    if self.subprocess.is_alive():
                        print("MotorKitStepperProxy: Terminating subprocess...")
                        self.subprocess.terminate()
                        
                        # Wait for graceful termination
                        self.subprocess.join(timeout=2.0)
                        
                        # Force kill if still alive
                        if self.subprocess.is_alive():
                            print("MotorKitStepperProxy: Force killing subprocess...")
                            self.subprocess.kill()
                            self.subprocess.join(timeout=1.0)
                    
                    print("MotorKitStepperProxy: Subprocess terminated")
                    
                except Exception as e:
                    print(f"MotorKitStepperProxy: Error during subprocess cleanup: {e}")
                finally:
                    self.subprocess = None
            
            # Close command queue
            if self.command_queue:
                try:
                    self.command_queue.close()
                    self.command_queue.join_thread()
                except:
                    pass  # Ignore errors during queue cleanup
                finally:
                    self.command_queue = None
    
    def _cleanup_on_exit(self):
        """Cleanup function called on program exit"""
        if self.enabled:
            print("MotorKitStepperProxy: Cleanup on exit")
            self.stop()
    
    def is_enabled(self) -> bool:
        """
        Check if the motor driver is enabled and operational.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        with self.subprocess_lock:
            return (self.enabled and 
                    self.subprocess is not None and 
                    self.subprocess.is_alive())
    
    def get_stats(self) -> dict:
        """
        Get driver statistics including cached stepper information.
        
        Returns:
            dict: Driver statistics
        """
        with self.state_lock:
            stats = super().get_stats()
            stats.update({
                'step_frequency': self.cached_frequency,
                'stepping_active': self.cached_stepping_active,
                'target_frequency': self.cached_frequency,
                'frequency_range': f"{self.min_frequency}-{self.max_frequency}Hz",
                'stepper_num': self.stepper_num,
                'stepping_style': str(self.stepping_style),
                'subprocess_alive': self.subprocess.is_alive() if self.subprocess else False,
                'subprocess_pid': self.subprocess.pid if self.subprocess and self.subprocess.is_alive() else None
            })
            
            # Add clutch status if clutch system is enabled
            if self.io_controller and self.clutch_output_pin is not None:
                clutch_status = self.get_clutch_status()
                stats.update({
                    'clutch_enabled': True,
                    'clutch_engaged': clutch_status['clutch_engaged'],
                    'clutch_locked': clutch_status['clutch_locked'],
                    'forward_limit_active': clutch_status['forward_limit_active'],
                    'reverse_limit_active': clutch_status['reverse_limit_active'],
                    'clutch_output_pin': clutch_status['clutch_output_pin'],
                    'forward_limit_pin': clutch_status['forward_limit_pin'],
                    'reverse_limit_pin': clutch_status['reverse_limit_pin']
                })
            else:
                stats.update({'clutch_enabled': False})
            
            return stats
    
    def _setup_clutch_system(self):
        """Initialize the clutch control system"""
        try:
            # Register clutch output pin
            if self.clutch_output_pin is not None:
                success = self.io_controller.register_pin(
                    self.clutch_output_pin, 
                    f"clutch_stepper_{self.stepper_num}", 
                    "output"
                )
                if not success:
                    print(f"MotorKitStepperProxy: Failed to register clutch output pin {self.clutch_output_pin}")
                    return False
                
                # Ensure clutch starts disengaged
                self._disengage_clutch()
            
            # Register limit switch input pins
            if self.forward_limit_pin is not None:
                success = self.io_controller.register_pin(
                    self.forward_limit_pin,
                    f"forward_limit_stepper_{self.stepper_num}",
                    "input",
                    "pull_up"
                )
                if not success:
                    print(f"MotorKitStepperProxy: Failed to register forward limit pin {self.forward_limit_pin}")
                    return False
            
            if self.reverse_limit_pin is not None:
                success = self.io_controller.register_pin(
                    self.reverse_limit_pin,
                    f"reverse_limit_stepper_{self.stepper_num}",
                    "input", 
                    "pull_up"
                )
                if not success:
                    print(f"MotorKitStepperProxy: Failed to register reverse limit pin {self.reverse_limit_pin}")
                    return False
            
            # Register event callback for limit switch monitoring
            self.io_controller.register_event_callback(self._handle_gpio_event)
            
            print("MotorKitStepperProxy: Clutch system initialized successfully")
            return True
            
        except Exception as e:
            print(f"MotorKitStepperProxy: Error setting up clutch system: {e}")
            return False
    
    def _handle_gpio_event(self, event):
        """Handle GPIO events from IOController"""
        try:
            if event['type'] != 'pin_changed':
                return
            
            pin_data = event['data']
            pin_number = pin_data['pin']
            new_state = pin_data['state']
            previous_state = pin_data['previous_state']
            
            # Check if this is a limit switch pin and if it's a HIGH->LOW transition (reed switch activation)
            if pin_number == self.forward_limit_pin and previous_state == 1 and new_state == 0:
                self._handle_forward_limit_reached()
            elif pin_number == self.reverse_limit_pin and previous_state == 1 and new_state == 0:
                self._handle_reverse_limit_reached()
            elif pin_number == self.forward_limit_pin and previous_state == 0 and new_state == 1:
                self._handle_forward_limit_cleared()
            elif pin_number == self.reverse_limit_pin and previous_state == 0 and new_state == 1:
                self._handle_reverse_limit_cleared()
                
        except Exception as e:
            print(f"MotorKitStepperProxy: Error handling GPIO event: {e}")
    
    def _handle_forward_limit_reached(self):
        """Handle forward rotation limit reached"""
        with self.clutch_lock:
            print("MotorKitStepperProxy: Forward rotation limit reached")
            self.forward_limit_active = True
            
            # Stop motor if currently moving forward
            if self.current_direction == "forward":
                print("MotorKitStepperProxy: Stopping motor due to forward limit")
                self._set_speed_immediate("stopped", 0.0)
                self._disengage_clutch()
    
    def _handle_reverse_limit_reached(self):
        """Handle reverse rotation limit reached"""
        with self.clutch_lock:
            print("MotorKitStepperProxy: Reverse rotation limit reached")
            self.reverse_limit_active = True
            
            # Stop motor if currently moving reverse
            if self.current_direction == "reverse":
                print("MotorKitStepperProxy: Stopping motor due to reverse limit")
                self._set_speed_immediate("stopped", 0.0)
                self._disengage_clutch()
    
    def _handle_forward_limit_cleared(self):
        """Handle forward rotation limit cleared"""
        with self.clutch_lock:
            print("MotorKitStepperProxy: Forward rotation limit cleared")
            self.forward_limit_active = False
    
    def _handle_reverse_limit_cleared(self):
        """Handle reverse rotation limit cleared"""
        with self.clutch_lock:
            print("MotorKitStepperProxy: Reverse rotation limit cleared")
            self.reverse_limit_active = False
    
    def _engage_clutch(self):
        """Engage the clutch by setting output pin HIGH"""
        if self.io_controller and self.clutch_output_pin is not None and not self.clutch_locked:
            try:
                success = self.io_controller.write_pin(self.clutch_output_pin, 1)
                if success:
                    self.clutch_engaged = True
                    print("MotorKitStepperProxy: Clutch engaged")
                else:
                    print("MotorKitStepperProxy: Failed to engage clutch")
                return success
            except Exception as e:
                print(f"MotorKitStepperProxy: Error engaging clutch: {e}")
                return False
        elif self.clutch_locked:
            print("MotorKitStepperProxy: Cannot engage clutch - manually locked")
            return False
        return True
    
    def _disengage_clutch(self):
        """Disengage the clutch by setting output pin LOW"""
        if self.io_controller and self.clutch_output_pin is not None:
            try:
                success = self.io_controller.write_pin(self.clutch_output_pin, 0)
                if success:
                    self.clutch_engaged = False
                    print("MotorKitStepperProxy: Clutch disengaged")
                else:
                    print("MotorKitStepperProxy: Failed to disengage clutch")
                return success
            except Exception as e:
                print(f"MotorKitStepperProxy: Error disengaging clutch: {e}")
                return False
        return True
    
    def _is_direction_blocked(self, direction: str) -> bool:
        """Check if movement in the specified direction is blocked by limit switches"""
        if direction == "forward" and self.forward_limit_active:
            return True
        elif direction == "reverse" and self.reverse_limit_active:
            return True
        return False
    
    def set_clutch_lock(self, locked: bool):
        """Manually lock or unlock the clutch"""
        with self.clutch_lock:
            self.clutch_locked = locked
            if locked:
                # If locking, disengage clutch immediately
                self._disengage_clutch()
                print("MotorKitStepperProxy: Clutch manually locked")
            else:
                print("MotorKitStepperProxy: Clutch manual lock released")
    
    def emergency_disengage(self):
        """Emergency clutch disengagement - stops motor and disengages clutch"""
        print("MotorKitStepperProxy: Emergency clutch disengagement activated")
        
        # Stop motor immediately
        self._set_speed_immediate("stopped", 0.0)
        
        # Disengage clutch
        self._disengage_clutch()
        
        # Lock clutch to prevent re-engagement
        self.set_clutch_lock(True)
    
    def get_clutch_status(self) -> dict:
        """Get current clutch and limit switch status"""
        with self.clutch_lock:
            return {
                'clutch_engaged': self.clutch_engaged,
                'clutch_locked': self.clutch_locked,
                'forward_limit_active': self.forward_limit_active,
                'reverse_limit_active': self.reverse_limit_active,
                'clutch_output_pin': self.clutch_output_pin,
                'forward_limit_pin': self.forward_limit_pin,
                'reverse_limit_pin': self.reverse_limit_pin
            }

    def __del__(self):
        """
        Destructor to ensure cleanup.
        """
        if hasattr(self, 'enabled') and self.enabled:
            self.stop()
