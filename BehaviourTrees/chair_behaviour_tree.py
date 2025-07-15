"""
ChairBehaviourTree class for managing behaviour tree operations.
Integrates with existing controllers using py_trees library.
"""

import py_trees
from py_trees import common, composites, behaviours, decorators, blackboard
import threading
import time
from typing import Dict, Any, Optional, List
import uuid

from camera_controller import CameraController
from Servo.Animation import ServoAnimationController
from io_controller import IOController
from yaw_controller import YawController


class PlayAnimationAction(py_trees.behaviour.Behaviour):
    """Custom behaviour for playing servo animations."""
    
    def __init__(self, name: str, animation_controller: ServoAnimationController, animation_name: str):
        super().__init__(name)
        self.animation_controller = animation_controller
        self.animation_name = animation_name
        self.blackboard = self.attach_blackboard_client(name="Animation")
        self.blackboard.register_key("current_animation", common.Access.WRITE)
        
    def setup(self, **kwargs):
        self.logger.debug(f"  {self.name} [PlayAnimationBehaviour::setup()]")
        
    def initialise(self):
        self.logger.debug(f"  {self.name} [PlayAnimationBehaviour::initialise()]")
        # Start the animation
        try:
            layer = self.animation_controller.get_layer_by_name(self.animation_name)
            if not layer and self.animation_name in self.animation_controller.available_animations:
                layer = self.animation_controller.create_layer(
                    self.animation_controller.available_animations[self.animation_name],
                    self.animation_name, 1.0, False
                )
            if layer:
                layer.play()
                self.blackboard.current_animation = self.animation_name
                self.feedback_message = f"Started animation: {self.animation_name}"
            else:
                self.feedback_message = f"Animation not found: {self.animation_name}"
        except Exception as e:
            self.feedback_message = f"Error starting animation: {str(e)}"
        
    def update(self):
        self.logger.debug(f"  {self.name} [PlayAnimationBehaviour::update()]")
        # Check if animation is still playing
        try:
            layer = self.animation_controller.get_layer_by_name(self.animation_name)
            if layer and layer.is_playing():
                return common.Status.RUNNING
            
            if layer.is_blending_out():
                self.feedback_message = f"Animation {self.animation_name} beginning to blend out"
                return common.Status.SUCCESS

            if layer.is_completed():
                self.feedback_message = f"Animation {self.animation_name} completed"
                return common.Status.SUCCESS
        except Exception as e:
            self.feedback_message = f"Error checking animation: {str(e)}"
            return common.Status.FAILURE
            
    def terminate(self, new_status):
        self.logger.debug(f"  {self.name} [PlayAnimationBehaviour::terminate()][{self.status}->{new_status}]")
        if new_status == common.Status.INVALID:
            # Stop animation if interrupted
            try:
                layer = self.animation_controller.get_layer_by_name(self.animation_name)
                if layer:
                    layer.stop()
            except Exception as e:
                self.logger.error(f"Error stopping animation: {str(e)}")


class PersonDetectionCheck(py_trees.behaviour.Behaviour):
    """Custom behaviour for checking person detection."""
    
    def __init__(self, name: str, camera_controller: CameraController):
        super().__init__(name)
        self.camera_controller = camera_controller
        self.blackboard = self.attach_blackboard_client(name="Camera")
        self.blackboard.register_key("person_detected", common.Access.WRITE)
        self.blackboard.register_key("person_count", common.Access.WRITE)
        self.blackboard.register_key("tracked_person_info", common.Access.WRITE)
        self.blackboard.register_key("movement_direction", common.Access.WRITE)
        self.blackboard.register_key("normalized_speed", common.Access.WRITE)
        
    def update(self):
        try:
            stats = self.camera_controller.get_detection_stats()
            person_count = stats.get('person_count', 0)
            person_id = stats.get('tracked_person_id', None)
            detections = stats.get('detections', [])
            movement_direction = stats.get('movement_direction', None)
            normalized_speed = stats.get('normalized_speed', None)
            
            self.blackboard.person_detected = person_count > 0
            self.blackboard.person_count = person_count
            self.blackboard.tracked_person_info = detections[person_id] if person_id is not None and detections else None
            self.blackboard.movement_direction = movement_direction
            self.blackboard.normalized_speed = normalized_speed
            
            if person_id:
                self.feedback_message = f"Tracking person {person_id}"
                return common.Status.SUCCESS
            else:
                self.feedback_message = "No person detected"
                return common.Status.FAILURE
        except Exception as e:
            self.feedback_message = f"Error in person detection: {str(e)}"
            return common.Status.FAILURE


