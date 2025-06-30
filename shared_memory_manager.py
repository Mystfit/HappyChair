import struct
import time
import threading
from typing import Optional, Tuple
import numpy as np
from multiprocessing import shared_memory

class SharedFrameBuffer:
    """
    Manages a circular buffer in shared memory for video frames.
    Uses multiprocessing.shared_memory for cross-platform compatibility.
    """
    
    def __init__(self, buffer_name: str, frame_width: int = 1280, frame_height: int = 720, 
                 channels: int = 3, buffer_size: int = 4):
        self.buffer_name = buffer_name
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.channels = channels
        self.buffer_size = buffer_size
        
        # Calculate frame size in bytes
        self.frame_bytes = frame_width * frame_height * channels
        
        # Header structure: write_index(4), read_index(4), frame_count(4), timestamps(8*buffer_size)
        self.header_size = 12 + (8 * buffer_size)  # 4 + 4 + 4 + timestamps
        
        # Total memory needed
        self.total_size = self.header_size + (self.frame_bytes * buffer_size)
        
        self.shm = None
        self.lock = threading.Lock()
        
    def create_buffer(self) -> bool:
        """Create the shared memory buffer (called by producer/detection process)"""
        try:
            # Create shared memory block
            self.shm = shared_memory.SharedMemory(
                name=self.buffer_name, 
                create=True, 
                size=self.total_size
            )
            
            # Initialize header
            self._write_header(0, 0, 0, [0.0] * self.buffer_size)
            
            print(f"Created shared frame buffer: {self.buffer_name} ({self.total_size} bytes)")
            return True
            
        except Exception as e:
            print(f"Failed to create shared buffer: {e}")
            return False
    
    def connect_buffer(self) -> bool:
        """Connect to existing shared memory buffer (called by consumer/web server process)"""
        try:
            # Connect to existing shared memory block
            self.shm = shared_memory.SharedMemory(name=self.buffer_name)
            print(f"Connected to shared frame buffer: {self.buffer_name}")
            return True
            
        except Exception as e:
            print(f"Failed to connect to shared buffer: {e}")
            return False
    
    def write_frame(self, frame: np.ndarray) -> bool:
        """Write a frame to the buffer (producer/detection process)"""
        if self.shm is None:
            return False
            
        try:
            with self.lock:
                # Read current header
                write_idx, read_idx, frame_count, timestamps = self._read_header()
                
                # Calculate next write position
                next_write_idx = (write_idx + 1) % self.buffer_size
                
                # Write frame data
                frame_offset = self.header_size + (write_idx * self.frame_bytes)
                frame_bytes = frame.tobytes()
                
                if len(frame_bytes) != self.frame_bytes:
                    print(f"Frame size mismatch: expected {self.frame_bytes}, got {len(frame_bytes)}")
                    return False
                
                self.shm.buf[frame_offset:frame_offset + self.frame_bytes] = frame_bytes
                
                # Update timestamps
                timestamps[write_idx] = time.time()
                
                # Update header
                self._write_header(next_write_idx, read_idx, frame_count + 1, timestamps)
                
                return True
                
        except Exception as e:
            print(f"Error writing frame: {e}")
            return False
    
    def read_latest_frame(self) -> Optional[Tuple[np.ndarray, float]]:
        """Read the most recent frame from buffer (consumer/web server process)"""
        if self.shm is None:
            return None
            
        try:
            with self.lock:
                # Read current header
                write_idx, read_idx, frame_count, timestamps = self._read_header()
                
                if frame_count == 0:
                    return None
                
                # Get the most recent frame (one before write_idx)
                latest_idx = (write_idx - 1) % self.buffer_size
                
                # Read frame data
                frame_offset = self.header_size + (latest_idx * self.frame_bytes)
                frame_bytes = self.shm.buf[frame_offset:frame_offset + self.frame_bytes]
                
                # Convert back to numpy array
                frame = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = frame.reshape((self.frame_height, self.frame_width, self.channels))
                
                # Get timestamp
                timestamp = timestamps[latest_idx]
                
                return frame.copy(), timestamp
                
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Get buffer statistics"""
        if self.shm is None:
            return {}
            
        try:
            write_idx, read_idx, frame_count, timestamps = self._read_header()
            
            # Calculate FPS from recent timestamps
            current_time = time.time()
            recent_timestamps = [t for t in timestamps if current_time - t < 2.0 and t > 0]
            
            fps = 0.0
            if len(recent_timestamps) > 1:
                time_span = max(recent_timestamps) - min(recent_timestamps)
                if time_span > 0:
                    fps = (len(recent_timestamps) - 1) / time_span
            
            return {
                'write_index': write_idx,
                'read_index': read_idx,
                'frame_count': frame_count,
                'buffer_size': self.buffer_size,
                'fps': fps,
                'recent_frames': len(recent_timestamps)
            }
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}
    
    def _read_header(self) -> Tuple[int, int, int, list]:
        """Read header information from shared memory"""
        header_data = self.shm.buf[:self.header_size]
        
        # Unpack header
        write_idx = struct.unpack('I', header_data[0:4])[0]
        read_idx = struct.unpack('I', header_data[4:8])[0]
        frame_count = struct.unpack('I', header_data[8:12])[0]
        
        # Unpack timestamps
        timestamps = []
        for i in range(self.buffer_size):
            offset = 12 + (i * 8)
            timestamp = struct.unpack('d', header_data[offset:offset + 8])[0]
            timestamps.append(timestamp)
        
        return write_idx, read_idx, frame_count, timestamps
    
    def _write_header(self, write_idx: int, read_idx: int, frame_count: int, timestamps: list):
        """Write header information to shared memory"""
        header_data = bytearray(self.header_size)
        
        # Pack header
        struct.pack_into('I', header_data, 0, write_idx)
        struct.pack_into('I', header_data, 4, read_idx)
        struct.pack_into('I', header_data, 8, frame_count)
        
        # Pack timestamps
        for i, timestamp in enumerate(timestamps):
            offset = 12 + (i * 8)
            struct.pack_into('d', header_data, offset, timestamp)
        
        # Write to shared memory
        self.shm.buf[:self.header_size] = header_data
    
    def close(self):
        """Close the shared memory buffer"""
        if self.shm:
            try:
                self.shm.close()
            except:
                pass
            self.shm = None
    
    def unlink(self):
        """Unlink/delete the shared memory buffer (call from creator process)"""
        if self.shm:
            try:
                self.shm.unlink()
            except:
                pass
    
    def __del__(self):
        self.close()


class DetectionResultsQueue:
    """
    Simple wrapper around multiprocessing queue for detection results.
    Handles serialization of detection data between processes.
    """
    
    def __init__(self, queue):
        self.queue = queue
    
    def put_detection_results(self, person_count: int, detections: list, fps: float):
        """Put detection results in queue"""
        try:
            result = {
                'timestamp': time.time(),
                'person_count': person_count,
                'detections': detections,  # List of {'bbox': (x,y,w,h), 'confidence': float, 'track_id': int}
                'fps': fps
            }
            
            # Non-blocking put, drop old results if queue is full
            try:
                self.queue.put_nowait(result)
            except:
                # Queue full, remove old result and add new one
                try:
                    self.queue.get_nowait()
                    self.queue.put_nowait(result)
                except:
                    pass  # Queue operations failed, skip this update
                    
        except Exception as e:
            print(f"Error putting detection results: {e}")
    
    def get_latest_results(self) -> Optional[dict]:
        """Get the most recent detection results (non-blocking)"""
        latest_result = None
        
        try:
            # Get all available results, keeping only the latest
            while True:
                try:
                    latest_result = self.queue.get_nowait()
                except:
                    break
                    
        except Exception as e:
            print(f"Error getting detection results: {e}")
        
        return latest_result
