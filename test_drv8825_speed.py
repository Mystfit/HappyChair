#!/usr/bin/env python3
"""
Test script to verify DRV8825 speed calculations.
"""

from motor_drivers.drv8825_driver import DRV8825Driver
import time


def test_speed_calculations():
    """Test the speed to step delay calculations"""
    print("Testing DRV8825 Speed Calculations")
    print("=" * 40)
    
    # Create driver (without starting it to avoid GPIO issues)
    driver = DRV8825Driver()
    
    # Test different speed values
    test_speeds = [0.1, 0.3, 0.5, 0.7, 1.0]
    
    print(f"Speed range: {driver.min_step_delay:.4f}s (fastest) to {driver.max_step_delay:.4f}s (slowest)")
    print(f"Range difference: {driver.max_step_delay - driver.min_step_delay:.4f}s")
    print()
    
    for speed in test_speeds:
        # Calculate step delay using the same formula as in set_speed
        if speed > 0:
            step_delay = driver.max_step_delay - (speed * (driver.max_step_delay - driver.min_step_delay))
        else:
            step_delay = driver.max_step_delay
        
        # Calculate steps per second for comparison
        steps_per_second = 1.0 / (step_delay * 2)  # *2 because each step has high and low phase
        
        print(f"Speed {speed:.1f}: delay={step_delay:.4f}s, ~{steps_per_second:.1f} steps/sec")
    
    print()
    print("Speed ratio comparison:")
    fast_delay = driver.min_step_delay
    slow_delay = driver.max_step_delay
    speed_ratio = slow_delay / fast_delay
    print(f"Fastest vs Slowest ratio: {speed_ratio:.1f}x difference")


def test_driver_speed_setting():
    """Test the actual driver speed setting (without GPIO)"""
    print("\nTesting Driver Speed Setting")
    print("=" * 40)
    
    # Create driver
    driver = DRV8825Driver()
    driver.enabled = True  # Fake enable for testing
    
    test_speeds = [0.1, 0.5, 1.0]
    
    for speed in test_speeds:
        print(f"\nTesting speed {speed}:")
        driver.set_speed("forward", speed)
        
        # Check the calculated delay
        with driver.step_lock:
            calculated_delay = driver.current_step_delay
        
        print(f"  Calculated delay: {calculated_delay:.4f}s")
        print(f"  Expected steps/sec: ~{1.0/(calculated_delay*2):.1f}")


if __name__ == "__main__":
    test_speed_calculations()
    test_driver_speed_setting()
