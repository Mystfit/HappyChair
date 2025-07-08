"""
DRV8825 driver implementation with hardware PWM for stepper motor control.
Provides stepper motor control with consistent timing using hardware PWM.
"""

import threading
import time
import lgpio
from rpi_hardware_pwm import HardwarePWM
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
        
        # Hardware PWM control
        self.hardware_pwm = None  # HardwarePWM instance
        self.pwm_frequency = 0  # Current PWM frequency (0 = stopped)
        self.pwm_duty_cycle = 50  # 50% duty cycle for square wave
        self.pwm_active = False
        
        # Speed mapping parameters - converted to frequency ranges
        # Start with much slower frequencies to ensure motor can step properly
        # Based on original driver default of 0.005s step_delay = 100Hz total frequency
        self.min_frequency = 50   # Very slow: 10Hz (100ms period)
        self.max_frequency = 500  # Moderate: 100Hz (10ms period, matches original default)
        self.current_frequency = 0
        
        # Limit speed changes to avoid abrupt stepper movements
        self.speed_change_threshold = 0.1  # Minimum speed change to trigger update
        self.limit_speed_updates = True
        
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
        Initialize and start the DRV8825 driver with hardware PWM control.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize hardware PWM for step pin FIRST (before claiming any GPIO pins)
            if self.step_pin == 18:
                pwm_channel = 2
            elif self.step_pin == 19:
                pwm_channel = 1
            else:
                raise ValueError(f"Step pin {self.step_pin} is not a hardware PWM pin. Use GPIO 18 or 19.")
            
            self.hardware_pwm = HardwarePWM(pwm_channel=pwm_channel, hz=self.min_frequency, chip=0)
            print(f"DRV8825DriverPWM: Hardware PWM initialized on GPIO {self.step_pin} (channel {pwm_channel})")
            
            # Setup GPIO pins (step pin is NOT claimed by lgpio - it's controlled by hardware PWM)
            lgpio.gpio_claim_output(self.gpio_handle, self.dir_pin)
            lgpio.gpio_claim_output(self.gpio_handle, self.enable_pin)
            
            # Setup mode pins for fullstep mode
            for pin in self.mode_pins:
                lgpio.gpio_claim_output(self.gpio_handle, pin)
                lgpio.gpio_write(self.gpio_handle, pin, 0)  # Fullstep mode (0,0,0)
            
            # Initialize pins to safe state
            lgpio.gpio_write(self.gpio_handle, self.dir_pin, 0)
            lgpio.gpio_write(self.gpio_handle, self.enable_pin, 0)  # Disabled initially
            
            print("DRV8825DriverPWM: GPIO pins and hardware PWM initialized")
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
        
        update_speed = not self.limit_speed_updates
        if update_speed and speed >= self.target_speed + self.speed_change_threshold or speed <= self.target_speed - self.speed_change_threshold:
            update_speed = True
                
        if update_speed:
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
        """Start or update hardware PWM on the step pin"""
        try:
            if not self.hardware_pwm:
                print("DRV8825DriverPWM: Hardware PWM not initialized")
                return
                
            if self.pwm_active:
                # Update existing PWM frequency
                self.hardware_pwm.change_frequency(frequency)
            else:
                # Start new hardware PWM
                self.hardware_pwm.start(self.pwm_duty_cycle)
                self.hardware_pwm.change_frequency(frequency)
                self.pwm_active = True
                
            self.pwm_frequency = frequency
            print(f"DRV8825DriverPWM: Hardware PWM started at {frequency:.1f}Hz, {self.pwm_duty_cycle}% duty cycle")
            
        except Exception as e:
            print(f"DRV8825DriverPWM: Error starting hardware PWM: {e}")
    
    def _stop_pwm(self):
        """Stop hardware PWM on the step pin"""
        try:
            if self.pwm_active and self.hardware_pwm:
                self.hardware_pwm.stop()
                self.pwm_active = False
                self.pwm_frequency = 0
                print("DRV8825DriverPWM: Hardware PWM stopped")
                
        except Exception as e:
            print(f"DRV8825DriverPWM: Error stopping hardware PWM: {e}")
    
    def _cleanup_gpio(self):
        """Cleanup GPIO resources and hardware PWM"""
        try:
            # Stop hardware PWM first
            self._stop_pwm()
            
            # Cleanup hardware PWM instance
            if self.hardware_pwm:
                try:
                    # Ensure PWM is stopped before cleanup
                    if self.pwm_active:
                        self.hardware_pwm.stop()
                    self.hardware_pwm = None
                    print("DRV8825DriverPWM: Hardware PWM cleaned up")
                except Exception as e:
                    print(f"DRV8825DriverPWM: Error cleaning up hardware PWM: {e}")
            
            if self.gpio_handle:
                # Free GPIO pins (step pin is handled by hardware PWM, not lgpio)
                try:
                    lgpio.gpio_free(self.gpio_handle, self.dir_pin)
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
