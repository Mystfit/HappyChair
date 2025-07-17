"""
Generic tracking action behaviour for py_trees.
"""

import py_trees
from py_trees import common
import time


class TrackingAction(py_trees.behaviour.Behaviour):
    """Generic behaviour for controlling tracking mechanisms (yaw, pan/tilt, etc.)."""
    
    def __init__(self, name: str, tracking_controller, 
                 person_detected_key: str = "person_detected",
                 movement_direction_key: str = "movement_direction",
                 speed_key: str = "normalized_speed"):
        super().__init__(name)
        self.tracking_controller = tracking_controller
        self.person_detected_key = person_detected_key
        self.movement_direction_key = movement_direction_key
        self.speed_key = speed_key
        self.start_time = None
        
    def initialise(self):
        self.logger.debug(f"  {self.name} [TrackingAction::initialise()]")
        self.start_time = time.time()
        try:
            if not self.tracking_controller.is_motor_enabled():
                self.tracking_controller.start()
            
            # Set target speed and direction by checking the blackboard
            direction = self.blackboard.get(self.movement_direction_key, "stopped")
            speed = self.blackboard.get(self.speed_key, 0.5)
            self.tracking_controller.set_speed_and_direction(direction, speed, 2.0)
            
            self.feedback_message = f"Started tracking: {direction} at {speed}"
        except Exception as e:
            self.feedback_message = f"Error starting tracking: {str(e)}"
        
    def update(self):
        try:
            if self.start_time is None:
                return common.Status.FAILURE
            
            # Check if we have a person to track
            if not self.blackboard.get(self.person_detected_key, False):
                self.feedback_message = "No person detected, stopping tracking"
                self.tracking_controller.stop_motor()
                return common.Status.FAILURE
                
            # Check if we're already facing the person
            if self.blackboard.get(self.movement_direction_key, "stopped") == "stopped":
                self.feedback_message = "Facing person, stopping tracking"
                self.tracking_controller.stop_motor()
                return common.Status.SUCCESS
                
            # Check if the tracking controller is still running
            if self.tracking_controller.motor_enabled:
                self.feedback_message = "Tracking in progress"
                return common.Status.RUNNING
                
        except Exception as e:
            self.feedback_message = f"Error in tracking: {str(e)}. Force stopping motor."
            # Force stop motor on error
            self.tracking_controller.set_speed_and_direction("stopped", 0, 0)
            return common.Status.FAILURE
            
    def terminate(self, new_status):
        self.logger.debug(f"  {self.name} [TrackingAction::terminate()][{self.status}->{new_status}]")
        try:
            self.tracking_controller.stop_motor()
        except Exception as e:
            self.logger.error(f"Error stopping tracking: {str(e)}")