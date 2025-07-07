#!/usr/bin/env python3
"""
Test script for the extended YawController with motor driver support.
Demonstrates usage with both MotorKit and DRV8825 drivers.
"""

import time
import sys
from yaw_controller import YawController


def test_motorkit():
    """Test YawController with MotorKit driver"""
    print("=" * 50)
    print("Testing YawController with MotorKit driver")
    print("=" * 50)
    
    # Create YawController with MotorKit driver (default)
    yaw_controller = YawController(motor_type="motorkit")
    
    try:
        # Test motor initialization
        print("Starting motor control...")
        if yaw_controller.start_motor_control():
            print("✓ Motor control started successfully")
            
            # Get motor stats
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
            # Test motor movements (simulated)
            print("Testing motor movements...")
            yaw_controller._set_motor_forward(1.0)
            time.sleep(1)
            
            yaw_controller._set_motor_reverse(0.3)
            time.sleep(1)
            
            yaw_controller._stop_motor()
            print("✓ Motor movements completed")
            
        else:
            print("✗ Failed to start motor control")
            
    except Exception as e:
        print(f"✗ Error during MotorKit test: {e}")
    
    finally:
        # Cleanup
        yaw_controller.stop_motor_control()
        print("✓ MotorKit test completed")


def test_drv8825():
    """Test YawController with DRV8825 driver"""
    print("=" * 50)
    print("Testing YawController with DRV8825 driver")
    print("=" * 50)
    
    # Create YawController with DRV8825 driver
    yaw_controller = YawController(motor_type="drv8825")
    
    try:
        # Test motor initialization
        print("Starting motor control...")
        if yaw_controller.start_motor_control():
            print("✓ Motor control started successfully")
            
            # Get motor stats
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
            # Test motor movements (simulated)
            print("Testing motor movements...")
            yaw_controller._set_motor_forward(1.0)
            time.sleep(5)
            
            yaw_controller._set_motor_reverse(1.0)
            time.sleep(5)
            
            yaw_controller._stop_motor()
            print("✓ Motor movements completed")
            
        else:
            print("✗ Failed to start motor control")
            
    except Exception as e:
        print(f"✗ Error during DRV8825 test: {e}")
    
    finally:
        # Cleanup
        yaw_controller.stop_motor_control()
        print("✓ DRV8825 test completed")


def test_invalid_motor_type():
    """Test YawController with invalid motor type"""
    print("=" * 50)
    print("Testing YawController with invalid motor type")
    print("=" * 50)
    
    # Create YawController with invalid motor type
    yaw_controller = YawController(motor_type="invalid_motor")
    
    try:
        # This should fail gracefully
        print("Attempting to start motor control with invalid type...")
        if not yaw_controller.start_motor_control():
            print("✓ Invalid motor type handled correctly")
        else:
            print("✗ Invalid motor type should have failed")
            
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    finally:
        yaw_controller.stop_motor_control()
        print("✓ Invalid motor type test completed")


def main():
    """Main test function"""
    print("YawController Motor Driver Test Suite")
    print("====================================")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "motorkit":
            test_motorkit()
        elif test_type == "drv8825":
            test_drv8825()
        elif test_type == "invalid":
            test_invalid_motor_type()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python test_yaw_controller.py [motorkit|drv8825|invalid]")
    else:
        # Run all tests
        test_motorkit()
        print()
        test_drv8825()
        print()
        test_invalid_motor_type()
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    main()
