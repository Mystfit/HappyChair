"""
YawController class for managing camera yaw control and motor operations.
Subscribes to IOController events for person detection data.
"""

import threading
import time
import math
from typing import Optional, Dict, Any
from motor_drivers import MotorDriver, MotorKitDriver, DRV8825Driver, DRV8825DriverPWM


class YawController:
    """
    Controls camera yaw rotation to track detected persons.
    Subscribes to IOController events for person detection data.
    """
    
    def __init__(self, io_controller=None, motor_type="drv8825_pwm"):
        # IOController reference for event subscription
        self.io_controller = io_controller
        
        # Motor control
        self.motor_type = motor_type
        self.motor_driver = None
        self.motor_enabled = False
        
        # GPIO handle sharing (for DRV8825 compatibility with IOController)
        self.gpio_handle = None
        if self.io_controller and hasattr(self.io_controller, 'gpio_handle'):
            self.gpio_handle = self.io_controller.gpio_handle
        
        # Person tracking
        self.tracking_enabled = False
        self.latest_detections = []
        
        # Movement parameters (received from DetectionProcess)
        self.movement_direction = "stopped"
        self.normalized_speed = 0.0
        self.tracked_person_id = None
        
        # Camera and control parameters
        self.camera_width = 1280  # From shared_memory_manager.py
        self.camera_height = 720
        self.center_x = self.camera_width // 2  # 640px
        self.dead_zone_width = 400  # 400px total dead zone
        self.dead_zone_half = self.dead_zone_width // 2  # ±200px from center
        
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
        self.control_thread = None
        self.control_thread_running = False
        self.control_lock = threading.Lock()
        
        # Register for IOController events
        if self.io_controller:
            self.io_controller.register_event_callback(self._handle_io_event)
        
        print("YawController initialized")
    
    def _handle_io_event(self, event: Dict[str, Any]):
        """Handle events from IOController"""
        event_type = event.get('type')
        data = event.get('data', {})
        
        if event_type == 'person_detected':
            # Update movement parameters from DetectionProcess
            with self.control_lock:
                self.latest_detections = data.get('detections', [])
                self.movement_direction = data.get('movement_direction', 'stopped')
                self.normalized_speed = data.get('normalized_speed', 0.0)
                self.tracked_person_id = data.get('tracked_person_id', None)
        elif event_type == 'pin_changed':
            # Handle GPIO pin changes if needed for future logic
            pin = data.get('pin')
            state = data.get('state')
            print(f"YawController: GPIO pin {pin} changed to {state}")
    
    def start_motor_control(self) -> bool:
        """Initialize and start motor control"""
        try:
            if not self.motor_driver:
                # Create the appropriate motor driver based on motor_type
                if self.motor_type == "motorkit":
                    self.motor_driver = MotorKitDriver()
                elif self.motor_type == "drv8825":
                    self.motor_driver = DRV8825Driver(gpio_handle=self.gpio_handle)
                elif self.motor_type == "drv8825_pwm":
                    self.motor_driver = DRV8825DriverPWM(gpio_handle=self.gpio_handle)
                else:
                    print(f"YawController: Unknown motor type: {self.motor_type}")
                    return False
                
                print(f"YawController: Created {self.motor_type} driver")
            
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
    
    def stop_motor_control(self):
        """Stop motor control and ensure motor is stopped"""
        self.motor_enabled = False
        if self.motor_driver:
            try:
                self.motor_driver.stop()
                self.motor_current_speed = 0.0
                self.motor_direction = "stopped"
                print("YawController: Motor stopped")
            except Exception as e:
                print(f"YawController: Error stopping motor: {e}")
    
    def start_tracking(self) -> bool:
        """Start the person tracking and motor control thread"""
        if self.control_thread_running:
            print("YawController: Tracking already running")
            return False
        
        try:
            # Start motor control
            if not self.start_motor_control():
                return False
            
            # Start control thread
            self.control_thread_running = True
            self.tracking_enabled = True
            self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self.control_thread.start()
            
            print("YawController: Tracking started")
            return True
            
        except Exception as e:
            print(f"YawController: Error starting tracking: {e}")
            self.control_thread_running = False
            self.tracking_enabled = False
            return False
    
    def stop_tracking(self):
        """Stop the person tracking and motor control thread"""
        print("YawController: Stopping tracking...")
        
        self.tracking_enabled = False
        self.control_thread_running = False
        
        # Stop motor
        self.stop_motor_control()
        
        # Wait for control thread to finish
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=2.0)
        
        # Reset tracking
        self.tracked_person_id = None
        
        print("YawController: Tracking stopped")
    
    def _control_loop(self):
        """Main control loop running in separate thread"""
        print("YawController: Control loop started")
        
        while self.control_thread_running:
            try:
                if not self.tracking_enabled or not self.motor_enabled:
                    time.sleep(0.1)
                    continue
                
                # Get movement parameters from DetectionProcess via IOController events
                with self.control_lock:
                    movement_direction = self.movement_direction
                    normalized_speed = self.normalized_speed
                    tracked_person_id = self.tracked_person_id
                
                # Apply motor control based on movement parameters
                self._update_motor_control_from_parameters(movement_direction, normalized_speed, tracked_person_id)
                
                # Control loop frequency (10 Hz)
                time.sleep(0.2)
                
            except Exception as e:
                print(f"YawController: Error in control loop: {e}")
                time.sleep(0.1)
        
        # Ensure motor is stopped when loop exits
        self._stop_motor()
        print("YawController: Control loop stopped")
    
    def _update_motor_control_from_parameters(self, movement_direction: str, normalized_speed: float, tracked_person_id: int):
        """Update motor control based on movement parameters from DetectionProcess"""
        with self.control_lock:
            # Calculate target motor state
            if movement_direction == "stopped" or normalized_speed <= 0:
                target_direction = "stopped"
                target_speed = 0.0
            else:
                # Convert normalized speed to motor speed
                target_speed = self._convert_normalized_to_motor_speed(normalized_speed)
                
                if movement_direction == "left":
                    # Person is on the left, motor should go forward
                    target_direction = "forward"
                elif movement_direction == "right":
                    # Person is on the right, motor should go reverse
                    target_direction = "reverse"
                else:
                    target_direction = "stopped"
                    target_speed = 0.0
            
            # Only send command if target has changed significantly
            direction_changed = target_direction != self.last_motor_direction
            speed_changed = abs(target_speed - self.last_motor_speed) > self.command_change_threshold
            
            if direction_changed or speed_changed:
                # Send new motor command
                if target_direction == "stopped":
                    print(f"YawController: Stopping motor (was {self.last_motor_direction}@{self.last_motor_speed:.3f})")
                    self._send_motor_command(target_direction, target_speed, duration=1.0, divisions=2)
                else:
                    print(f"YawController: Person {tracked_person_id} {movement_direction}, motor {target_direction} at speed {target_speed:.3f} (was {self.last_motor_direction}@{self.last_motor_speed:.3f})")
                    self._send_motor_command(target_direction, target_speed, duration=5.0, divisions=2)
                
                # Update state tracking
                self.last_motor_direction = target_direction
                self.last_motor_speed = target_speed
    
    def _convert_normalized_to_motor_speed(self, normalized_speed: float) -> float:
        """Convert normalized speed (0.0-1.0) to motor speed with min/max scaling"""
        # Apply speed scaling (min to max speed)
        motor_speed = self.min_motor_speed + (normalized_speed * (self.max_motor_speed - self.min_motor_speed))
        return min(motor_speed, self.max_motor_speed)
    
    def _send_motor_command(self, direction: str, speed: float, duration: float = 3.0, divisions: int = 5):
        """Send motor command with specified parameters"""
        if self.motor_driver and self.motor_enabled:
            try:
                self.motor_driver.set_speed(direction, speed, duration=duration, divisions=divisions)
                self.motor_current_speed = speed
                self.motor_direction = direction
            except Exception as e:
                print(f"YawController: Error sending motor command {direction}@{speed:.3f}: {e}")
    
    def _set_motor_forward(self, speed: float):
        """Set motor to move forward at specified speed (legacy method)"""
        self._send_motor_command("forward", speed, duration=3.0, divisions=5)
    
    def _set_motor_reverse(self, speed: float):
        """Set motor to move reverse at specified speed (legacy method)"""
        self._send_motor_command("reverse", speed, duration=3.0, divisions=5)
    
    def _stop_motor(self):
        """Stop the motor (legacy method - used when control loop exits)"""
        if self.motor_driver and self.motor_enabled:
            try:
                # Use smooth transition to stop
                self.motor_driver.set_speed("stopped", 0.0, duration=1.0, divisions=5)
                self.motor_current_speed = 0.0
                self.motor_direction = "stopped"
                # Update state tracking
                self.last_motor_direction = "stopped"
                self.last_motor_speed = 0.0
            except Exception as e:
                print(f"YawController: Error stopping motor: {e}")
    
    def get_motor_stats(self) -> Dict[str, Any]:
        """Get motor control statistics"""
        with self.control_lock:
            stats = {
                'tracked_person_id': self.tracked_person_id,
                'motor_direction': self.motor_direction,
                'motor_speed': self.motor_current_speed,
                'tracking_enabled': self.tracking_enabled,
                'motor_enabled': self.motor_enabled,
                'motor_type': self.motor_type
            }
            
            # Add driver-specific stats if available
            if self.motor_driver:
                driver_stats = self.motor_driver.get_stats()
                stats.update({f'driver_{k}': v for k, v in driver_stats.items()})
            
            return stats
    
    def is_tracking_enabled(self) -> bool:
        """Check if tracking is enabled"""
        return self.tracking_enabled
    
    def shutdown(self):
        """Shutdown the YawController and cleanup resources"""
        print("YawController: Shutting down...")
        
        # Unregister from IOController events
        if self.io_controller:
            self.io_controller.unregister_event_callback(self._handle_io_event)
        
        # Stop tracking
        self.stop_tracking()
        
        print("YawController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()
