#!/usr/bin/env python3
"""
Test script for MotorKit stepper driver with multiprocess architecture.
Tests the new MotorKitStepperProxy implementation.
"""

import time
import sys
from motor_drivers import MotorKitStepperProxy


def test_basic_functionality():
    """Test basic stepper motor functionality"""
    print("=== Testing MotorKit Stepper Driver ===")
    
    # Initialize driver
    driver = MotorKitStepperProxy()
    
    try:
        # Start the driver
        print("\n1. Starting driver...")
        if not driver.start():
            print("ERROR: Failed to start driver")
            return False
        
        print("Driver started successfully")
        print(f"Driver enabled: {driver.is_enabled()}")
        
        # Test forward movement
        print("\n2. Testing forward movement...")
        driver.set_speed("forward", 0.3)  # 30% speed
        time.sleep(3)
        
        # Test speed change
        print("\n3. Testing speed change...")
        driver.set_speed("forward", 0.6)  # 60% speed
        time.sleep(2)
        
        # Test reverse movement
        print("\n4. Testing reverse movement...")
        driver.set_speed("reverse", 0.4)  # 40% speed
        time.sleep(3)
        
        # Test stopping
        print("\n5. Testing stop...")
        driver.set_speed("stopped", 0.0)
        time.sleep(1)
        
        # Test smooth transitions
        print("\n6. Testing smooth transitions...")
        driver.set_speed("forward", 0.8, duration=2.0)  # Smooth acceleration over 2 seconds
        time.sleep(3)
        
        driver.set_speed("stopped", 0.0, duration=1.5)  # Smooth deceleration over 1.5 seconds
        time.sleep(2)
        
        # Display final stats
        print("\n7. Final statistics:")
        stats = driver.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\nTest completed successfully!")
        return True
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return False
    except Exception as e:
        print(f"\nERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Always stop the driver
        print("\nStopping driver...")
        driver.stop()
        print("Driver stopped")


def test_speed_range():
    """Test different speed values"""
    print("\n=== Testing Speed Range ===")
    
    driver = MotorKitStepperProxy()
    
    try:
        if not driver.start():
            print("ERROR: Failed to start driver")
            return False
        
        speeds = [0.1, 0.25, 0.5, 0.75, 1.0]
        
        for speed in speeds:
            print(f"\nTesting speed {speed} (forward)...")
            driver.set_speed("forward", speed)
            
            # Get stats to show calculated frequency
            stats = driver.get_stats()
            print(f"  Calculated frequency: {stats.get('step_frequency', 0):.1f} Hz")
            
            time.sleep(2)
        
        # Test reverse speeds
        print("\nTesting reverse speeds...")
        for speed in [0.3, 0.7]:
            print(f"Testing speed {speed} (reverse)...")
            driver.set_speed("reverse", speed)
            time.sleep(2)
        
        driver.set_speed("stopped", 0.0)
        return True
        
    except Exception as e:
        print(f"ERROR during speed test: {e}")
        return False
    finally:
        driver.stop()


def main():
    """Main test function"""
    print("MotorKit Stepper Driver Test")
    print("============================")
    
    # Check if we should run basic test
    if len(sys.argv) > 1 and sys.argv[1] == "--speed-only":
        success = test_speed_range()
    else:
        success = test_basic_functionality()
        
        if success:
            print("\nRunning speed range test...")
            success = test_speed_range()
    
    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
