"""
YawController class for managing stepper motor operations.
Provides a simple API for controlling stepper motor speed and direction.
"""

import threading
import time
from io_controller import IOController
from typing import Optional, Dict, Any
from motor_drivers import MotorDriver, MotorKitDriver, MotorKitStepperProxy, DRV8825Driver, DRV8825DriverPWM, DRV8825DriverPWMProxy


class YawController:
    """
    Simple stepper motor controller providing speed and direction control.
    """
    
    def __init__(self, io_controller:IOController, motor_type="motorkit_stepper", gpio_handle=None):

        self.io_controller = io_controller

        # Motor control
        self.motor_type = motor_type
        self.motor_driver = None
        self.motor_enabled = False
        
        # GPIO handle (for DRV8825 compatibility)
        self.gpio_handle = gpio_handle
        
        # Motor control parameters
        self.max_motor_speed = 1.0
        self.min_motor_speed = 0.1
        self.motor_current_speed = 0.0
        self.motor_direction = "stopped"  # "forward", "reverse", "stopped"
        
        # State tracking to prevent redundant commands
        self.last_motor_direction = "stopped"
        self.last_motor_speed = 0.0
        self.command_change_threshold = 0.01  # Minimum speed change to trigger new command
        
        # Threading
        self.control_lock = threading.Lock()

        if not self.motor_driver:
            # Create the appropriate motor driver based on motor_type
            if self.motor_type == "motorkit":
                self.motor_driver = MotorKitDriver()
            elif self.motor_type == "motorkit_stepper":
                self.motor_driver = MotorKitStepperProxy(1, self.io_controller, 14, 23, 24)
            elif self.motor_type == "drv8825":
                self.motor_driver = DRV8825Driver(gpio_handle=self.gpio_handle)
            elif self.motor_type == "drv8825_pwm":
                self.motor_driver = DRV8825DriverPWM(gpio_handle=self.gpio_handle)
            elif self.motor_type == "drv8825_pwm_multiprocess":
                self.motor_driver = DRV8825DriverPWMProxy(gpio_handle=self.gpio_handle)
            else:
                print(f"YawController: Unknown motor type: {self.motor_type}")
        
        print("YawController initialized")
    
    
    def start(self) -> bool:
        """Initialize and start motor control"""
        try:
            # Start the motor driver
            if self.motor_driver.start():
                self.motor_enabled = True
                print("YawController: Motor control started")
                return True
            else:
                print("YawController: Failed to start motor driver")
                return False
            
        except Exception as e:
            print(f"YawController: Error initializing motor: {e}")
            return False
    
    def stop(self):
        """Stop motor control and ensure motor is stopped"""
        self.motor_enabled = False
        if hasattr(self, "motor_driver") and self.motor_driver:
            try:
                self.motor_driver.stop()
                self.motor_current_speed = 0.0
                self.motor_direction = "stopped"
                print("YawController: Motor stopped")
            except Exception as e:
                print(f"YawController: Error stopping motor: {e}")
    
    def set_speed_and_direction(self, direction: str, speed: float, duration: float = 3.0, divisions: int = 5):
        """
        Set motor speed and direction.
        
        Args:
            direction: Motor direction ("forward", "reverse", "stopped")
            speed: Motor speed (0.0 to 1.0)
            duration: Duration for the movement in seconds
            divisions: Number of speed divisions for smooth acceleration
        """
        if not self.motor_enabled:
            print("YawController: Motor not enabled. Call start() first.")
            return False
        
        # Validate inputs
        if direction not in ["forward", "reverse", "stopped"]:
            print(f"YawController: Invalid direction '{direction}'. Use 'forward', 'reverse', or 'stopped'.")
            return False
        
        if direction == "stopped":
            speed = 0.0
        else:
            speed = max(0.0, min(1.0, speed))  # Clamp speed between 0.0 and 1.0
            if speed > 0.0:
                # Apply min/max speed scaling
                speed = self.min_motor_speed + (speed * (self.max_motor_speed - self.min_motor_speed))
        
        # Only send command if target has changed significantly
        direction_changed = direction != self.last_motor_direction
        speed_changed = abs(speed - self.last_motor_speed) > self.command_change_threshold
        
        if direction_changed or speed_changed:
            print(f"YawController: Setting motor {direction} at speed {speed:.3f}")
            success = self._send_motor_command(direction, speed, duration, divisions)
            
            if success:
                # Update state tracking
                self.last_motor_direction = direction
                self.last_motor_speed = speed
            
            return success
        
        return True  # No change needed
    
    def _send_motor_command(self, direction: str, speed: float, duration: float = 3.0, divisions: int = 5) -> bool:
        """Send motor command with specified parameters"""
        if self.motor_driver and self.motor_enabled:
            try:
                self.motor_driver.set_speed(direction, speed, duration=duration, divisions=divisions)
                self.motor_current_speed = speed
                self.motor_direction = direction
                return True
            except Exception as e:
                print(f"YawController: Error sending motor command {direction}@{speed:.3f}: {e}")
                return False
        return False
    
    def stop_motor(self):
        """Stop the motor immediately"""
        return self.set_speed_and_direction("stopped", 0.0, duration=1.0, divisions=2)
    
    def get_motor_stats(self) -> Dict[str, Any]:
        """Get motor control statistics"""
        with self.control_lock:
            stats = {
                'motor_direction': self.motor_direction,
                'motor_speed': self.motor_current_speed,
                'motor_enabled': self.motor_enabled,
                'motor_type': self.motor_type,
                'max_motor_speed': self.max_motor_speed,
                'min_motor_speed': self.min_motor_speed
            }
            
            # Add driver-specific stats if available
            if self.motor_driver:
                driver_stats = self.motor_driver.get_stats()
                stats.update({f'driver_{k}': v for k, v in driver_stats.items()})
            
            return stats
    
    def is_motor_enabled(self) -> bool:
        """Check if motor is enabled"""
        return self.motor_enabled
    
    def shutdown(self):
        """Shutdown the YawController and cleanup resources"""
        print("YawController: Shutting down...")
        
        # Stop motor
        self.stop()
        
        print("YawController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()
