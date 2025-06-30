#!/usr/bin/env python3
"""
Test script for the multiprocessing detection system.
This script can be used to verify that the detection works correctly
before integrating with the web server.
"""

import time
import sys
import signal
from detection_multiprocess import PersonDetectionMultiprocess

def signal_handler(signum, frame):
    print("\nReceived interrupt signal, shutting down...")
    sys.exit(0)

def main():
    print("=== Multiprocessing Person Detection Test ===")
    print("This test will run the detection system for 60 seconds")
    print("Press Ctrl+C to stop early\n")
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create detector instance
    detector = PersonDetectionMultiprocess("test_detection_buffer")
    
    try:
        # Start detection
        print("Starting detection process...")
        if not detector.start_detection():
            print("ERROR: Failed to start detection process")
            return 1
        
        print("Detection started successfully!")
        print(f"Process info: {detector.get_process_info()}")
        print("\nMonitoring detection for 60 seconds...")
        print("=" * 60)
        
        start_time = time.time()
        last_stats_time = time.time()
        
        while time.time() - start_time < 60:
            # Check if detection is still running
            if not detector.is_running():
                print("ERROR: Detection process stopped unexpectedly")
                break
            
            # Get and display stats every 2 seconds
            current_time = time.time()
            if current_time - last_stats_time >= 2.0:
                stats = detector.get_detection_stats()
                
                print(f"Time: {current_time - start_time:6.1f}s | "
                      f"Persons: {stats['person_count']:2d} | "
                      f"Detection FPS: {stats['fps']:5.1f} | "
                      f"Buffer FPS: {stats.get('buffer_fps', 0):5.1f} | "
                      f"Total: {stats['total_detections']:4d}")
                
                # Test frame retrieval
                frame = detector.get_latest_frame()
                if frame is not None:
                    print(f"                    Frame shape: {frame.shape} | "
                          f"Buffer frames: {stats.get('buffer_frames', 0)}")
                else:
                    print("                    No frame available")
                
                last_stats_time = current_time
            
            time.sleep(0.1)
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        
        # Final stats
        final_stats = detector.get_detection_stats()
        print(f"\nFinal Statistics:")
        print(f"  Total detections: {final_stats['total_detections']}")
        print(f"  Average FPS: {final_stats['fps']:.1f}")
        print(f"  Buffer FPS: {final_stats.get('buffer_fps', 0):.1f}")
        print(f"  Process info: {detector.get_process_info()}")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    
    except Exception as e:
        print(f"\nERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        print("\nStopping detection process...")
        detector.stop_detection()
        print("Test cleanup completed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