class SeatSensorCheck(py_trees.behaviour.Behaviour):
    """Custom behaviour for checking seat sensor."""
    
    def __init__(self, name: str, pin: int, io_controller: IOController):
        super().__init__(name)
        self.io_controller = io_controller
        self.pin = pin
        self.blackboard = self.attach_blackboard_client(name="GPIO")
        self.blackboard.register_key("seat_occupied", common.Access.WRITE)
        
    def update(self):
        try:
            # Get pin state from IO controller
            if not self.io_controller:
                self.feedback_message = "IOController not initialized"
                return common.Status.FAILURE
            
            pin_states = self.io_controller.get_pin_states()
            seat_sensor_state = pin_states.get(self.pin, {}).get('state', 1)
            
            # Assuming pull-up configuration: 0 = occupied, 1 = not occupied
            occupied = seat_sensor_state == 0
            self.blackboard.seat_occupied = occupied
            
            if occupied:
                self.feedback_message = "Seat is occupied"
                return common.Status.SUCCESS
            else:
                self.feedback_message = "Seat is not occupied"
                return common.Status.FAILURE
        except Exception as e:
            self.feedback_message = f"Error reading seat sensor: {str(e)}"
            return common.Status.FAILURE


class TrackToFacePersonAction(py_trees.behaviour.Behaviour):
    """Custom behaviour for controlling chair yaw rotation."""
    
    def __init__(self, name: str, yaw_controller: YawController):
        super().__init__(name)
        self.yaw_controller = yaw_controller
        self.start_time = None
        
    def initialise(self):
        self.logger.debug(f"  {self.name} [YawControlBehaviour::initialise()]")
        self.start_time = time.time()
        try:
            if not self.yaw_controller.is_motor_enabled():
                self.yaw_controller.start()
            
            # Set target speed and direction by checking the blackboard
            direction = self.blackboard.get("movement_direction", "stopped")
            speed = self.blackboard.get("normalized_speed", 0.5)
            self.yaw_controller.set_speed_and_direction(direction, speed, 2.0)
            
            self.feedback_message = f"Started yaw control: {direction} at {speed}"
        except Exception as e:
            self.feedback_message = f"Error starting yaw control: {str(e)}"
        
    def update(self):
        try:
            if self.start_time is None:
                return common.Status.FAILURE
            
            # Check if we are facing the person by checking the person_detected and movement_direction keys on the blackboard
            if not self.blackboard.get("person_detected", False):
                self.feedback_message = "No person detected, stopping yaw control"
                self.yaw_controller.stop_motor()
                return common.Status.FAILURE
            if self.blackboard.get("movement_direction", "stopped") == "stopped":
                self.feedback_message = "Facing person, stopping yaw control"
                self.yaw_controller.stop_motor()
                return common.Status.SUCCESS
            # Check if the yaw controller is still running
            if self.yaw_controller.motor_enabled:
                self.feedback_message = "Tracking to face person"
                return common.Status.RUNNING
        except Exception as e:
            self.feedback_message = f"Error in yaw control: {str(e)}. Force stopping motor."
            # Force stop motor on error
            self.yaw_controller.set_speed_and_direction("stopped", 0, 0)
            return common.Status.FAILURE
            
    def terminate(self, new_status):
        self.logger.debug(f"  {self.name} [YawControlBehaviour::terminate()][{self.status}->{new_status}]")
        try:
            self.yaw_controller.stop_motor()
        except Exception as e:
            self.logger.error(f"Error stopping yaw control: {str(e)}")


