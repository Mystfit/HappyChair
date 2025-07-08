#!/usr/bin/env python3
"""
Example usage of the extended YawController with motor driver support.
This demonstrates how to integrate the YawController with different motor types.
"""

from yaw_controller import YawController
import time


def example_motorkit_usage():
    """Example: Using YawController with MotorKit driver"""
    print("Example: YawController with MotorKit")
    print("-" * 40)
    
    # Create YawController with MotorKit driver (default)
    yaw_controller = YawController(motor_type="motorkit")
    
    try:
        # Start tracking (this will initialize the motor)
        if yaw_controller.start_tracking():
            print("✓ Tracking started with MotorKit driver")
            
            # Let it run for a few seconds
            time.sleep(5)
            
            # Get motor statistics
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
        else:
            print("✗ Failed to start tracking")
            
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # Always stop tracking to cleanup
        yaw_controller.stop_tracking()
        print("✓ Tracking stopped")


def example_drv8825_usage():
    """Example: Using YawController with DRV8825 driver"""
    print("Example: YawController with DRV8825")
    print("-" * 40)
    
    # Create YawController with DRV8825 driver
    yaw_controller = YawController(motor_type="drv8825")
    
    try:
        # Start tracking (this will initialize the stepper motor)
        if yaw_controller.start_tracking():
            print("✓ Tracking started with DRV8825 driver")
            
            yaw_controller.
            
            # Let it run for a few seconds
            time.sleep(5)
            
            # Get motor statistics
            stats = yaw_controller.get_motor_stats()
            print(f"Motor stats: {stats}")
            
        else:
            print("✗ Failed to start tracking")
            
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # Always stop tracking to cleanup
        yaw_controller.stop_tracking()
        print("✓ Tracking stopped")


def example_with_io_controller():
    """Example: Using YawController with IOController integration"""
    print("Example: YawController with IOController")
    print("-" * 40)
    
    # Note: This example assumes you have an IOController instance
    # In practice, you would import and create your IOController here
    
    # For demonstration, we'll use None (no IOController)
    io_controller = None
    
    # Create YawController with DRV8825 and IOController
    yaw_controller = YawController(
        io_controller=io_controller,
        motor_type="drv8825"
    )
    
    try:
        # Start tracking
        if yaw_controller.start_tracking():
            print("✓ Tracking started with IOController integration")
            
            # In a real scenario, the IOController would provide person detection events
            # and the YawController would automatically track detected persons
            
            time.sleep(3)
            
        else:
            print("✗ Failed to start tracking")
            
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        yaw_controller.stop_tracking()
        print("✓ Tracking stopped")


def main():
    """Main example function"""
    print("YawController Extended Motor Driver Examples")
    print("=" * 50)
    
    # Example 1: MotorKit usage
    example_motorkit_usage()
    print()
    
    # Example 2: DRV8825 usage
    example_drv8825_usage()
    print()
    
    # Example 3: IOController integration
    example_with_io_controller()
    print()
    
    print("All examples completed!")
    print("\nKey Benefits:")
    print("- Same YawController API for both motor types")
    print("- Easy switching between motor implementations")
    print("- Backward compatibility with existing code")
    print("- Extensible architecture for future motor types")


if __name__ == "__main__":
    main()
