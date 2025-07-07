"""
DRV8825 driver implementation with hardware PWM for stepper motor control.
Provides stepper motor control with consistent timing using hardware PWM.
"""

import threading
import time
import lgpio
from .base_driver import MotorDriver


class DRV8825DriverPWM(MotorDriver):
    """
    Motor driver implementation for DRV8825 stepper motor controller using hardware PWM.
    Provides stepper motor control with hardware-timed precision, eliminating GIL-related timing issues.
    """
    
    def __init__(self, dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27), gpio_handle=None):
        super().__init__()
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        self.gpio_handle = gpio_handle
        self.owns_handle = False
        
        # PWM control
        self.pwm_frequency = 0  # Current PWM frequency (0 = stopped)
        self.pwm_duty_cycle = 50  # 50% duty cycle for square wave
        self.pwm_active = False
        
        # Speed mapping parameters - converted to frequency ranges
        self.min_frequency = 50   # Slowest stepping (50 Hz = 20ms period = 0.01s per half-step)
        self.max_frequency = 500  # Fastest stepping (500 Hz = 2ms period = 0.001s per half-step)
        self.current_frequency = 0
        
        # Target state for PWM control
        self.target_direction = "stopped"
        self.target_speed = 0.0
        
        # Threading for state management
        self.control_lock = threading.Lock()
        
        # Initialize GPIO handle if not provided
        if self.gpio_handle is None:
            try:
                self.gpio_handle = lgpio.gpiochip_open(0)
                self.owns_handle = True
            except Exception as e:
                print(f"DRV8825DriverPWM: Error opening GPIO chip: {e}")
                raise
    
    def start(self) -> bool:
        """
        Initialize and start the DRV8825 driver with PWM control.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Setup GPIO pins
            lgpio.gpio_claim_output(self.gpio_handle, self.dir_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.step_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.enable_pin)
            
            # Setup mode pins for fullstep mode
            for pin in self.mode_pins:
                lgpio.gpio_claim_output(self.gpio_handle, pin)
                lgpio.gpio_write(self.gpio_handle, pin, 0)  # Fullstep mode (0,0,0)
            
            # Initialize pins to safe state
            lgpio.gpio_write(self.gpio_handle, self.dir_pin, 0)
            lgpio.gpio_write(self.gpio_handle, self.step_pin, 0)
            lgpio.gpio_write(self.gpio_handle, self.enable_pin, 0)  # Disabled initially
            
            print("DRV8825DriverPWM: GPIO pins initialized")
            self.enabled = True
            return True
            
        except Exception as e:
            print(f"DRV8825DriverPWM: Error initializing stepper motor: {e}")
            self._cleanup_gpio()
            return False
    
    def stop(self):
        """
        Stop the motor and cleanup resources.
        """
        print("DRV8825DriverPWM: Stopping motor...")
        
        # Stop PWM and disable motor
        self._stop_pwm()
        
        with self.control_lock:
            self.target_direction = "stopped"
            self.target_speed = 0.0
            self.current_frequency = 0
        
        # Disable motor
        try:
            if self.gpio_handle:
                lgpio.gpio_write(self.gpio_handle, self.enable_pin, 0)
        except Exception as e:
            print(f"DRV8825DriverPWM: Error disabling motor: {e}")
        
        # Cleanup GPIO
        self._cleanup_gpio()
        
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"
        print("DRV8825DriverPWM: Motor stopped")
    
    def set_speed(self, direction: str, speed: float):
        """
        Set motor direction and speed using hardware PWM.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        if not self.enabled:
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        if speed >= self.target_speed + 0.1 or speed <= self.target_speed - 0.1:
            print(f"DRV8825DriverPWM: Speed change detected: {speed:.3f} (target: {self.target_speed:.3f})")
        
            with self.control_lock:
                self.target_direction = direction
                self.target_speed = speed
                
                if direction == "stopped" or speed <= 0:
                    self._stop_pwm()
                    self.current_frequency = 0
                else:
                    # Calculate PWM frequency from speed
                    frequency = self.min_frequency + (speed * (self.max_frequency - self.min_frequency))
                    self.current_frequency = frequency
                    
                    # Set direction
                    dir_value = 0 if direction == "forward" else 1
                    try:
                        lgpio.gpio_write(self.gpio_handle, self.dir_pin, dir_value)
                        lgpio.gpio_write(self.gpio_handle, self.enable_pin, 1)  # Enable motor
                    except Exception as e:
                        print(f"DRV8825DriverPWM: Error setting direction: {e}")
                        return
                    
                    # Start/update PWM
                    self._start_pwm(frequency)
            
            # Update current state
            self.current_speed = speed
            self.current_direction = direction
            
            # Calculate steps per second for debugging
            steps_per_sec = frequency if frequency > 0 else 0
            print(f"DRV8825DriverPWM: Set direction={direction}, speed={speed:.3f}, frequency={frequency:.1f}Hz (~{steps_per_sec:.1f} steps/sec)")
    
    def _start_pwm(self, frequency: float):
        """Start or update PWM on the step pin"""
        try:
            if self.pwm_active:
                # Update existing PWM frequency
                lgpio.tx_pwm(self.gpio_handle, self.step_pin, frequency, self.pwm_duty_cycle)
            else:
                # Start new PWM
                lgpio.tx_pwm(self.gpio_handle, self.step_pin, frequency, self.pwm_duty_cycle)
                self.pwm_active = True
                
            self.pwm_frequency = frequency
            
        except Exception as e:
            print(f"DRV8825DriverPWM: Error starting PWM: {e}")
    
    def _stop_pwm(self):
        """Stop PWM on the step pin"""
        try:
            if self.pwm_active:
                lgpio.tx_pwm(self.gpio_handle, self.step_pin, 0, 0)  # Stop PWM
                lgpio.gpio_write(self.gpio_handle, self.step_pin, 0)  # Ensure pin is LOW
                self.pwm_active = False
                self.pwm_frequency = 0
                
        except Exception as e:
            print(f"DRV8825DriverPWM: Error stopping PWM: {e}")
    
    def _cleanup_gpio(self):
        """Cleanup GPIO resources"""
        try:
            if self.gpio_handle:
                # Stop PWM first
                self._stop_pwm()
                
                # Free GPIO pins
                try:
                    lgpio.gpio_free(self.gpio_handle, self.dir_pin)
                    lgpio.gpio_free(self.gpio_handle, self.step_pin)
                    lgpio.gpio_free(self.gpio_handle, self.enable_pin)
                    
                    for pin in self.mode_pins:
                        lgpio.gpio_free(self.gpio_handle, pin)
                except Exception as e:
                    print(f"DRV8825DriverPWM: Error freeing GPIO pins: {e}")
                
                # Close handle if we own it
                if self.owns_handle:
                    lgpio.gpiochip_close(self.gpio_handle)
                    self.gpio_handle = None
                    
        except Exception as e:
            print(f"DRV8825DriverPWM: Error during GPIO cleanup: {e}")
    
    def is_enabled(self) -> bool:
        """
        Check if the motor driver is enabled and operational.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        return self.enabled and self.gpio_handle is not None
    
    def get_stats(self) -> dict:
        """
        Get driver statistics including PWM information.
        
        Returns:
            dict: Driver statistics
        """
        with self.control_lock:
            stats = super().get_stats()
            stats.update({
                'pwm_frequency': self.pwm_frequency,
                'pwm_active': self.pwm_active,
                'target_frequency': self.current_frequency,
                'frequency_range': f"{self.min_frequency}-{self.max_frequency}Hz"
            })
            return stats
    
    def __del__(self):
        """
        Destructor to ensure cleanup.
        """
        if hasattr(self, 'enabled') and self.enabled:
            self.stop()