class ChairBehaviourTree:
    """Main behaviour tree class for the HappyChair system."""
    
    def __init__(self, animation_controller, yaw_controller, camera_controller, io_controller):
        # Store controller references
        self.animation_controller = animation_controller
        self.yaw_controller = yaw_controller
        self.camera_controller = camera_controller
        self.io_controller = io_controller
        
        # Create blackboard for shared data between behaviours
        self.blackboard = blackboard.Client(name="ChairBehaviourTree")
        
        # Build the behavior tree
        self.root = self._create_tree()
        
        # Create the BehaviourTree wrapper
        self.tree = py_trees.trees.BehaviourTree(root=self.root)
        
        # Add visitors for monitoring
        self.snapshot_visitor = py_trees.visitors.SnapshotVisitor()
        self.tree.visitors.append(self.snapshot_visitor)
        
        # Tree execution control
        self.tree_running = False
        self.tree_thread = None
        self._stop_event = threading.Event()
        
        print("ChairBehaviourTree initialized")
        
    def _create_tree(self):
        """Create the basic behaviour tree structure."""
        # Create root selector - chooses between different high-level behaviors
        root = composites.Parallel(name="Chair Root", policy=py_trees.common.ParallelPolicy.SuccessOnOne())
        # root = composites.Selector(name="Chair Root", memory=False)
        
        # # Add basic idle behavior as fallback
        # idle_sequence = composites.Sequence(name="Idle Sequence", memory=True)
        # idle_sequence.add_children([
        #     behaviours.Success(name="Idle Success")
        # ])
        
        # root.add_child(idle_sequence)
        
        # Test basic sensor blackboard reads
        seat_sensor_check = SeatSensorCheck(
            name="Seat Sensor Check",
            pin=14,  # Example GPIO pin for seat sensor
            io_controller=self.io_controller
        )
        
        person_detection_check = PersonDetectionCheck(
            name="Person Detection Check",
            camera_controller=self.camera_controller
        )

        root.add_children([
            seat_sensor_check,
            person_detection_check
        ])
        
        return root
    
    def _find_behaviour_by_id(self, behaviour_id: uuid.UUID):
        """Find a behaviour in the tree by its UUID."""
        for behaviour in self.root.iterate():
            if behaviour.id == behaviour_id:
                return behaviour
        return None
    
    def start(self) -> bool:
        """Start the behaviour tree execution."""
        if self.tree_running:
            print("ChairBehaviourTree: Tree is already running")
            return False
            
        try:
            # Monkey-patch signal.signal to avoid thread issues (similar to persondetection.py)
            import signal
            original_signal = signal.signal
            
            def thread_safe_signal(signum, handler):
                # Only set signal handlers if we're in the main thread
                try:
                    return original_signal(signum, handler)
                except ValueError as e:
                    if "main thread" in str(e):
                        print(f"ChairBehaviourTree: Skipping signal handler setup in thread: {e}")
                        return None
                    else:
                        raise
            
            # Temporarily replace signal.signal
            signal.signal = thread_safe_signal
            
            try:
                # Setup the tree
                self.tree.setup(timeout=15)
                
                # Start the tree execution thread
                self._stop_event.clear()
                self.tree_running = True
                self.tree_thread = threading.Thread(target=self._tree_execution_loop, daemon=True)
                self.tree_thread.start()
                
                print("ChairBehaviourTree: Started successfully")
                return True
            finally:
                # Restore original signal function
                signal.signal = original_signal
                
        except Exception as e:
            print(f"ChairBehaviourTree: Error starting tree: {e}")
            self.tree_running = False
            return False
    
    def stop(self):
        """Stop the behaviour tree execution."""
        if not self.tree_running:
            print("ChairBehaviourTree: Tree is not running")
            return
            
        print("ChairBehaviourTree: Stopping...")
        self.tree_running = False
        self._stop_event.set()
        
        if self.tree_thread and self.tree_thread.is_alive():
            self.tree_thread.join(timeout=2.0)
        
        print("ChairBehaviourTree: Stopped")
    
    def _tree_execution_loop(self):
        """Main execution loop for the behaviour tree."""
        try:
            while self.tree_running and not self._stop_event.is_set():
                # Tick the tree using the BehaviourTree wrapper
                self.tree.tick()
                
                # Sleep for a short period (10Hz tick rate)
                time.sleep(0.1)
                
        except Exception as e:
            print(f"ChairBehaviourTree: Error in execution loop: {e}")
        finally:
            self.tree_running = False
    
    def get_tree_status(self) -> Dict[str, Any]:
        """Get current tree state for visualization."""
        if not self.snapshot_visitor:
            return {'nodes': [], 'currently_running': [], 'changed': False, 'tree_running': False}
        
        nodes = []
        for behaviour_id, status in self.snapshot_visitor.visited.items():
            # Find the behaviour by ID
            behaviour = self._find_behaviour_by_id(behaviour_id)
            if behaviour:
                nodes.append({
                    'id': str(behaviour_id),
                    'name': behaviour.name,
                    'status': status.value,
                    'type': type(behaviour).__name__,
                    'feedback': getattr(behaviour, 'feedback_message', '')
                })
        
        return {
            'nodes': nodes,
            'currently_running': [str(bid) for bid in getattr(self.snapshot_visitor, 'running_nodes', [])],
            'changed': getattr(self.snapshot_visitor, 'changed', False),
            'tree_running': self.tree_running
        }
    
    def generate_ascii_graph(self) -> str:
        """Generate dot graph representation using py_trees utilities."""
        try:
            return py_trees.display.unicode_tree(self.root)
        except Exception as e:
            print(f"ChairBehaviourTree: Error generating dot graph: {e}")
            return ""
    
    def get_blackboard_data(self) -> Dict[str, Any]:
        """Get current blackboard data."""
        try:
            return {
                'person_detected': getattr(self.blackboard, 'person_detected', False),
                'seat_occupied': getattr(self.blackboard, 'seat_occupied', False),
                'current_animation': getattr(self.blackboard, 'current_animation', None),
                'person_count': getattr(self.blackboard, 'person_count', 0),
                'tracked_person_info': getattr(self.blackboard, 'tracked_person_info', None),
                'movement_direction': getattr(self.blackboard, 'movement_direction', None),
                'normalized_speed': getattr(self.blackboard, 'normalized_speed', None),
                'seat_occupied': getattr(self.blackboard, 'seat_occupied', False)
            }
        except Exception as e:
            print(f"ChairBehaviourTree: Error getting blackboard data: {e}")
            return {}
    
    def is_running(self) -> bool:
        """Check if the behaviour tree is currently running."""
        return self.tree_running
    
    def shutdown(self):
        """Shutdown the behaviour tree and cleanup resources."""
        self.stop()
        print("ChairBehaviourTree: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.shutdown()
