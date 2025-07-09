"""
DRV8825 driver proxy implementation that forwards commands to a subprocess.
Provides the same API as DRV8825DriverPWM but runs PWM control in isolation.
"""

import threading
import time
import multiprocessing
import atexit
from .base_driver import MotorDriver
from .drv8825_driver_pwm_process import run_drv8825_process


class DRV8825DriverPWMProxy(MotorDriver):
    """
    Proxy driver that forwards commands to a DRV8825DriverPWMProcess subprocess.
    Maintains the same interface as DRV8825DriverPWM while isolating PWM operations.
    """
    
    def __init__(self, dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27), gpio_handle=None):
        super().__init__()
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        # Note: gpio_handle is ignored since subprocess manages its own GPIO
        
        # Subprocess management
        self.subprocess = None
        self.command_queue = None
        self.subprocess_lock = threading.Lock()
        
        # Local state cache (for API responses)
        self.cached_speed = 0.0
        self.cached_direction = "stopped"
        self.cached_frequency = 0
        self.cached_pwm_active = False
        
        # Speed mapping parameters (same as original)
        self.min_frequency = 200
        self.max_frequency = 700
        
        # State tracking
        self.state_lock = threading.Lock()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
        
        print("DRV8825DriverPWMProxy: Initialized")
    
    def start(self) -> bool:
        """
        Initialize and start the DRV8825 driver subprocess.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self.subprocess_lock:
            if self.subprocess and self.subprocess.is_alive():
                print("DRV8825DriverPWMProxy: Subprocess already running")
                return True
            
            try:
                # Create command queue
                self.command_queue = multiprocessing.Queue()
                
                # Start subprocess
                self.subprocess = multiprocessing.Process(
                    target=run_drv8825_process,
                    args=(self.command_queue, self.dir_pin, self.step_pin, self.enable_pin, self.mode_pins),
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
                print(f"DRV8825DriverPWMProxy: Subprocess started (PID: {self.subprocess.pid})")
                return True
                
            except Exception as e:
                print(f"DRV8825DriverPWMProxy: Error starting subprocess: {e}")
                self._cleanup_subprocess()
                return False
    
    def stop(self):
        """
        Stop the motor and cleanup subprocess.
        """
        print("DRV8825DriverPWMProxy: Stopping motor and subprocess...")
        
        # Stop any active transitions
        self.stop_transitions()
        
        # Send stop command to subprocess
        self._send_command('stop')
        
        # Update local state
        with self.state_lock:
            self.current_speed = 0.0
            self.current_direction = "stopped"
            self.cached_speed = 0.0
            self.cached_direction = "stopped"
            self.cached_frequency = 0
            self.cached_pwm_active = False
        
        # Cleanup subprocess
        self._cleanup_subprocess()
        
        self.enabled = False
        print("DRV8825DriverPWMProxy: Motor stopped and subprocess terminated")
    
    def _set_speed_immediate(self, direction: str, speed: float):
        """
        Set motor direction and speed immediately by sending command to subprocess.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        if not self.enabled:
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
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
                self.cached_pwm_active = False
            else:
                self.cached_frequency = self.min_frequency + (speed * (self.max_frequency - self.min_frequency))
                self.cached_pwm_active = True
        
        # Calculate steps per second for debugging
        steps_per_sec = self.cached_frequency if self.cached_frequency > 0 else 0
        print(f"DRV8825DriverPWMProxy: Sent command - direction={direction}, speed={speed:.3f}, frequency={self.cached_frequency:.1f}Hz (~{steps_per_sec:.1f} steps/sec)")
    
    def _send_command(self, action, params=None):
        """Send a command to the subprocess"""
        if not self.command_queue:
            print("DRV8825DriverPWMProxy: No command queue available")
            return
        
        command = {
            'action': action,
            'params': params or {}
        }
        
        try:
            self.command_queue.put(command, timeout=1.0)
        except Exception as e:
            print(f"DRV8825DriverPWMProxy: Error sending command {action}: {e}")
    
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
                        print("DRV8825DriverPWMProxy: Terminating subprocess...")
                        self.subprocess.terminate()
                        
                        # Wait for graceful termination
                        self.subprocess.join(timeout=2.0)
                        
                        # Force kill if still alive
                        if self.subprocess.is_alive():
                            print("DRV8825DriverPWMProxy: Force killing subprocess...")
                            self.subprocess.kill()
                            self.subprocess.join(timeout=1.0)
                    
                    print("DRV8825DriverPWMProxy: Subprocess terminated")
                    
                except Exception as e:
                    print(f"DRV8825DriverPWMProxy: Error during subprocess cleanup: {e}")
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
            print("DRV8825DriverPWMProxy: Cleanup on exit")
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
        Get driver statistics including cached PWM information.
        
        Returns:
            dict: Driver statistics
        """
        with self.state_lock:
            stats = super().get_stats()
            stats.update({
                'pwm_frequency': self.cached_frequency,
                'pwm_active': self.cached_pwm_active,
                'target_frequency': self.cached_frequency,
                'frequency_range': f"{self.min_frequency}-{self.max_frequency}Hz",
                'subprocess_alive': self.subprocess.is_alive() if self.subprocess else False,
                'subprocess_pid': self.subprocess.pid if self.subprocess and self.subprocess.is_alive() else None
            })
            return stats
    
    def __del__(self):
        """
        Destructor to ensure cleanup.
        """
        if hasattr(self, 'enabled') and self.enabled:
            self.stop()
