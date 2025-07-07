"""
DRV8825 driver implementation for stepper motor control.
Provides stepper motor control with continuous stepping using threading.
"""

import threading
import time
from .base_driver import MotorDriver
from Servo.DRV8825 import DRV8825


class DRV8825Driver(MotorDriver):
    """
    Motor driver implementation for DRV8825 stepper motor controller.
    Provides stepper motor control with continuous stepping.
    """
    
    def __init__(self, dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27), gpio_handle=None):
        super().__init__()
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        self.gpio_handle = gpio_handle
        self.motor = None
        
        # Threading for continuous stepping
        self.step_thread = None
        self.step_thread_running = False
        self.step_lock = threading.Lock()
        
        # Speed mapping parameters - expanded range for more noticeable speed differences
        self.min_step_delay = 0.001  # Fastest stepping (0.5ms delay)
        self.max_step_delay = 0.01    # Slowest stepping (20ms delay)
        self.current_step_delay = 0.01  # Default delay
        
        # Target state for stepping thread
        self.target_direction = "stopped"
        self.target_speed = 0.0
    
    def start(self) -> bool:
        """
        Initialize and start the DRV8825 driver.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.motor:
                self.motor = DRV8825(
                    dir_pin=self.dir_pin,
                    step_pin=self.step_pin,
                    enable_pin=self.enable_pin,
                    mode_pins=self.mode_pins,
                    gpio_handle=self.gpio_handle
                )
                # Set to fullstep mode
                self.motor.SetMicroStep('softward', 'fullstep')
                print("DRV8825Driver: Stepper motor initialized")
            
            # Start the stepping thread
            if not self.step_thread_running:
                self.step_thread_running = True
                self.step_thread = threading.Thread(target=self._stepping_loop, daemon=True)
                self.step_thread.start()
                print("DRV8825Driver: Stepping thread started")
            
            self.enabled = True
            return True
            
        except Exception as e:
            print(f"DRV8825Driver: Error initializing stepper motor: {e}")
            return False
    
    def stop(self):
        """
        Stop the motor and cleanup resources.
        """
        print("DRV8825Driver: Stopping motor...")
        
        # Stop stepping thread
        self.step_thread_running = False
        
        # Set target to stopped
        with self.step_lock:
            self.target_direction = "stopped"
            self.target_speed = 0.0
        
        # Wait for thread to finish
        if self.step_thread and self.step_thread.is_alive():
            self.step_thread.join(timeout=1.0)
        
        # Stop motor hardware
        if self.motor:
            try:
                self.motor.Stop()
                print("DRV8825Driver: Motor stopped")
            except Exception as e:
                print(f"DRV8825Driver: Error stopping motor: {e}")
        
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"
    
    def set_speed(self, direction: str, speed: float):
        """
        Set motor direction and speed.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        if not self.enabled:
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        # Calculate step delay from speed (inverse relationship)
        if speed > 0:
            # Map speed (0.0-1.0) to step delay (max_delay to min_delay)
            step_delay = self.max_step_delay - (speed * (self.max_step_delay - self.min_step_delay))
            # print(f"Normalized DRV8825 step delay: {step_delay:.4f}")
        else:
            step_delay = self.max_step_delay
        
        # Update target state for stepping thread
        with self.step_lock:
            self.target_direction = direction
            self.target_speed = speed
            self.current_step_delay = step_delay
        
        # Update current state
        self.current_speed = speed
        self.current_direction = direction
        
        # Calculate steps per second for debugging
        steps_per_sec = 1.0 / (step_delay * 2) if step_delay > 0 else 0
        # print(f"DRV8825Driver: Set direction={direction}, speed={speed:.3f}, delay={step_delay:.4f}s (~{steps_per_sec:.1f} steps/sec)")
        
        # self.motor.TurnStep(Dir=self.target_direction, steps=2, stepdelay=self.current_step_delay)

    
    def is_enabled(self) -> bool:
        """
        Check if the motor driver is enabled and operational.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        return self.enabled and self.motor is not None and self.step_thread_running
    
    def _stepping_loop(self):
        """
        Main stepping loop running in separate thread.
        Continuously steps the motor based on target direction and speed.
        """
        print("DRV8825Driver: Stepping loop started")
        
        while self.step_thread_running:
            try:
                # Get current target state
                with self.step_lock:
                    direction = self.target_direction
                    speed = self.target_speed
                    step_delay = self.current_step_delay
                
                # Check if we should be stepping
                if direction == "stopped" or speed <= 0:
                    time.sleep(0.01)  # Small delay when stopped
                    continue
                
                # Convert direction for DRV8825
                drv_direction = "forward" if direction == "forward" else "backward"
                
                # Perform single step
                if self.motor:
                    self.motor.TurnStep(Dir=drv_direction, steps=1, stepdelay=step_delay)
                
            except Exception as e:
                print(f"DRV8825Driver: Error in stepping loop: {e}")
                time.sleep(0.1)
        
        print("DRV8825Driver: Stepping loop stopped")
    
    def __del__(self):
        """
        Destructor to ensure cleanup.
        """
        if hasattr(self, 'step_thread_running'):
            self.stop()
