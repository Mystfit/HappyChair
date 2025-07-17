"""
Generic base class for animatronic behaviour trees.
"""

import py_trees
from py_trees import common, composites, behaviours, decorators, blackboard
import threading
import time
from typing import Dict, Any, Optional, List
import uuid
import signal

from .animation_action import AnimationAction
from .sensor_check import SensorCheck, PersonDetectionCheck
from .tracking_action import TrackingAction


class AnimatronicBehaviourTree:
    """Generic base class for animatronic behaviour trees."""
    
    def __init__(self, animation_controller, tracking_controller, camera_controller, io_controller):
        # Store controller references
        self.animation_controller = animation_controller
        self.tracking_controller = tracking_controller
        self.camera_controller = camera_controller
        self.io_controller = io_controller
        
        # Callbacks
        self.last_executed_ascii_graph = None
        
        # Build the behavior tree
        self.root = self._create_tree()
        
        # Create the BehaviourTree wrapper
        self.tree = py_trees.trees.BehaviourTree(root=self.root)
        
        # Create blackboard for shared data between behaviours
        self.blackboard = blackboard.Client(name="AnimatronicBehaviourTree")
        self._register_blackboard_keys()
        
        # Add visitors for monitoring
        self.snapshot_visitor = py_trees.visitors.SnapshotVisitor()
        self.tree.visitors.append(self.snapshot_visitor)
        
        # Tree execution control
        self.tree_running = False
        self.tree_thread = None
        self._stop_event = threading.Event()
        
        print("AnimatronicBehaviourTree initialized")
        
    def _register_blackboard_keys(self):
        """Register common blackboard keys. Override to add specific keys."""
        keys = [
            "person_detected", "person_count", "tracked_person_info",
            "movement_direction", "normalized_speed", "current_animation", "can_scan"
        ]
        for key in keys:
            self.blackboard.register_key(key=key, access=common.Access.READ)
    
    def _create_tree(self):
        """Create the basic behaviour tree structure. Override in subclasses."""
        # Create root sequence - sensors populate blackboard, then tasks execute
        root = composites.Sequence(name="Root", memory=False)

        # Create child nodes for different behaviors
        sensor_populate_node = self._create_sensor_tree()
        tasks_node = self._create_tasks_tree()
        idle_node = self._create_idle_tree()

        # Add basic structure
        root.add_children([
            sensor_populate_node,
            tasks_node,
            idle_node
        ])
                     
        return root
    
    def _create_sensor_tree(self):
        """Create sensor monitoring tree. Override to add specific sensors."""
        sensor_root = composites.Parallel(name="Sensors", policy=py_trees.common.ParallelPolicy.SuccessOnAll())

        # Add person detection check
        person_detection_check = PersonDetectionCheck(
            name="Person Detection Check",
            camera_controller=self.camera_controller
        )
        
        sensor_root.add_children([
            person_detection_check
        ])
        
        return sensor_root

    def _create_tasks_tree(self):
        """Create main tasks tree. Override in subclasses for specific behaviors."""
        # Default implementation - just a placeholder
        tasks_selector = composites.Selector(name="Tasks", memory=True)
        tasks_selector.add_children([
            behaviours.Success(name="Default Task")
        ])
        return tasks_selector

    def _create_idle_tree(self):
        """Create idle behavior tree."""
        idle_sequence = composites.Sequence(name="Idle Sequence", memory=True)
        idle_sequence.add_children([
            behaviours.Success(name="Idle Success")
        ])
        return idle_sequence
    
    def _find_behaviour_by_id(self, behaviour_id: uuid.UUID):
        """Find a behaviour in the tree by its UUID."""
        for behaviour in self.root.iterate():
            if behaviour.id == behaviour_id:
                return behaviour
        return None
    
    def start(self) -> bool:
        """Start the behaviour tree execution."""
        if self.tree_running:
            print("AnimatronicBehaviourTree: Tree is already running")
            return False
            
        try:
            # Monkey-patch signal.signal to avoid thread issues
            original_signal = signal.signal
            
            def thread_safe_signal(signum, handler):
                # Only set signal handlers if we're in the main thread
                try:
                    return original_signal(signum, handler)
                except ValueError as e:
                    if "main thread" in str(e):
                        print(f"AnimatronicBehaviourTree: Skipping signal handler setup in thread: {e}")
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
                
                print("AnimatronicBehaviourTree: Started successfully")
                return True
            finally:
                # Restore original signal function
                signal.signal = original_signal
                
        except Exception as e:
            print(f"AnimatronicBehaviourTree: Error starting tree: {e}")
            self.tree_running = False
            return False
    
    def stop(self):
        """Stop the behaviour tree execution."""
        if not self.tree_running:
            print("AnimatronicBehaviourTree: Tree is not running")
            return
            
        print("AnimatronicBehaviourTree: Stopping...")
        self.tree_running = False
        self._stop_event.set()
        
        if self.tree_thread and self.tree_thread.is_alive():
            self.tree_thread.join(timeout=2.0)
        
        print("AnimatronicBehaviourTree: Stopped")
    
    def _tree_execution_loop(self):
        """Main execution loop for the behaviour tree."""
        try:
            while self.tree_running and not self._stop_event.is_set():
                # Tick the tree using the BehaviourTree wrapper
                self.tree.tick()
                self.last_executed_ascii_graph = self.generate_ascii_graph()
                                    
                # Sleep for a short period (10Hz tick rate)
                time.sleep(0.1)
                
        except Exception as e:
            print(f"AnimatronicBehaviourTree: Error in execution loop: {e}")
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
            return py_trees.display.unicode_tree(self.root, show_status=True)
        except Exception as e:
            print(f"AnimatronicBehaviourTree: Error generating dot graph: {e}")
            return ""
    
    def get_blackboard_data(self) -> Dict[str, Any]:
        """Get current blackboard data."""
        try:
            return {
                'person_detected': self.blackboard.person_detected if self.blackboard.exists('person_detected') else False,
                'current_animation': self.blackboard.current_animation if self.blackboard.exists('current_animation') else None,
                'person_count': self.blackboard.person_count if self.blackboard.exists('person_count') else 0,
                'tracked_person_info': self.blackboard.tracked_person_info if self.blackboard.exists('tracked_person_info') else None,
                'movement_direction': self.blackboard.movement_direction if self.blackboard.exists('movement_direction') else None,
                'normalized_speed': self.blackboard.normalized_speed if self.blackboard.exists('normalized_speed') else None,
            }
        except Exception as e:
            print(f"AnimatronicBehaviourTree: Error getting blackboard data: {e}")
            return {}
    
    def is_running(self) -> bool:
        """Check if the behaviour tree is currently running."""
        return self.tree_running
    
    def shutdown(self):
        """Shutdown the behaviour tree and cleanup resources."""
        self.stop()
        print("AnimatronicBehaviourTree: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.shutdown()