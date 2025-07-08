"""
Abstract base class for motor drivers.
Defines the common interface that all motor implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import threading
import time


class MotorDriver(ABC):
    """
    Abstract base class for motor drivers.
    All motor implementations must inherit from this class and implement its methods.
    """
    
    def __init__(self):
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"  # "forward", "reverse", "stopped"
        
        # Continuous transition control
        self.transition_thread = None
        self.transition_active = False
        self.transition_lock = threading.Lock()
        
        # Target state for continuous transitions
        self.target_speed = 0.0
        self.target_direction = "stopped"
        self.target_duration = 0.0
        self.target_divisions = 10
        self.target_updated = False
    
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
    
    def set_speed(self, direction: str, speed: float, duration: float = 0.0, divisions: int = 10):
        """
        Set motor direction and speed with optional smooth transitions.
        
        Args:
            direction (str): "forward", "reverse", or "stopped"
            speed (float): Speed value between 0.0 and 1.0
            duration (float): Time in seconds to reach target speed (0.0 for immediate)
            divisions (int): Number of steps to reach target speed during transition
        """
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        if duration <= 0.0:
            # Immediate speed change
            self._set_speed_immediate(direction, speed)
        else:
            # Update target for continuous transition
            self._update_transition_target(direction, speed, duration, divisions)
    
    def _update_transition_target(self, direction: str, speed: float, duration: float, divisions: int):
        """
        Update the target for continuous smooth transitions.
        
        Args:
            direction (str): Target direction
            speed (float): Target speed (0.0 to 1.0)
            duration (float): Duration in seconds
            divisions (int): Number of transition steps
        """
        with self.transition_lock:
            self.target_direction = direction
            self.target_speed = speed
            self.target_duration = duration
            self.target_divisions = divisions
            self.target_updated = True
            
            # Start transition thread if not already running
            if not self.transition_active:
                self.transition_active = True
                self.transition_thread = threading.Thread(
                    target=self._continuous_transition_loop,
                    daemon=True
                )
                self.transition_thread.start()
    
    @abstractmethod
    def _set_speed_immediate(self, direction: str, speed: float):
        """
        Set motor direction and speed immediately (internal method).
        
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
            'direction': self.current_direction,
            'transition_active': self.transition_active
        }
    
    def _continuous_transition_loop(self):
        """
        Continuous transition loop that smoothly moves toward the current target.
        Updates target dynamically when set_speed is called with new values.
        """
        try:
            while True:
                with self.transition_lock:
                    if not self.transition_active:
                        break
                    
                    current_target_direction = self.target_direction
                    current_target_speed = self.target_speed
                    current_duration = self.target_duration
                    current_divisions = self.target_divisions
                    target_was_updated = self.target_updated
                    self.target_updated = False
                
                # Check if we've reached the target
                if (abs(self.current_speed - current_target_speed) < 0.01 and 
                    self.current_direction == current_target_direction and 
                    not target_was_updated):
                    # We're at the target, sleep briefly and check again
                    time.sleep(0.05)
                    continue
                
                # Calculate step toward target
                self._step_toward_target(
                    current_target_direction, 
                    current_target_speed, 
                    current_duration, 
                    current_divisions
                )
                
                # Small delay between steps
                time.sleep(0.05)  # 20Hz update rate
                
        except Exception as e:
            print(f"MotorDriver: Error in continuous transition loop: {e}")
        finally:
            with self.transition_lock:
                self.transition_active = False
    
    def _step_toward_target(self, target_direction: str, target_speed: float, duration: float, divisions: int):
        """
        Take one step toward the target speed and direction.
        
        Args:
            target_direction (str): Target direction
            target_speed (float): Target speed
            duration (float): Total duration for the transition
            divisions (int): Number of divisions for the transition
        """
        current_speed = self.current_speed
        current_direction = self.current_direction
        
        # Handle direction changes - need to go through zero first
        if current_direction != target_direction and current_direction != "stopped" and current_speed > 0:
            # First slow down to zero in current direction
            step_size = self._calculate_step_size(current_speed, 0.0, duration, divisions)
            new_speed = max(0.0, current_speed - step_size)
            self._set_speed_immediate(current_direction, new_speed)
            return
        
        # Handle the case where we've reached zero speed during a direction change
        if current_speed == 0.0 and current_direction != target_direction and target_direction != "stopped":
            # We're at zero speed and need to change direction - update direction and start accelerating
            step_size = self._calculate_step_size(0.0, target_speed, duration, divisions)
            new_speed = min(target_speed, step_size)
            self._set_speed_immediate(target_direction, new_speed)
            return
        
        # Same direction or stopped - move toward target speed
        if current_direction == target_direction or (current_direction == "stopped" and target_direction == "stopped"):
            step_size = self._calculate_step_size(current_speed, target_speed, duration, divisions)
            
            if current_speed < target_speed:
                # Accelerating
                new_speed = min(target_speed, current_speed + step_size)
            else:
                # Decelerating
                new_speed = max(target_speed, current_speed - step_size)
            
            self._set_speed_immediate(target_direction, new_speed)
    
    def _calculate_step_size(self, current_speed: float, target_speed: float, duration: float, divisions: int) -> float:
        """
        Calculate the step size for smooth transitions.
        
        Args:
            current_speed (float): Current speed
            target_speed (float): Target speed
            duration (float): Total duration
            divisions (int): Number of divisions
            
        Returns:
            float: Step size for this iteration
        """
        if divisions <= 0:
            divisions = 1
        
        # Calculate step size based on duration and update rate (20Hz = 0.05s per step)
        update_rate = 0.05  # 20Hz
        total_steps = max(1, int(duration / update_rate))
        
        speed_difference = abs(target_speed - current_speed)
        step_size = speed_difference / total_steps
        
        # Ensure minimum step size for progress - increased for better responsiveness
        min_step_size = 0.02
        return max(step_size, min_step_size)
    
    def stop_transitions(self):
        """Stop any active transitions and set motor to stopped immediately."""
        with self.transition_lock:
            self.transition_active = False
            self.target_direction = "stopped"
            self.target_speed = 0.0
            self.target_updated = True
        
        # Wait for transition thread to finish
        if self.transition_thread and self.transition_thread.is_alive():
            self.transition_thread.join(timeout=1.0)
        
        # Immediately stop the motor
        self._set_speed_immediate("stopped", 0.0)
