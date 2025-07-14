"""
CameraController class for managing camera detection and person tracking operations.
Handles camera detection, person tracking statistics, and event dispatching.
"""

import threading
import time
from typing import Optional, Dict, Any, List, Callable
from detection_multiprocess import PersonDetectionMultiprocess


class CameraController:
    """
    Controls camera detection and person tracking operations.
    Dispatches events to registered callbacks for decoupled system architecture.
    """
    
    def __init__(self, buffer_name: str = "happychair_detection_buffer"):
        self.buffer_name = buffer_name
        
        # Detection system
        self.person_detector = None
        
        # Event system
        self.event_callbacks = []  # List of callback functions
        
        # Statistics
        self.unique_people_seen = set()
        
        print("CameraController initialized")
    
    def register_event_callback(self, callback: Callable):
        """Register a callback function for events"""
        if callback not in self.event_callbacks:
            self.event_callbacks.append(callback)
            print(f"CameraController: Registered event callback: {callback.__name__}")
    
    def unregister_event_callback(self, callback: Callable):
        """Unregister a callback function"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
            print(f"CameraController: Unregistered event callback: {callback.__name__}")
    
    def dispatch_event(self, event_type: str, data: Dict[str, Any]):
        """Dispatch an event to all registered callbacks"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        }
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"CameraController: Error in event callback {callback.__name__}: {e}")
    
    def start_detection(self) -> bool:
        """Start the person detection system"""
        try:
            if not self.person_detector:
                self.person_detector = PersonDetectionMultiprocess(self.buffer_name)
            
            if self.person_detector.start_detection():
                print("CameraController: Detection started successfully")
                return True
            else:
                print("CameraController: Failed to start detection")
                return False
                
        except Exception as e:
            print(f"CameraController: Error starting detection: {e}")
            return False
    
    def stop_detection(self) -> bool:
        """Stop the person detection system"""
        try:
            if self.person_detector and self.person_detector.stop_detection():
                print("CameraController: Detection stopped successfully")
                return True
            else:
                print("CameraController: Failed to stop detection or not running")
                return False
                
        except Exception as e:
            print(f"CameraController: Error stopping detection: {e}")
            return False
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        if not self.person_detector:
            return {
                'person_count': 0,
                'unique_people': 0,
                'last_update': 0,
                'fps': 0,
                'detections': []
            }
        
        # Get base stats from detector
        stats = self.person_detector.get_detection_stats()
        
        # Update unique people count
        detections = stats.get('detections', [])
        for detection in detections:
            track_id = detection.get('track_id', 0)
            if track_id > 0:
                self.unique_people_seen.add(track_id)
        
        # Add CameraController specific stats
        stats.update({
            'unique_people': len(self.unique_people_seen)
        })
        
        # Dispatch detection event if there are detections
        if detections:
            event_data = {
                'detections': detections,
                'person_count': stats.get('person_count', 0),
                'unique_people': len(self.unique_people_seen)
            }
            
            # Include movement parameters if available
            if 'movement_direction' in stats:
                event_data['movement_direction'] = stats['movement_direction']
            if 'normalized_speed' in stats:
                event_data['normalized_speed'] = stats['normalized_speed']
            if 'tracked_person_id' in stats:
                event_data['tracked_person_id'] = stats['tracked_person_id']
            
            self.dispatch_event('person_detected', event_data)
        
        return stats
    
    def get_latest_frame(self):
        """Get the latest frame from detection system"""
        if self.person_detector:
            return self.person_detector.get_latest_frame()
        return None
    
    def is_detection_running(self) -> bool:
        """Check if detection is running"""
        if self.person_detector:
            return self.person_detector.is_running()
        return False
    
    def restart_detection(self) -> bool:
        """Restart the detection system"""
        if self.person_detector:
            return self.person_detector.restart_detection()
        return False
    
    def get_process_info(self) -> Dict:
        """Get detection process information"""
        if self.person_detector:
            return self.person_detector.get_process_info()
        return {'status': 'not_initialized'}
    
    def shutdown(self):
        """Shutdown the CameraController and cleanup resources"""
        print("CameraController: Shutting down...")
        
        # Stop detection
        if self.person_detector:
            self.person_detector.shutdown()
        
        print("CameraController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()
