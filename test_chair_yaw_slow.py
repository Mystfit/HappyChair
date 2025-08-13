#!/usr/bin/env python3
"""
Test script for MotorKit stepper driver with multiprocess architecture.
Tests the new MotorKitStepperProxy implementation.
"""

import time
import sys
from motor_drivers import MotorKitStepperProxy


def test_chair_slow():
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
        driver.set_speed("forward", 0.1, 4.0)  # 10% speed
        time.sleep(5)

        
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

def main():
    """Main test function"""
    print("MotorKit Stepper Driver Test")
    print("============================")
    
    success = test_chair_slow() 
    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
