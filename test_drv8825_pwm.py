#!/usr/bin/env python3
"""
Test script for the DRV8825DriverPWM to demonstrate hardware PWM timing consistency.
Compares the new PWM driver with the original sleep-based driver.
"""

import time
import sys
from yaw_controller import YawController


def test_drv8825_pwm():
    """Test YawController with DRV8825 PWM driver"""
    print("=" * 60)
    print("Testing YawController with DRV8825 PWM driver")
    print("Hardware PWM for consistent timing")
    print("=" * 60)
    
    # Create YawController with DRV8825 PWM driver
    yaw_controller = YawController(motor_type="drv8825_pwm")
    
    try:
        # Test motor initialization
        print("Starting PWM motor control...")
        if yaw_controller.start_motor_control():
            print("✓ PWM Motor control started successfully")
            
            # Get motor stats
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
            # Test different speeds to demonstrate consistent timing
            print("\nTesting PWM motor movements with different speeds...")
            
            # Test slow speed
            print("Testing slow speed (0.2)...")
            yaw_controller._set_motor_forward(0.2)
            time.sleep(3)
            
            # Test medium speed
            print("Testing medium speed (0.5)...")
            yaw_controller._set_motor_forward(0.5)
            time.sleep(3)
            
            # Test high speed
            print("Testing high speed (1.0)...")
            yaw_controller._set_motor_forward(1.0)
            time.sleep(3)
            
            # Test reverse
            print("Testing reverse direction (0.7)...")
            yaw_controller._set_motor_reverse(0.7)
            time.sleep(3)
            
            # Stop motor
            yaw_controller._stop_motor()
            print("✓ PWM Motor movements completed")
            
            # Show final stats
            final_stats = yaw_controller.get_motor_stats()
            print(f"Final motor stats: {final_stats}")
            
        else:
            print("✗ Failed to start PWM motor control")
            
    except Exception as e:
        print(f"✗ Error during DRV8825 PWM test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        yaw_controller.stop_motor_control()
        print("✓ DRV8825 PWM test completed")


def test_drv8825_original():
    """Test YawController with original DRV8825 driver for comparison"""
    print("=" * 60)
    print("Testing YawController with original DRV8825 driver")
    print("Sleep-based timing (may be inconsistent in Flask)")
    print("=" * 60)
    
    # Create YawController with original DRV8825 driver
    yaw_controller = YawController(motor_type="drv8825")
    
    try:
        # Test motor initialization
        print("Starting original motor control...")
        if yaw_controller.start_motor_control():
            print("✓ Original Motor control started successfully")
            
            # Get motor stats
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
            # Test different speeds
            print("\nTesting original motor movements with different speeds...")
            
            # Test slow speed
            print("Testing slow speed (0.2)...")
            yaw_controller._set_motor_forward(0.2)
            time.sleep(3)
            
            # Test medium speed
            print("Testing medium speed (0.5)...")
            yaw_controller._set_motor_forward(0.5)
            time.sleep(3)
            
            # Test high speed
            print("Testing high speed (1.0)...")
            yaw_controller._set_motor_forward(1.0)
            time.sleep(3)
            
            # Test reverse
            print("Testing reverse direction (0.7)...")
            yaw_controller._set_motor_reverse(0.7)
            time.sleep(3)
            
            # Stop motor
            yaw_controller._stop_motor()
            print("✓ Original Motor movements completed")
            
            # Show final stats
            final_stats = yaw_controller.get_motor_stats()
            print(f"Final motor stats: {final_stats}")
            
        else:
            print("✗ Failed to start original motor control")
            
    except Exception as e:
        print(f"✗ Error during original DRV8825 test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        yaw_controller.stop_motor_control()
        print("✓ Original DRV8825 test completed")


def test_speed_consistency():
    """Test to demonstrate timing consistency between drivers"""
    print("=" * 60)
    print("Speed Consistency Test")
    print("Comparing PWM vs Sleep-based timing")
    print("=" * 60)
    
    print("This test demonstrates the difference in timing consistency:")
    print("- PWM driver: Hardware-timed, consistent regardless of system load")
    print("- Original driver: Software-timed, affected by GIL and thread contention")
    print("\nIn a Flask server environment with multiple threads,")
    print("the PWM driver will maintain consistent motor speed,")
    print("while the original driver may have irregular timing.")
    print("\nTo see the difference, run this test both:")
    print("1. Standalone (consistent for both)")
    print("2. While Flask server is running (PWM remains consistent)")


def main():
    """Main test function"""
    print("DRV8825 PWM Driver Test Suite")
    print("============================")
    print("Testing hardware PWM solution for timing consistency")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "pwm":
            test_drv8825_pwm()
        elif test_type == "original":
            test_drv8825_original()
        elif test_type == "consistency":
            test_speed_consistency()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python test_drv8825_pwm.py [pwm|original|consistency]")
    else:
        # Run consistency explanation and PWM test
        test_speed_consistency()
        print()
        test_drv8825_pwm()
    
    print("\nTest completed!")
    print("\nTo use the PWM driver in your Flask server:")
    print("Change YawController initialization from:")
    print("  yaw_controller = YawController(io_controller, motor_type='drv8825')")
    print("To:")
    print("  yaw_controller = YawController(io_controller, motor_type='drv8825_pwm')")


if __name__ == "__main__":
    main()
