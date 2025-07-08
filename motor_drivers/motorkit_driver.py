"""
MotorKit driver implementation for Adafruit MotorKit.
Wraps the existing adafruit_motorkit functionality.
"""

import threading
from .base_driver import MotorDriver
from adafruit_motorkit import MotorKit


class MotorKitDriver(MotorDriver):
    """
    Motor driver implementation for Adafruit MotorKit.
    Provides DC motor control with continuous speed adjustment.
    """
    
    def __init__(self):
        super().__init__()
        self.motor_kit = None
    
    def start(self) -> bool:
        """
        Initialize and start the MotorKit driver.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.motor_kit:
                self.motor_kit = MotorKit()
                print("MotorKitDriver: Motor kit initialized")
            
            self.enabled = True
            return True
            
        except Exception as e:
            print(f"MotorKitDriver: Error initializing motor: {e}")
            return False
    
    def stop(self):
        """
        Stop the motor and cleanup resources.
        """
        # Stop any active transitions
        self.stop_transitions()
        
        self.enabled = False
        if self.motor_kit:
            try:
                self.motor_kit.motor1.throttle = 0
                self.current_speed = 0.0
                self.current_direction = "stopped"
                print("MotorKitDriver: Motor stopped")
            except Exception as e:
                print(f"MotorKitDriver: Error stopping motor: {e}")
    
    # set_speed is now inherited from base class
    
    def _set_speed_immediate(self, direction: str, speed: float):
        """
        Set motor direction and speed immediately (internal method).
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        if not self.motor_kit or not self.enabled:
            return
        
        try:
            if direction == "stopped":
                self.motor_kit.motor1.throttle = 0
                self.current_speed = 0.0
                self.current_direction = "stopped"
            elif direction == "forward":
                self.motor_kit.motor1.throttle = speed
                self.current_speed = speed
                self.current_direction = "forward"
            elif direction == "reverse":
                self.motor_kit.motor1.throttle = -speed
                self.current_speed = speed
                self.current_direction = "reverse"
            else:
                print(f"MotorKitDriver: Invalid direction: {direction}")
                
        except Exception as e:
            print(f"MotorKitDriver: Error setting motor speed: {e}")
    
    def is_enabled(self) -> bool:
        """
        Check if the motor driver is enabled and operational.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        return self.enabled and self.motor_kit is not None
