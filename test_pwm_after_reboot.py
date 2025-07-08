#!/usr/bin/env python3
"""
Test script to verify PWM functionality after reboot.
Run this after rebooting to check if hardware PWM is working.
"""

import time
import os
from rpi_hardware_pwm import HardwarePWM

def check_pwm_setup():
    """Check if PWM hardware is properly set up"""
    print("PWM Hardware Setup Check")
    print("=" * 30)
    
    # Check if PWM devices exist
    pwm_devices = ["/sys/class/pwm/pwmchip0", "/sys/class/pwm/pwmchip1"]
    for device in pwm_devices:
        if os.path.exists(device):
            print(f"✓ {device} exists")
        else:
            print(f"✗ {device} missing")
    
    # Check overlays
    print("\nChecking device tree overlays...")
    try:
        result = os.popen("dtoverlay -l").read()
        print(f"Loaded overlays: {result.strip()}")
    except Exception as e:
        print(f"Error checking overlays: {e}")
    
    # Check PWM export status
    print("\nChecking PWM export status...")
    try:
        if os.path.exists("/sys/class/pwm/pwmchip0/pwm0"):
            print("✓ PWM channel 0 is exported")
        else:
            print("✗ PWM channel 0 not exported")
            
        if os.path.exists("/sys/class/pwm/pwmchip0/pwm1"):
            print("✓ PWM channel 1 is exported")
        else:
            print("✗ PWM channel 1 not exported")
            
        if os.path.exists("/sys/class/pwm/pwmchip0/pwm2"):
            print("✓ PWM channel 2 is exported")
        else:
            print("✗ PWM channel 2 not exported")
    except Exception as e:
        print(f"Error checking PWM export: {e}")

def test_hardware_pwm_simple():
    """Simple hardware PWM test"""
    print("\nTesting Hardware PWM...")
    print("=" * 30)
    
    try:
        # Test PWM channel 0 (GPIO 18)
        print("Initializing hardware PWM on GPIO 18...")
        pwm = HardwarePWM(pwm_channel=2, hz=1, chip=0)
        print("✓ Hardware PWM initialized successfully")
        
        print("Starting 1Hz PWM (should see GPIO 18 LED blinking slowly)...")
        pwm.start(50)  # 50% duty cycle
        print("PWM running for 10 seconds - watch GPIO 18 LED...")
        time.sleep(10)
        
        print("Stopping PWM...")
        pwm.stop()
        print("✓ PWM test completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Hardware PWM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("Post-Reboot PWM Test")
    print("=" * 40)
    print("This script tests if hardware PWM is working after reboot.")
    print()
    
    # Check setup
    check_pwm_setup()
    
    # Test hardware PWM
    success = test_hardware_pwm_simple()
    
    print("\n" + "=" * 40)
    if success:
        print("✓ Hardware PWM is working correctly!")
        print("GPIO 18 should have been blinking during the test.")
    else:
        print("✗ Hardware PWM is not working properly.")
        print("Check the overlay configuration and reboot if needed.")

if __name__ == "__main__":
    main()
