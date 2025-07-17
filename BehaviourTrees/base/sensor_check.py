"""
Generic sensor check behaviours for py_trees.
"""

import py_trees
from py_trees import common
from typing import Dict, Any


class SensorCheck(py_trees.behaviour.Behaviour):
    """Generic behaviour for checking sensor states."""
    
    def __init__(self, name: str, sensor_key: str, io_controller, pin: int, 
                 inverted: bool = True, blackboard_namespace: str = "Sensor"):
        super().__init__(name)
        self.io_controller = io_controller
        self.pin = pin
        self.sensor_key = sensor_key
        self.inverted = inverted  # For pull-up configurations where 0 = active
        self.blackboard = self.attach_blackboard_client(name=blackboard_namespace)
        self.blackboard.register_key(sensor_key, common.Access.WRITE)
        self.blackboard.register_key(f"{sensor_key}_last", common.Access.WRITE)
        
        # Initialize blackboard values
        setattr(self.blackboard, sensor_key, False)
        setattr(self.blackboard, f"{sensor_key}_last", False)

    def update(self):
        try:
            # Get pin state from IO controller
            if not self.io_controller:
                self.feedback_message = "IOController not initialized"
                return common.Status.FAILURE
            
            pin_states = self.io_controller.get_pin_states()
            pin_state = pin_states.get(self.pin, {}).get('state', 1)
            
            # Apply inversion if configured (for pull-up: 0 = active, 1 = inactive)
            sensor_active = (pin_state == 0) if self.inverted else (pin_state == 1)
            
            # Check for state change
            current_state = getattr(self.blackboard, self.sensor_key, False)
            updated = sensor_active != current_state
            
            # Update blackboard
            setattr(self.blackboard, self.sensor_key, sensor_active)
            
            if updated:            
                if sensor_active:
                    self.feedback_message = f"{self.sensor_key} is active"
                else:
                    self.feedback_message = f"{self.sensor_key} is inactive"
                return common.Status.SUCCESS
            
            return common.Status.SUCCESS
        
        except Exception as e:
            self.feedback_message = f"Error reading {self.sensor_key}: {str(e)}"
            return common.Status.FAILURE


class PersonDetectionCheck(py_trees.behaviour.Behaviour):
    """Generic behaviour for checking person detection from camera."""
    
    def __init__(self, name: str, camera_controller, blackboard_namespace: str = "Camera"):
        super().__init__(name)
        self.camera_controller = camera_controller
        self.blackboard = self.attach_blackboard_client(name=blackboard_namespace)
        
        # Register blackboard keys
        keys = ["can_scan", "person_detected", "person_count", "tracked_person_info", 
                "movement_direction", "normalized_speed"]
        for key in keys:
            self.blackboard.register_key(key, common.Access.WRITE)
        
        # Initialize blackboard values
        self.blackboard.can_scan = False
        self.blackboard.person_detected = False
        self.blackboard.person_count = 0
        self.blackboard.tracked_person_info = None
        self.blackboard.movement_direction = "stopped"
        self.blackboard.normalized_speed = 0.0
        
    def update(self):
        try:
            stats = self.camera_controller.get_detection_stats()
            person_count = stats.get('person_count', 0)
            person_id = stats.get('tracked_person_id', None)
            movement_direction = stats.get('movement_direction', None)
            normalized_speed = stats.get('normalized_speed', None)
                        
            updated = person_id is not None
            self.blackboard.person_count = person_count
            self.blackboard.tracked_person_info = None
            self.blackboard.person_detected = person_id is not None
            self.blackboard.movement_direction = movement_direction
            self.blackboard.normalized_speed = normalized_speed
            
            if updated:
                if person_id:
                    self.feedback_message = f"Tracking person {person_id}"
                else:
                    self.feedback_message = "No person detected"
                return common.Status.SUCCESS
            
            self.feedback_message = "No change in person detection"
            return common.Status.SUCCESS
        except Exception as e:
            self.feedback_message = f"Error in person detection: {str(e)}"
            return common.Status.FAILURE