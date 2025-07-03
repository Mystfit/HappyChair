"""
YawController class for managing camera yaw control and motor operations.
Subscribes to IOController events for person detection data.
"""

import threading
import time
import math
from typing import Optional, Dict, Any
from adafruit_motorkit import MotorKit


class YawController:
    """
    Controls camera yaw rotation to track detected persons.
    Subscribes to IOController events for person detection data.
    """
    
    def __init__(self, io_controller=None):
        # IOController reference for event subscription
        self.io_controller = io_controller
        
        # Motor control
        self.motor_kit = None
        self.motor_enabled = False
        
        # Person tracking
        self.tracked_person_id = None
        self.tracking_enabled = False
        self.latest_detections = []
        
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
            # Update latest detections for motor control
            with self.control_lock:
                self.latest_detections = data.get('detections', [])
        elif event_type == 'pin_changed':
            # Handle GPIO pin changes if needed for future logic
            pin = data.get('pin')
            state = data.get('state')
            print(f"YawController: GPIO pin {pin} changed to {state}")
    
    def start_motor_control(self) -> bool:
        """Initialize and start motor control"""
        try:
            if not self.motor_kit:
                self.motor_kit = MotorKit()
                print("YawController: Motor kit initialized")
            
            self.motor_enabled = True
            return True
            
        except Exception as e:
            print(f"YawController: Error initializing motor: {e}")
            return False
    
    def stop_motor_control(self):
        """Stop motor control and ensure motor is stopped"""
        self.motor_enabled = False
        if self.motor_kit:
            try:
                self.motor_kit.motor1.throttle = 0
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
                
                # Get latest detection results from IOController events
                with self.control_lock:
                    detections = self.latest_detections.copy()
                
                if not detections:
                    time.sleep(0.1)
                    continue
                
                # Find person to track
                target_detection = self._find_target_person(detections)
                
                if target_detection:
                    # Calculate motor control
                    self._update_motor_control(target_detection)
                else:
                    # No target found, stop motor
                    self._stop_motor()
                
                # Control loop frequency (10 Hz)
                time.sleep(0.1)
                
            except Exception as e:
                print(f"YawController: Error in control loop: {e}")
                time.sleep(0.1)
        
        # Ensure motor is stopped when loop exits
        self._stop_motor()
        print("YawController: Control loop stopped")
    
    def _find_target_person(self, detections: list) -> Optional[Dict]:
        """Find the person to track based on tracking logic"""
        if not detections:
            return None
        
        # If we have a tracked person, try to find them
        if self.tracked_person_id is not None:
            for detection in detections:
                if detection.get('track_id') == self.tracked_person_id:
                    return detection
            
            # Tracked person not found, reset tracking
            print(f"YawController: Lost track of person {self.tracked_person_id}")
            self.tracked_person_id = None
        
        # No tracked person or lost track, find first available person
        for detection in detections:
            track_id = detection.get('track_id', 0)
            if track_id > 0:
                self.tracked_person_id = track_id
                print(f"YawController: Now tracking person {track_id}")
                return detection
        
        return None
    
    def _update_motor_control(self, detection: Dict):
        """Update motor control based on person's position"""
        bbox = detection.get('bbox', (0, 0, 0, 0))
        x, y, w, h = bbox
        x *= 1280  # Scale bounding box x position to camera width
        y *= 720   # Scale bounding box y position to camera height
        w *= 1280  # Scale bounding box width to camera width
        h *= 720   # Scale bounding box height to camera height

        # Calculate person's center X position
        person_center_x = x + (w / 2)
        
        # Calculate distance from camera center
        distance_from_center = person_center_x - self.center_x
        
        with self.control_lock:
            # Check if person is in dead zone
            if abs(distance_from_center) <= self.dead_zone_half:
                # Person is in dead zone, stop motor
                self._stop_motor()
                return
            
            print(f"Bounding box: {bbox}, Tracking ID: {detection.get('track_id', 'N/A')}, Person Center X: {person_center_x}")
            
            # Calculate motor speed based on distance from dead zone edge
            if distance_from_center < -self.dead_zone_half:
                # Person is on the left, motor should go forward
                distance_from_dead_zone = abs(distance_from_center) - self.dead_zone_half
                max_distance = self.center_x - self.dead_zone_half
                speed = self._calculate_motor_speed(distance_from_dead_zone, max_distance)
                print(f"Person on left, speed: {speed}")
                self._set_motor_forward(speed)
                
            elif distance_from_center > self.dead_zone_half:
                # Person is on the right, motor should go reverse
                distance_from_dead_zone = distance_from_center - self.dead_zone_half
                max_distance = self.center_x - self.dead_zone_half
                speed = self._calculate_motor_speed(distance_from_dead_zone, max_distance)
                print(f"Person on right, speed: {speed}")
                self._set_motor_reverse(speed)
    
    def _calculate_motor_speed(self, distance_from_dead_zone: float, max_distance: float) -> float:
        """Calculate motor speed based on distance from dead zone"""
        # Normalize distance (0.0 to 1.0)
        normalized_distance = min(distance_from_dead_zone / max_distance, 1.0)
        
        # Apply speed scaling (min to max speed)
        speed = self.min_motor_speed + (normalized_distance * (self.max_motor_speed - self.min_motor_speed))
        
        return min(speed, self.max_motor_speed)
    
    def _set_motor_forward(self, speed: float):
        """Set motor to move forward at specified speed"""
        if self.motor_kit and self.motor_enabled:
            try:
                self.motor_kit.motor1.throttle = speed
                self.motor_current_speed = speed
                self.motor_direction = "forward"
            except Exception as e:
                print(f"YawController: Error setting motor forward: {e}")
    
    def _set_motor_reverse(self, speed: float):
        """Set motor to move reverse at specified speed"""
        if self.motor_kit and self.motor_enabled:
            try:
                self.motor_kit.motor1.throttle = -speed
                self.motor_current_speed = speed
                self.motor_direction = "reverse"
            except Exception as e:
                print(f"YawController: Error setting motor reverse: {e}")
    
    def _stop_motor(self):
        """Stop the motor"""
        if self.motor_kit and self.motor_enabled:
            try:
                self.motor_kit.motor1.throttle = 0
                self.motor_current_speed = 0.0
                self.motor_direction = "stopped"
            except Exception as e:
                print(f"YawController: Error stopping motor: {e}")
    
    def get_motor_stats(self) -> Dict[str, Any]:
        """Get motor control statistics"""
        with self.control_lock:
            return {
                'tracked_person_id': self.tracked_person_id,
                'motor_direction': self.motor_direction,
                'motor_speed': self.motor_current_speed,
                'tracking_enabled': self.tracking_enabled,
                'motor_enabled': self.motor_enabled
            }
    
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
