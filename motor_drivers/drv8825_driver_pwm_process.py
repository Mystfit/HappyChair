"""
DRV8825 driver subprocess implementation for isolated PWM control.
Runs in a separate process to avoid GIL-related timing issues.
"""

import os
import signal
import time
import multiprocessing
import lgpio
from rpi_hardware_pwm import HardwarePWM


class DRV8825DriverPWMProcess:
    """
    Subprocess worker that handles actual DRV8825 PWM control.
    Runs in isolation to avoid GIL interference with timing-critical operations.
    """
    
    def __init__(self, command_queue, dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27)):
        self.command_queue = command_queue
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        
        # GPIO and PWM control
        self.gpio_handle = None
        self.hardware_pwm = None
        self.pwm_active = False
        self.pwm_frequency = 0
        self.pwm_duty_cycle = 50
        
        # Speed mapping parameters
        self.min_frequency = 200
        self.max_frequency = 700
        self.current_frequency = 0
        
        # Current state
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"
        
        # Process control
        self.running = True
        
        print(f"DRV8825DriverPWMProcess: Initialized (PID: {os.getpid()})")
    
    def run(self):
        """Main process loop - handles commands from queue"""
        # Set up signal handling for clean shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print("DRV8825DriverPWMProcess: Starting command processing loop")
        
        try:
            while self.running:
                try:
                    # Wait for commands with timeout to allow periodic checks
                    if not self.command_queue.empty():
                        command = self.command_queue.get(timeout=0.1)
                        self._process_command(command)
                    else:
                        time.sleep(0.01)  # Small sleep to prevent busy waiting
                        
                except multiprocessing.TimeoutError:
                    # Timeout is normal, continue loop
                    continue
                except Exception as e:
                    print(f"DRV8825DriverPWMProcess: Error processing command: {e}")
                    continue
                    
        except KeyboardInterrupt:
            print("DRV8825DriverPWMProcess: Received keyboard interrupt")
        finally:
            self._cleanup()
            print("DRV8825DriverPWMProcess: Process terminated")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"DRV8825DriverPWMProcess: Received signal {signum}")
        self.running = False
    
    def _process_command(self, command):
        """Process a command from the queue"""
        if not isinstance(command, dict):
            print(f"DRV8825DriverPWMProcess: Invalid command format: {command}")
            return
        
        action = command.get('action')
        params = command.get('params', {})
        
        try:
            if action == 'start':
                self._handle_start()
            elif action == 'stop':
                self._handle_stop()
            elif action == 'set_speed':
                direction = params.get('direction', 'stopped')
                speed = params.get('speed', 0.0)
                self._handle_set_speed(direction, speed)
            elif action == 'cleanup':
                self.running = False
            else:
                print(f"DRV8825DriverPWMProcess: Unknown action: {action}")
                
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error handling {action}: {e}")
    
    def _handle_start(self):
        """Initialize GPIO and PWM hardware"""
        if self.enabled:
            print("DRV8825DriverPWMProcess: Already started")
            return
        
        try:
            # Initialize GPIO handle
            self.gpio_handle = lgpio.gpiochip_open(0)
            
            # Initialize hardware PWM
            if self.step_pin == 18:
                pwm_channel = 2
            elif self.step_pin == 19:
                pwm_channel = 1
            else:
                raise ValueError(f"Step pin {self.step_pin} is not a hardware PWM pin. Use GPIO 18 or 19.")
            
            self.hardware_pwm = HardwarePWM(pwm_channel=pwm_channel, hz=self.min_frequency, chip=0)
            
            # Setup GPIO pins
            lgpio.gpio_claim_output(self.gpio_handle, self.dir_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.enable_pin)
            
            # Setup mode pins for fullstep mode
            for pin in self.mode_pins:
                lgpio.gpio_claim_output(self.gpio_handle, pin)
                lgpio.gpio_write(self.gpio_handle, pin, 0)  # Fullstep mode (0,0,0)
            
            # Initialize pins to safe state
            lgpio.gpio_write(self.gpio_handle, self.dir_pin, 0)
            lgpio.gpio_write(self.gpio_handle, self.enable_pin, 0)  # Disabled initially
            
            self.enabled = True
            print("DRV8825DriverPWMProcess: Hardware initialized successfully")
            
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error initializing hardware: {e}")
            self._cleanup_gpio()
    
    def _handle_stop(self):
        """Stop motor and disable"""
        if not self.enabled:
            return
        
        print("DRV8825DriverPWMProcess: Stopping motor")
        
        # Stop PWM
        self._stop_pwm()
        
        # Update state
        self.current_direction = "stopped"
        self.current_speed = 0.0
        self.current_frequency = 0
        
        # Disable motor
        try:
            if self.gpio_handle:
                lgpio.gpio_write(self.gpio_handle, self.enable_pin, 0)
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error disabling motor: {e}")
    
    def _handle_set_speed(self, direction, speed):
        """Set motor direction and speed"""
        if not self.enabled:
            print("DRV8825DriverPWMProcess: Cannot set speed - not initialized")
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        try:
            if direction == "stopped" or speed <= 0:
                self._stop_pwm()
                self.current_frequency = 0
                self.current_speed = speed
                self.current_direction = direction
            else:
                # Calculate PWM frequency from speed
                frequency = self.min_frequency + (speed * (self.max_frequency - self.min_frequency))
                self.current_frequency = frequency
                
                # Set direction
                dir_value = 0 if direction == "forward" else 1
                lgpio.gpio_write(self.gpio_handle, self.dir_pin, dir_value)
                lgpio.gpio_write(self.gpio_handle, self.enable_pin, 1)  # Enable motor
                
                # Start/update PWM
                self._start_pwm(frequency)
                
                # Update state
                self.current_speed = speed
                self.current_direction = direction
            
            # Calculate steps per second for debugging
            steps_per_sec = self.current_frequency if self.current_frequency > 0 else 0
            print(f"DRV8825DriverPWMProcess: Set direction={direction}, speed={speed:.3f}, frequency={self.current_frequency:.1f}Hz (~{steps_per_sec:.1f} steps/sec)")
            
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error setting speed: {e}")
    
    def _start_pwm(self, frequency):
        """Start or update hardware PWM"""
        try:
            if not self.hardware_pwm:
                print("DRV8825DriverPWMProcess: Hardware PWM not initialized")
                return
            
            if self.pwm_active:
                # Update existing PWM frequency
                self.hardware_pwm.change_frequency(frequency)
            else:
                # Start new hardware PWM
                self.hardware_pwm.start(self.pwm_duty_cycle)
                self.hardware_pwm.change_frequency(frequency)
                self.pwm_active = True
                print(f"DRV8825DriverPWMProcess: Hardware PWM started at {frequency:.1f}Hz")
            
            self.pwm_frequency = frequency
            
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error starting PWM: {e}")
    
    def _stop_pwm(self):
        """Stop hardware PWM"""
        try:
            if self.pwm_active and self.hardware_pwm:
                self.hardware_pwm.stop()
                self.pwm_active = False
                self.pwm_frequency = 0
                print("DRV8825DriverPWMProcess: Hardware PWM stopped")
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error stopping PWM: {e}")
    
    def _cleanup_gpio(self):
        """Cleanup GPIO resources"""
        try:
            # Stop PWM first
            self._stop_pwm()
            
            # Cleanup hardware PWM
            if self.hardware_pwm:
                try:
                    if self.pwm_active:
                        self.hardware_pwm.stop()
                    self.hardware_pwm = None
                except Exception as e:
                    print(f"DRV8825DriverPWMProcess: Error cleaning up PWM: {e}")
            
            # Free GPIO pins
            if self.gpio_handle:
                try:
                    lgpio.gpio_free(self.gpio_handle, self.dir_pin)
                    lgpio.gpio_free(self.gpio_handle, self.enable_pin)
                    
                    for pin in self.mode_pins:
                        lgpio.gpio_free(self.gpio_handle, pin)
                except Exception as e:
                    print(f"DRV8825DriverPWMProcess: Error freeing GPIO pins: {e}")
                
                # Close GPIO handle
                try:
                    lgpio.gpiochip_close(self.gpio_handle)
                    self.gpio_handle = None
                except Exception as e:
                    print(f"DRV8825DriverPWMProcess: Error closing GPIO handle: {e}")
                    
        except Exception as e:
            print(f"DRV8825DriverPWMProcess: Error during cleanup: {e}")
    
    def _cleanup(self):
        """Final cleanup before process termination"""
        print("DRV8825DriverPWMProcess: Performing final cleanup")
        self._cleanup_gpio()
        self.enabled = False


def run_drv8825_process(command_queue, dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27)):
    """
    Entry point for the DRV8825 subprocess.
    """
    try:
        process = DRV8825DriverPWMProcess(command_queue, dir_pin, step_pin, enable_pin, mode_pins)
        process.run()
    except Exception as e:
        print(f"DRV8825DriverPWMProcess: Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Test standalone execution
    import multiprocessing
    
    queue = multiprocessing.Queue()
    
    try:
        run_drv8825_process(queue)
    except KeyboardInterrupt:
        print("Process interrupted")
