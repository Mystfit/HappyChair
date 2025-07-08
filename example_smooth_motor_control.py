#!/usr/bin/env python3
"""
Example demonstrating smooth motor speed transitions.
Shows how to use the new duration and divisions parameters.
"""

import time
from motor_drivers.motorkit_driver import MotorKitDriver


def main():
    """Example of smooth motor control."""
    print("Smooth Motor Control Example")
    print("============================")
    
    # Create and start motor driver
    motor = MotorKitDriver()
    
    if not motor.start():
        print("Failed to start motor driver")
        return
    
    try:
        print("\n1. Traditional immediate speed changes:")
        print("   Setting speed to 0.5 immediately...")
        motor.set_speed("forward", 0.5)  # duration defaults to 0.0
        time.sleep(2)
        
        print("   Stopping immediately...")
        motor.set_speed("stopped", 0.0)
        time.sleep(1)
        
        print("\n2. Smooth speed transitions:")
        print("   Gradually accelerating to full speed over 3 seconds...")
        motor.set_speed("forward", 1.0, duration=3.0, divisions=10)
        time.sleep(4)  # Wait for transition to complete
        
        print("   Smoothly reducing to half speed over 2 seconds...")
        motor.set_speed("forward", 0.5, duration=2.0, divisions=8)
        time.sleep(3)
        
        print("\n3. Direction change with smooth transition:")
        print("   Changing direction with 2-second transition...")
        # This will first slow down to zero, then accelerate in reverse
        motor.set_speed("reverse", 0.8, duration=2.0, divisions=6)
        time.sleep(3)
        
        print("\n4. Smooth stop:")
        print("   Gradually stopping over 1.5 seconds...")
        motor.set_speed("stopped", 0.0, duration=1.5, divisions=5)
        time.sleep(2)
        
        print("\nExample completed!")
        
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    
    finally:
        print("Stopping motor...")
        motor.stop()


if __name__ == "__main__":
    main()
