"""
Abstract base class for motor drivers.
Defines the common interface that all motor implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class MotorDriver(ABC):
    """
    Abstract base class for motor drivers.
    All motor implementations must inherit from this class and implement its methods.
    """
    
    def __init__(self):
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"  # "forward", "reverse", "stopped"
    
    @abstractmethod
    def start(self) -> bool:
        """
        Initialize and start the motor driver.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop the motor and cleanup resources.
        """
        pass
    
    @abstractmethod
    def set_speed(self, direction: str, speed: float):
        """
        Set motor direction and speed.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
        """
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """
        Check if the motor driver is enabled and operational.
        
        Returns:
            bool: True if enabled, False otherwise
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current motor statistics.
        
        Returns:
            Dict containing current motor state
        """
        return {
            'enabled': self.enabled,
            'speed': self.current_speed,
            'direction': self.current_direction
        }
