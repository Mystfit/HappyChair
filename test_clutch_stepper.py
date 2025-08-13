#!/usr/bin/env python3
"""
Test script for the MotorKitStepperProxy with clutch control functionality.
This script demonstrates how to initialize and use the clutch-enabled stepper motor.
"""

import time
import sys
from adafruit_motor import stepper
from io_controller import IOController
from motor_drivers.motorkit_stepper_proxy import MotorKitStepperProxy


def test_clutch_stepper():
    """Test the clutch-enabled stepper motor functionality"""
    
    print("=== MotorKit Stepper Clutch Control Test ===")
    
    # Initialize IOController
    print("Initializing IOController...")
    io_controller = IOController()
    
    # Example GPIO pin assignments (adjust these to match your hardware)
    clutch_output_pin = 14      # GPIO pin to control clutch (output)
    forward_limit_pin = 23      # GPIO pin for forward limit switch (input)
    reverse_limit_pin = 24      # GPIO pin for reverse limit switch (input)
    
    print(f"Using pins: clutch={clutch_output_pin}, forward_limit={forward_limit_pin}, reverse_limit={reverse_limit_pin}")
    
    # Initialize MotorKitStepperProxy with clutch control
    print("Initializing MotorKitStepperProxy with clutch control...")
    motor = MotorKitStepperProxy(
        stepper_num=1,
        io_controller=io_controller,
        clutch_output_pin=clutch_output_pin,
        forward_limit_pin=forward_limit_pin,
        reverse_limit_pin=reverse_limit_pin
    )
    
    try:
        # Start the motor driver
        print("Starting motor driver...")
        if not motor.start():
            print("Failed to start motor driver!")
            return
        
        print("Motor driver started successfully!")
        
        # Display initial clutch status
        clutch_status = motor.get_clutch_status()
        print(f"Initial clutch status: {clutch_status}")
        
        # Test 1: Basic motor movement with clutch
        print("\n--- Test 1: Basic Motor Movement ---")
        print("Moving forward at 50% speed for 3 seconds...")
        motor.set_speed("forward", 0.5)
        time.sleep(3)
        
        print("Stopping motor...")
        motor.set_speed("stopped", 0.0)
        time.sleep(1)
        
        # Test 2: Manual clutch lock/unlock
        print("\n--- Test 2: Manual Clutch Lock ---")
        print("Locking clutch manually...")
        motor.set_clutch_lock(True)
        
        clutch_status = motor.get_clutch_status()
        print(f"Clutch status after lock: {clutch_status}")
        
        print("Attempting to move motor with locked clutch...")
        motor.set_speed("forward", 0.3)
        time.sleep(2)
        
        print("Unlocking clutch...")
        motor.set_clutch_lock(False)
        time.sleep(1)
        
        print("Moving motor after unlock...")
        motor.set_speed("forward", 0.3)
        time.sleep(2)
        
        motor.set_speed("stopped", 0.0)
        time.sleep(1)
        
        # Test 3: Emergency disengagement
        print("\n--- Test 3: Emergency Disengagement ---")
        print("Starting motor movement...")
        motor.set_speed("reverse", 0.4)
        time.sleep(1)
        
        print("Triggering emergency disengagement...")
        motor.emergency_disengage()
        
        clutch_status = motor.get_clutch_status()
        print(f"Clutch status after emergency: {clutch_status}")
        
        time.sleep(2)
        
        # Test 4: Direction reversal
        print("\n--- Test 4: Direction Reversal ---")
        print("Unlocking clutch for direction test...")
        motor.set_clutch_lock(False)
        time.sleep(1)
        
        print("Moving forward...")
        motor.set_speed("forward", 0.3)
        time.sleep(2)
        
        print("Changing to reverse...")
        motor.set_speed("reverse", 0.3)
        time.sleep(2)
        
        print("Stopping...")
        motor.set_speed("stopped", 0.0)
        
        # Display final statistics
        print("\n--- Final Statistics ---")
        stats = motor.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        print("\nTest completed successfully!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up...")
        motor.stop()
        io_controller.shutdown()
        print("Cleanup complete")


def test_without_clutch():
    """Test the stepper motor without clutch functionality for comparison"""
    
    print("=== MotorKit Stepper WITHOUT Clutch Control Test ===")
    
    # Initialize MotorKitStepperProxy without clutch control
    print("Initializing MotorKitStepperProxy without clutch control...")
    motor = MotorKitStepperProxy(
        stepper_num=1,
        stepping_style=stepper.SINGLE
        # No io_controller or clutch pins specified
    )
    
    try:
        # Start the motor driver
        print("Starting motor driver...")
        if not motor.start():
            print("Failed to start motor driver!")
            return
        
        print("Motor driver started successfully!")
        
        # Test basic motor movement
        print("Moving forward at 50% speed for 3 seconds...")
        motor.set_speed("forward", 0.5)
        time.sleep(3)
        
        print("Moving reverse at 30% speed for 3 seconds...")
        motor.set_speed("reverse", 0.3)
        time.sleep(3)
        
        print("Stopping motor...")
        motor.set_speed("stopped", 0.0)
        
        # Display statistics
        print("\n--- Statistics ---")
        stats = motor.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        print("\nTest completed successfully!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up...")
        motor.stop()
        print("Cleanup complete")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--no-clutch":
        test_without_clutch()
    else:
        test_clutch_stepper()
