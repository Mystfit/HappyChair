"""
Multiprocessing-based PersonDetection class.
Manages detection process and shared memory communication.
"""

import multiprocessing
import time
import os
import signal
from typing import Optional, Tuple
import numpy as np

from shared_memory_manager import SharedFrameBuffer, DetectionResultsQueue
from detection_process import run_detection_process


class PersonDetectionMultiprocess:
    """
    PersonDetection class using multiprocessing for high-performance detection.
    Eliminates GIL contention by running detection in a separate process.
    """
    
    def __init__(self, buffer_name: str = "person_detection_buffer"):
        self.buffer_name = buffer_name
        self.detection_process = None
        self.results_queue = None
        self.stop_event = None
        self.shared_buffer = None
        self.running = False
        
        # Detection statistics
        self.detection_stats = {
            'person_count': 0,
            'total_detections': 0,
            'last_update': time.time(),
            'fps': 0,
            'detections': []  # List of current detections with bounding boxes
        }
        
        # Performance monitoring
        self.last_frame_time = time.time()
        self.frame_count = 0
        
    def start_detection(self) -> bool:
        """Start the detection process"""
        if self.running:
            print("Detection is already running")
            return False
        
        try:
            print("Starting multiprocess person detection...")
            
            # Create multiprocessing components
            self.results_queue = multiprocessing.Queue(maxsize=10)
            self.stop_event = multiprocessing.Event()
            
            # Create shared memory buffer (consumer side)
            self.shared_buffer = SharedFrameBuffer(self.buffer_name)
            
            # Start detection process
            self.detection_process = multiprocessing.Process(
                target=run_detection_process,
                args=(self.buffer_name, self.results_queue, self.stop_event),
                name="PersonDetectionProcess"
            )
            
            self.detection_process.start()
            
            # Wait a moment for the process to initialize
            time.sleep(1.0)
            
            # Connect to shared memory buffer
            if not self.shared_buffer.connect_buffer():
                print("Failed to connect to shared memory buffer")
                self.stop_detection()
                return False
            
            self.running = True
            print(f"Detection process started (PID: {self.detection_process.pid})")
            return True
            
        except Exception as e:
            print(f"Failed to start detection process: {e}")
            self.stop_detection()
            return False
    
    def stop_detection(self) -> bool:
        """Stop the detection process"""
        if not self.running:
            print("Detection is not running")
            return False
        
        try:
            print("Stopping detection process...")
            self.running = False
            
            # Signal the process to stop
            if self.stop_event:
                self.stop_event.set()
            
            # Wait for process to terminate
            if self.detection_process and self.detection_process.is_alive():
                self.detection_process.join(timeout=5.0)
                
                # Force terminate if still alive
                if self.detection_process.is_alive():
                    print("Force terminating detection process...")
                    self.detection_process.terminate()
                    self.detection_process.join(timeout=2.0)
                    
                    # Kill if still alive
                    if self.detection_process.is_alive():
                        print("Force killing detection process...")
                        os.kill(self.detection_process.pid, signal.SIGKILL)
                        self.detection_process.join()
            
            # Clean up resources
            if self.shared_buffer:
                self.shared_buffer.close()
                # Note: Don't unlink here as we're the consumer, not creator
                self.shared_buffer = None
            
            if self.results_queue:
                # Clear any remaining items
                while not self.results_queue.empty():
                    try:
                        self.results_queue.get_nowait()
                    except:
                        break
                self.results_queue = None
            
            self.detection_process = None
            self.stop_event = None
            
            print("Detection process stopped")
            return True
            
        except Exception as e:
            print(f"Error stopping detection process: {e}")
            return False
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get the most recent frame from shared memory"""
        if not self.running or not self.shared_buffer:
            return None
        
        try:
            result = self.shared_buffer.read_latest_frame()
            if result:
                frame, timestamp = result
                return frame
            return None
            
        except Exception as e:
            print(f"Error reading frame from shared memory: {e}")
            return None
    
    def get_detection_stats(self) -> dict:
        """Get current detection statistics"""
        if not self.running:
            return {
                'person_count': 0,
                'total_detections': 0,
                'last_update': 0,
                'fps': 0,
                'detections': []
            }
        
        # Update stats from results queue
        self._update_stats_from_queue()
        
        # Add buffer statistics
        stats = self.detection_stats.copy()
        if self.shared_buffer:
            buffer_stats = self.shared_buffer.get_stats()
            stats.update({
                'buffer_fps': buffer_stats.get('fps', 0),
                'buffer_frames': buffer_stats.get('frame_count', 0),
                'shared_memory_stats': buffer_stats
            })
        
        return stats
    
    def _update_stats_from_queue(self):
        """Update detection statistics from the results queue"""
        if not self.results_queue:
            return
        
        # Get latest detection results
        results_queue_wrapper = DetectionResultsQueue(self.results_queue)
        latest_results = results_queue_wrapper.get_latest_results()
        
        if latest_results:
            self.detection_stats.update({
                'person_count': latest_results['person_count'],
                'total_detections': self.detection_stats['total_detections'] + latest_results['person_count'],
                'last_update': latest_results['timestamp'],
                'fps': latest_results['fps'],
                'detections': latest_results['detections']
            })
    
    def is_running(self) -> bool:
        """Check if detection is currently running"""
        if not self.running:
            return False
        
        # Check if process is still alive
        if self.detection_process and not self.detection_process.is_alive():
            print("Detection process died unexpectedly")
            self.running = False
            return False
        
        return True
    
    def get_process_info(self) -> dict:
        """Get information about the detection process"""
        if not self.detection_process:
            return {'status': 'not_started'}
        
        return {
            'status': 'running' if self.detection_process.is_alive() else 'stopped',
            'pid': self.detection_process.pid if self.detection_process.is_alive() else None,
            'name': self.detection_process.name,
            'shared_buffer_name': self.buffer_name
        }
    
    def restart_detection(self) -> bool:
        """Restart the detection process"""
        print("Restarting detection process...")
        
        if self.is_running():
            if not self.stop_detection():
                return False
        
        # Wait a moment before restarting
        time.sleep(1.0)
        
        return self.start_detection()
    
    def get_frame_with_detections(self) -> Optional[Tuple[np.ndarray, list]]:
        """Get the latest frame along with detection information"""
        frame = self.get_latest_frame()
        stats = self.get_detection_stats()
        
        if frame is not None:
            return frame, stats.get('detections', [])
        
        return None
    
    def shutdown(self, signum=None, frame=None):
        """Shutdown handler for graceful cleanup"""
        print("PersonDetectionMultiprocess shutting down...")
        self.stop_detection()
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        if self.running:
            self.stop_detection()


# Compatibility function for easy migration
def create_person_detector(use_multiprocessing: bool = True, buffer_name: str = "person_detection_buffer"):
    """
    Factory function to create a PersonDetection instance.
    
    Args:
        use_multiprocessing: If True, use multiprocessing version (recommended)
        buffer_name: Name for shared memory buffer
    
    Returns:
        PersonDetection instance
    """
    if use_multiprocessing:
        return PersonDetectionMultiprocess(buffer_name)
    else:
        # Fallback to original threading version
        from persondetection import PersonDetection
        return PersonDetection()


# Test function
def test_multiprocess_detection():
    """Test function for the multiprocessing detection"""
    detector = PersonDetectionMultiprocess("test_buffer")
    
    try:
        print("Starting multiprocess detection test...")
        
        if not detector.start_detection():
            print("Failed to start detection")
            return
        
        print("Detection started successfully")
        
        # Monitor for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            if not detector.is_running():
                print("Detection stopped unexpectedly")
                break
            
            # Get stats
            stats = detector.get_detection_stats()
            print(f"Stats: Persons={stats['person_count']}, FPS={stats['fps']:.1f}, "
                  f"Buffer FPS={stats.get('buffer_fps', 0):.1f}")
            
            # Get frame
            frame = detector.get_latest_frame()
            if frame is not None:
                print(f"Got frame: {frame.shape}")
            
            time.sleep(2)
        
    except KeyboardInterrupt:
        print("Test interrupted")
    
    finally:
        print("Stopping detection...")
        detector.stop_detection()
        print("Test completed")


if __name__ == "__main__":
    test_multiprocess_detection()
