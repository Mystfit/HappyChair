#!/usr/bin/env python3
"""
Test script for motor driver smooth speed transitions.
Demonstrates the new duration and divisions parameters.
"""

import time
import sys
from motor_drivers.motorkit_driver import MotorKitDriver
from motor_drivers.drv8825_driver import DRV8825Driver
from motor_drivers.drv8825_driver_pwm import DRV8825DriverPWM


def test_motor_transitions(driver, driver_name):
    """Test smooth speed transitions with a motor driver."""
    print(f"\n=== Testing {driver_name} ===")
    
    # Start the driver
    if not driver.start():
        print(f"Failed to start {driver_name}")
        return False
    
    try:
        print("1. Immediate speed change (duration=0.0)")
        driver.set_speed("forward", 0.5, duration=0.0)
        time.sleep(2)
        
        print("2. Smooth acceleration over 3 seconds with 5 divisions")
        driver.set_speed("forward", 1.0, duration=3.0, divisions=5)
        time.sleep(4)  # Wait for transition to complete
        
        print("3. Smooth deceleration over 2 seconds with 8 divisions")
        driver.set_speed("forward", 0.3, duration=2.0, divisions=8)
        time.sleep(3)  # Wait for transition to complete
        
        print("4. Direction change with smooth transition (2 seconds, 6 divisions)")
        driver.set_speed("reverse", 0.7, duration=2.0, divisions=6)
        time.sleep(3)  # Wait for transition to complete
        
        print("5. Smooth stop over 1.5 seconds with 4 divisions")
        driver.set_speed("stopped", 0.0, duration=1.5, divisions=4)
        time.sleep(2)  # Wait for transition to complete
        
        print(f"{driver_name} test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during {driver_name} test: {e}")
        return False
    
    finally:
        driver.stop()


def main():
    """Main test function."""
    print("Motor Driver Smooth Transition Test")
    print("===================================")
    
    # Test available drivers
    drivers_to_test = []
    
    # Add MotorKit driver (most likely to work without hardware)
    try:
        motorkit_driver = MotorKitDriver()
        drivers_to_test.append((motorkit_driver, "MotorKitDriver"))
    except Exception as e:
        print(f"MotorKitDriver not available: {e}")
    
    # Add DRV8825 drivers (require specific hardware)
    try:
        drv8825_driver = DRV8825Driver()
        drivers_to_test.append((drv8825_driver, "DRV8825Driver"))
    except Exception as e:
        print(f"DRV8825Driver not available: {e}")
    
    try:
        drv8825_pwm_driver = DRV8825DriverPWM()
        drivers_to_test.append((drv8825_pwm_driver, "DRV8825DriverPWM"))
    except Exception as e:
        print(f"DRV8825DriverPWM not available: {e}")
    
    if not drivers_to_test:
        print("No motor drivers available for testing!")
        return 1
    
    # Test each available driver
    success_count = 0
    for driver, name in drivers_to_test:
        try:
            if test_motor_transitions(driver, name):
                success_count += 1
        except KeyboardInterrupt:
            print(f"\nTest interrupted during {name}")
            driver.stop()
            break
        except Exception as e:
            print(f"Unexpected error testing {name}: {e}")
            try:
                driver.stop()
            except:
                pass
    
    print(f"\n=== Test Summary ===")
    print(f"Drivers tested: {len(drivers_to_test)}")
    print(f"Successful tests: {success_count}")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
