#!/usr/bin/env python3
"""
Test script for the new DRV8825DriverPWMProxy multiprocess implementation.
Tests both isolated operation and comparison with the original driver.
"""

import time
import sys
from motor_drivers import DRV8825DriverPWM, DRV8825DriverPWMProxy


def test_multiprocess_driver():
    """Test the new multiprocess DRV8825 driver"""
    print("=" * 60)
    print("Testing DRV8825DriverPWMProxy (Multiprocess Implementation)")
    print("=" * 60)
    
    # Create multiprocess driver
    driver = DRV8825DriverPWMProxy()
    
    try:
        # Test driver initialization
        print("Starting multiprocess driver...")
        if driver.start():
            print("✓ Multiprocess driver started successfully")
            
            # Get driver stats
            stats = driver.get_stats()
            print(f"Driver stats: {stats}")
            
            # Test motor movements
            print("\nTesting motor movements...")
            
            print("Forward at full speed for 3 seconds...")
            driver.set_speed("forward", 1.0)
            time.sleep(3)
            
            print("Reverse at half speed for 3 seconds...")
            driver.set_speed("reverse", 0.5)
            time.sleep(3)
            
            print("Forward at quarter speed for 3 seconds...")
            driver.set_speed("forward", 0.25)
            time.sleep(3)
            
            print("Stopping motor...")
            driver.set_speed("stopped", 0.0)
            time.sleep(1)
            
            # Test smooth transitions
            print("\nTesting smooth transitions...")
            print("Smooth acceleration to full speed over 2 seconds...")
            driver.set_speed("forward", 1.0, duration=2.0, divisions=10)
            time.sleep(3)
            
            print("Smooth deceleration to stop over 2 seconds...")
            driver.set_speed("stopped", 0.0, duration=2.0, divisions=10)
            time.sleep(3)
            
            # Get final stats
            final_stats = driver.get_stats()
            print(f"\nFinal driver stats: {final_stats}")
            
            print("✓ Multiprocess driver test completed successfully")
            
        else:
            print("✗ Failed to start multiprocess driver")
            return False
            
    except Exception as e:
        print(f"✗ Error during multiprocess driver test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print("\nCleaning up multiprocess driver...")
        driver.stop()
        print("✓ Multiprocess driver cleanup completed")
    
    return True


def test_original_driver():
    """Test the original DRV8825DriverPWM for comparison"""
    print("\n" + "=" * 60)
    print("Testing DRV8825DriverPWM (Original Implementation)")
    print("=" * 60)
    
    # Create original driver
    driver = DRV8825DriverPWM()
    
    try:
        # Test driver initialization
        print("Starting original driver...")
        if driver.start():
            print("✓ Original driver started successfully")
            
            # Get driver stats
            stats = driver.get_stats()
            print(f"Driver stats: {stats}")
            
            # Test motor movements (shorter test)
            print("\nTesting motor movements...")
            
            print("Forward at full speed for 2 seconds...")
            driver.set_speed("forward", 1.0)
            time.sleep(2)
            
            print("Reverse at half speed for 2 seconds...")
            driver.set_speed("reverse", 0.5)
            time.sleep(2)
            
            print("Stopping motor...")
            driver.set_speed("stopped", 0.0)
            time.sleep(1)
            
            # Get final stats
            final_stats = driver.get_stats()
            print(f"\nFinal driver stats: {final_stats}")
            
            print("✓ Original driver test completed successfully")
            
        else:
            print("✗ Failed to start original driver")
            return False
            
    except Exception as e:
        print(f"✗ Error during original driver test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print("\nCleaning up original driver...")
        driver.stop()
        print("✓ Original driver cleanup completed")
    
    return True


def test_rapid_commands():
    """Test rapid command sending to simulate web server load"""
    print("\n" + "=" * 60)
    print("Testing Rapid Command Handling (Simulating Web Server Load)")
    print("=" * 60)
    
    driver = DRV8825DriverPWMProxy()
    
    try:
        if not driver.start():
            print("✗ Failed to start driver for rapid command test")
            return False
        
        print("Sending rapid commands to simulate web server scenario...")
        
        # Simulate rapid frequency changes like in web server
        commands = [
            ("forward", 0.3),
            ("forward", 0.5),
            ("forward", 0.8),
            ("forward", 1.0),
            ("forward", 0.7),
            ("forward", 0.4),
            ("stopped", 0.0),
            ("reverse", 0.3),
            ("reverse", 0.6),
            ("reverse", 0.9),
            ("stopped", 0.0)
        ]
        
        for i, (direction, speed) in enumerate(commands):
            print(f"Command {i+1}: {direction} @ {speed}")
            driver.set_speed(direction, speed)
            time.sleep(0.5)  # Short delay between commands
        
        print("✓ Rapid command test completed")
        return True
        
    except Exception as e:
        print(f"✗ Error during rapid command test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        driver.stop()


def main():
    """Main test function"""
    print("DRV8825 Multiprocess Driver Test Suite")
    print("======================================")
    
    test_results = []
    
    try:
        # Test multiprocess implementation
        result1 = test_multiprocess_driver()
        test_results.append(("Multiprocess Driver", result1))
        
        # Small delay between tests
        time.sleep(2)
        
        # Test rapid commands
        result2 = test_rapid_commands()
        test_results.append(("Rapid Commands", result2))
        
        # Small delay between tests
        time.sleep(2)
        
        # Test original implementation for comparison (optional)
        if len(sys.argv) > 1 and sys.argv[1].lower() == "compare":
            result3 = test_original_driver()
            test_results.append(("Original Driver", result3))
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        all_passed = True
        for test_name, result in test_results:
            status = "PASSED" if result else "FAILED"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n✓ All tests PASSED! The multiprocess implementation is working correctly.")
            print("  The stutter issue should be resolved in the web server environment.")
        else:
            print("\n✗ Some tests FAILED. Please check the implementation.")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
