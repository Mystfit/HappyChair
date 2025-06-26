#!/usr/bin/env python3
"""
Simple test script to verify PersonDetection class works
Run this to test the camera detection before running the full Flask server
"""

import sys
import time
from persondetection import PersonDetection

def test_person_detection():
    """Test PersonDetection class functionality"""
    print("Testing PersonDetection class...")
    print("Make sure you have sourced setup_env.sh before running this!")
    print("=" * 50)
    
    # Create detector instance
    detector = PersonDetection()
    
    try:
        # Start detection
        print("Starting person detection...")
        if detector.start_detection():
            print("✓ Detection started successfully")
        else:
            print("✗ Failed to start detection")
            return False
        
        # Monitor for 30 seconds
        print("Monitoring detection for 30 seconds...")
        print("Press Ctrl+C to stop early")
        
        start_time = time.time()
        while time.time() - start_time < 30:
            if not detector.is_running():
                print("✗ Detection stopped unexpectedly")
                break
                
            # Get current stats
            stats = detector.get_detection_stats()
            frame = detector.get_latest_frame()
            
            # Print status every 2 seconds
            if int(time.time() - start_time) % 2 == 0:
                print(f"Time: {int(time.time() - start_time)}s | "
                      f"Persons: {stats['person_count']} | "
                      f"Total: {stats['total_detections']} | "
                      f"FPS: {stats['fps']:.1f} | "
                      f"Frame: {'✓' if frame is not None else '✗'}")
            
            time.sleep(0.5)
        
        print("\n" + "=" * 50)
        print("Final Statistics:")
        final_stats = detector.get_detection_stats()
        for key, value in final_stats.items():
            if key == 'fps':
                print(f"  {key}: {value:.2f}")
            elif key == 'last_update':
                if value > 0:
                    print(f"  {key}: {time.ctime(value)}")
                else:
                    print(f"  {key}: Never")
            else:
                print(f"  {key}: {value}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return True
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        return False
    finally:
        # Clean shutdown
        print("\nStopping detection...")
        if detector.stop_detection():
            print("✓ Detection stopped successfully")
        else:
            print("✗ Failed to stop detection cleanly")

if __name__ == "__main__":
    print("PersonDetection Test Script")
    print("=" * 50)
    print("This script tests the PersonDetection class independently")
    print("Make sure to run: source setup_env.sh")
    print("Before running this script!")
    print()
    
    # Check if user wants to continue
    try:
        input("Press Enter to start test (Ctrl+C to cancel)...")
    except KeyboardInterrupt:
        print("\nTest cancelled")
        sys.exit(0)
    
    # Run test
    success = test_person_detection()
    
    if success:
        print("\n✓ Test completed successfully!")
        print("You can now run the full Flask server with:")
        print("  source setup_env.sh && python anim_webapp.py")
    else:
        print("\n✗ Test failed!")
        print("Please check your setup and try again")
        sys.exit(1)
