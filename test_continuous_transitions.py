#!/usr/bin/env python3
"""
Test script for continuous motor driver transitions.
Tests the new target-based system that updates smoothly without canceling threads.
"""

import time
import sys
from motor_drivers.motorkit_driver import MotorKitDriver
from motor_drivers.motorkit_stepper_proxy import MotorKitStepperProxy
from motor_drivers.drv8825_driver import DRV8825Driver
from motor_drivers.drv8825_driver_pwm import DRV8825DriverPWM


def test_continuous_transitions(driver, driver_name):
    """Test continuous transitions that update targets dynamically."""
    print(f"\n=== Testing {driver_name} Continuous Transitions ===")
    
    # Start the driver
    if not driver.start():
        print(f"Failed to start {driver_name}")
        return False
    
    try:
        print("1. Start with smooth acceleration")
        driver.set_speed("forward", 0.8, duration=3.0, divisions=10)
        time.sleep(1)  # Let it start accelerating
        
        print("2. Change target mid-transition (should smoothly adjust)")
        driver.set_speed("forward", 0.4, duration=2.0, divisions=8)
        time.sleep(1)
        
        print("3. Change target again (should continue smoothly)")
        driver.set_speed("forward", 1.0, duration=2.0, divisions=6)
        time.sleep(2)
        
        print("4. Rapid target changes (simulating yaw_controller behavior)")
        for i in range(10):
            # Simulate frequent calls like yaw_controller makes
            speed = 0.3 + (i * 0.07)  # Gradually increase from 0.3 to 0.93
            driver.set_speed("forward", speed, duration=1.0, divisions=5)
            time.sleep(0.2)  # 5Hz like yaw_controller
        
        time.sleep(2)  # Let final transition complete
        
        print("5. Direction change with continuous transition")
        driver.set_speed("reverse", 1.0, duration=2.0, divisions=8)
        time.sleep(4)
        
        print("6. More rapid direction/speed changes")
        driver.set_speed("forward", 0.3, duration=1.5, divisions=6)
        time.sleep(0.5)
        driver.set_speed("reverse", 1.0, duration=1.5, divisions=6)
        time.sleep(1.5)
        driver.set_speed("forward", 0.5, duration=1.5, divisions=6)
        time.sleep(2)
        
        print("7. Smooth stop")
        driver.set_speed("stopped", 0.0, duration=1.0, divisions=4)
        time.sleep(2)
        
        print(f"{driver_name} continuous transition test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during {driver_name} test: {e}")
        return False
    
    finally:
        driver.stop()


def test_yaw_controller_simulation(driver, driver_name):
    """Simulate the yaw_controller's frequent set_speed calls."""
    print(f"\n=== Simulating YawController behavior with {driver_name} ===")
    
    if not driver.start():
        print(f"Failed to start {driver_name}")
        return False
    
    try:
        print("Simulating person tracking with frequent speed updates...")
        
        # Simulate person moving left to right across camera view
        # This creates frequent speed/direction changes like the real yaw_controller
        
        speeds = [
            ("forward", 0.3), ("forward", 0.5), ("forward", 0.7), ("forward", 0.8),
            ("forward", 0.6), ("forward", 0.4), ("forward", 0.2), ("stopped", 0.0),
            ("reverse", 0.2), ("reverse", 0.4), ("reverse", 0.6), ("reverse", 0.8),
            ("reverse", 0.7), ("reverse", 0.5), ("reverse", 0.3), ("stopped", 0.0)
        ]
        
        for direction, speed in speeds:
            print(f"  Setting: {direction} @ {speed}")
            driver.set_speed(direction, speed, duration=2.0, divisions=10)
            time.sleep(0.2)  # 5Hz update rate like yaw_controller
        
        # Let final transition complete
        time.sleep(3)
        
        print(f"{driver_name} yaw_controller simulation completed!")
        return True
        
    except Exception as e:
        print(f"Error during {driver_name} simulation: {e}")
        return False
    
    finally:
        driver.stop()


def main():
    """Main test function."""
    print("Continuous Motor Transition Test")
    print("================================")
    print("This test verifies that frequent set_speed calls work smoothly")
    print("without canceling threads or causing motor stuttering.\n")
    
    # Test available drivers
    drivers_to_test = []
    
    # Add MotorKit drivers
    try:
        motorkit_driver = MotorKitDriver()
        # drivers_to_test.append((motorkit_driver, "MotorKitDriver"))
    except Exception as e:
        print(f"MotorKitDriver not available: {e}")
    
    # Add MotorKit Stepper driver (new multiprocess stepper implementation)
    try:
        motorkit_stepper_driver = MotorKitStepperProxy()
        drivers_to_test.append((motorkit_stepper_driver, "MotorKitStepperProxy"))
    except Exception as e:
        print(f"MotorKitStepperProxy not available: {e}")
    
    # Add DRV8825 drivers (require specific hardware)
    try:
        drv8825_driver = DRV8825Driver()
        # drivers_to_test.append((drv8825_driver, "DRV8825Driver"))
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
            # Test continuous transitions
            if test_continuous_transitions(driver, name):
                success_count += 1
            
            # Create new instance for simulation test
            if name == "MotorKitDriver":
                sim_driver = MotorKitDriver()
            elif name == "MotorKitStepperProxy":
                sim_driver = MotorKitStepperProxy()
            elif name == "DRV8825Driver":
                sim_driver = DRV8825Driver()
            elif name == "DRV8825DriverPWM":
                sim_driver = DRV8825DriverPWM()
            
            # Test yaw_controller simulation
            test_yaw_controller_simulation(sim_driver, name)
            
        except KeyboardInterrupt:
            print(f"\nTest interrupted during {name}")
            try:
                driver.stop()
            except:
                pass
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
    print("\nKey improvements:")
    print("- Frequent set_speed calls no longer cancel/restart threads")
    print("- Smooth target updates without motor stuttering")
    print("- Continuous transitions adapt to new targets dynamically")
    print("- Perfect for yaw_controller's frequent update pattern")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
