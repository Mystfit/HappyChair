"""
Chair-specific behaviour tree implementation.
"""

import py_trees
from py_trees import common, composites, behaviours, decorators
import operator
from typing import Dict, Any

from ..base import AnimatronicBehaviourTree, AnimationAction, SensorCheck, TrackingAction


class ChairBehaviourTree(AnimatronicBehaviourTree):
    """Chair-specific behaviour tree implementation."""
    
    # Chair-specific configuration
    SEAT_SENSOR = "seatsensor"

    ANIMATIONS = {
        'hug_intro': 'hug_intro',
        'hug_idle': 'hug', 
        'hug_outro': 'hug_exit'
    }
    
    def __init__(self, animation_controller, yaw_controller, camera_controller, io_controller):
        # Map yaw_controller to tracking_controller for base class
        super().__init__(animation_controller, yaw_controller, camera_controller, io_controller)
        
        print("ChairBehaviourTree initialized")
    
    def _register_blackboard_keys(self):
        """Register chair-specific blackboard keys."""
        super()._register_blackboard_keys()
        # Add chair-specific keys
        chair_keys = ["seat_occupied", "seat_occupied_last"]
        for key in chair_keys:
            self.blackboard.register_key(key=key, access=common.Access.READ)
    
    def _create_sensor_tree(self):
        """Create chair-specific sensor monitoring tree."""
        sensor_root = composites.Parallel(name="Sensors", policy=py_trees.common.ParallelPolicy.SuccessOnAll())

        # Seat sensor check
        seat_sensor_check = SensorCheck(
            name="Seat Sensor Check",
            sensor_key="seat_occupied",
            io_controller=self.io_controller,
            pin_name=self.SEAT_SENSOR,
            pin_value_inverted=True,  # Pin should be pull-up configuration so invert pin state
            blackboard_namespace="GPIO"
        )
        
        # Person detection check
        from ..base.sensor_check import PersonDetectionCheck
        person_detection_check = PersonDetectionCheck(
            name="Person Detection Check",
            camera_controller=self.camera_controller
        )
        
        sensor_root.add_children([
            seat_sensor_check,
            person_detection_check
        ])
        
        return sensor_root

    def _create_tasks_tree(self):
        """Create chair-specific tasks tree."""
        tasks_selector = composites.Selector(name="Tasks", memory=True)
        
        sitting_node = self._create_sitting_tree()
        scanning_node = self._create_scanning_tree()
        
        tasks_selector.add_children([
            sitting_node,
            scanning_node
        ])
        
        return tasks_selector
    
    def _create_sitting_tree(self):
        """Create the behaviour tree for when a person is sitting on the chair."""
        
        guard_sitting_in_seat = behaviours.CheckBlackboardVariableValue(
            name="Check: Is seat occupied?",
            check=common.ComparisonExpression(
                variable="seat_occupied", value=True, operator=operator.eq
            )
        )
        
        guard_not_previously_in_seat = behaviours.CheckBlackboardVariableValue(
            name="Check: Was seat previously occupied?",
            check=common.ComparisonExpression(
                variable="seat_occupied_last", value=False, operator=operator.eq
            )
        )
        
        person_in_seat_last_BB = behaviours.SetBlackboardVariable(
            name="BB: Set person in seat",
            variable_name="seat_occupied_last",
            variable_value=True,
            overwrite=True
        )
        
        # Disable scanning while sitting
        disable_scanning_bb = behaviours.SetBlackboardVariable(
            name="BB: Disable scanning",
            variable_name="can_scan",
            variable_value=False,
            overwrite=True
        )

        # Create the sitting root sequence
        sitting_animgraph = composites.Sequence(name="Sitting animations", memory=True)
        
        # Create actions for playing chair-specific animations
        hug_intro_anim = AnimationAction(
            name="Anim: Hug Intro",
            animation_controller=self.animation_controller,
            animation_name=self.ANIMATIONS['hug_intro']
        )
        idle_animation = AnimationAction(
            name="Anim: Hug idle",
            animation_controller=self.animation_controller,
            animation_name=self.ANIMATIONS['hug_idle'],
            looping=True,
            autoplay=False
        )
        
        guard_person_left_seat = decorators.FailureIsRunning(
            name="Decorator: Hug Outro",
            child=behaviours.CheckBlackboardVariableValue(
                name="Check: Did person leave seat?",
                check=common.ComparisonExpression(
                    variable="seat_occupied", value=False, operator=operator.eq
                )
            )
        )
        
        # Outro animation to handle when person gets up
        hug_outro_anim = AnimationAction(
            name="Anim: hug outro",
            animation_controller=self.animation_controller,
            animation_name=self.ANIMATIONS['hug_outro']
        )
        person_finished_leaving_bb = behaviours.SetBlackboardVariable(
            name="BB: Set person finished leaving",
            variable_name="seat_occupied_last",
            variable_value=False,
            overwrite=True
        )
        enable_scanning_bb = behaviours.SetBlackboardVariable(
            name="BB: Enable scanning",
            variable_name="can_scan",
            variable_value=True,
            overwrite=True
        )
        
        guard_leave_sitting_animations = behaviours.CheckBlackboardVariableValue(
            name="Check: Is seat occupied?",
            check=common.ComparisonExpression(
                variable="seat_occupied", value=False, operator=operator.eq
            )
        )
        
        hug_outro_sequence = composites.Sequence(name="AnimSeq: Transition out of hug", memory=True)
        hug_outro_sequence.add_children([
            guard_leave_sitting_animations,
            hug_outro_anim,
            person_finished_leaving_bb,
            enable_scanning_bb
        ])
        
        # Add behaviours to the sitting root
        sitting_animgraph.add_children([
            guard_sitting_in_seat,
            guard_not_previously_in_seat,
            person_in_seat_last_BB,
            disable_scanning_bb,
            hug_intro_anim,
            idle_animation,
            guard_person_left_seat,
            hug_outro_sequence
        ])  

        # Guard sitting animations to play only when seat is occupied
        sitting_exit_selector = composites.Selector(name="Sitting Exit Selector", memory=True)
        sitting_exit_selector.add_children([ 
            sitting_animgraph
        ])

        return sitting_exit_selector
    
    def _create_scanning_tree(self):
        """Create the behaviour tree for when no one is sitting on the chair."""
        # Tree to handle when no-one is sitting on the chair
        scan_root = py_trees.composites.Sequence(name="Scan", memory=True)
        is_scan_requested = behaviours.CheckBlackboardVariableValue(
            name="Check: Can look for people?",
            check=common.ComparisonExpression(
                variable="can_scan", value=True, operator=operator.eq
            )
        )
        
        scan_handle_states = composites.Selector(name="Searching for person", memory=True)
        
        person_detected = behaviours.CheckBlackboardVariableValue(
            name="Person detected?",
            check=common.ComparisonExpression(
                variable="person_detected", value=True, operator=operator.eq
            )
        )
        scan_handle_states.add_children([
            person_detected,
            behaviours.Success(name="Placeholder: Rotate chair to face person"),
        ])
        
        scan_root.add_children([
            is_scan_requested,
            scan_handle_states
        ])
        
        return scan_root
    
    def get_blackboard_data(self) -> Dict[str, Any]:
        """Get current blackboard data including chair-specific data."""
        data = super().get_blackboard_data()
        # Add chair-specific blackboard data
        data.update({
            'seat_occupied': self.blackboard.seat_occupied if self.blackboard.exists('seat_occupied') else False,
            'seat_occupied_last': self.blackboard.seat_occupied_last if self.blackboard.exists('seat_occupied_last') else False,
        })
        return data