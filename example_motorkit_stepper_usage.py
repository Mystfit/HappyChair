#!/usr/bin/env python3
"""
Example usage of the MotorKit stepper driver.
Shows how to integrate the new MotorKitStepperProxy into existing applications.
"""

import time
from motor_drivers import MotorKitStepperProxy


def example_basic_usage():
    """Basic usage example"""
    print("=== Basic MotorKit Stepper Usage ===")
    
    # Create and start the driver
    stepper = MotorKitStepperProxy()
    
    if not stepper.start():
        print("Failed to start stepper driver")
        return
    
    try:
        # Move forward at medium speed
        print("Moving forward...")
        stepper.set_speed("forward", 0.5)
        time.sleep(2)
        
        # Change to reverse
        print("Moving reverse...")
        stepper.set_speed("reverse", 0.3)
        time.sleep(2)
        
        # Stop
        print("Stopping...")
        stepper.set_speed("stopped", 0.0)
        
    finally:
        stepper.stop()


def example_smooth_transitions():
    """Example with smooth speed transitions"""
    print("\n=== Smooth Transitions Example ===")
    
    stepper = MotorKitStepperProxy()
    
    if not stepper.start():
        print("Failed to start stepper driver")
        return
    
    try:
        # Smooth acceleration
        print("Smooth acceleration to full speed over 3 seconds...")
        stepper.set_speed("forward", 1.0, duration=3.0)
        time.sleep(4)  # Wait for acceleration + 1 second at full speed
        
        # Smooth deceleration
        print("Smooth deceleration to stop over 2 seconds...")
        stepper.set_speed("stopped", 0.0, duration=2.0)
        time.sleep(3)  # Wait for deceleration to complete
        
    finally:
        stepper.stop()


def example_replacing_existing_motorkit():
    """Example showing how to replace existing MotorKitDriver usage"""
    print("\n=== Replacing Existing MotorKitDriver ===")
    
    # OLD CODE (commented out):
    # from motor_drivers import MotorKitDriver
    # motor = MotorKitDriver()
    
    # NEW CODE:
    from motor_drivers import MotorKitStepperProxy
    motor = MotorKitStepperProxy()
    
    # The API is exactly the same!
    if not motor.start():
        print("Failed to start motor")
        return
    
    try:
        # Same API calls work
        motor.set_speed("forward", 0.4)
        time.sleep(1)
        
        motor.set_speed("reverse", 0.6)
        time.sleep(1)
        
        motor.set_speed("stopped", 0.0)
        
        # Get stats (now includes stepper-specific info)
        stats = motor.get_stats()
        print("Motor stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    finally:
        motor.stop()


def example_yaw_controller_integration():
    """Example showing integration with YawController"""
    print("\n=== YawController Integration Example ===")
    
    # This is how you would modify yaw_controller.py to use the stepper driver:
    print("""
To integrate with YawController, modify yaw_controller.py:

# OLD:
# from motor_drivers import MotorKitDriver
# self.motor_driver = MotorKitDriver()

# NEW:
from motor_drivers import MotorKitStepperProxy
self.motor_driver = MotorKitStepperProxy()

# Everything else stays the same! The API is identical.
""")


def main():
    """Run all examples"""
    print("MotorKit Stepper Driver Usage Examples")
    print("=====================================")
    
    try:
        example_basic_usage()
        example_smooth_transitions()
        example_replacing_existing_motorkit()
        example_yaw_controller_integration()
        
        print("\n✅ All examples completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
