#!/usr/bin/env python3
"""
Simple test script to verify hardware PWM is working on GPIO 18.
"""

import time
from rpi_hardware_pwm import HardwarePWM

def test_hardware_pwm():
    """Test hardware PWM on GPIO 18 (PWM channel 0)"""
    print("Testing Hardware PWM on GPIO 18 (PWM channel 0)")
    
    try:
        # Initialize hardware PWM on channel 0 (GPIO 18)
        pwm = HardwarePWM(pwm_channel=0, hz=100, chip=0)
        print("Hardware PWM initialized")
        
        # Test different frequencies and duty cycles
        frequencies = [10, 50, 100, 200]
        duty_cycles = [25, 50, 75]
        
        for freq in frequencies:
            print(f"\nTesting frequency: {freq}Hz")
            
            for duty in duty_cycles:
                print(f"  Starting PWM at {freq}Hz, {duty}% duty cycle")
                pwm.start(duty)
                pwm.change_frequency(freq)
                time.sleep(2)
                
                print(f"  Stopping PWM")
                pwm.stop()
                time.sleep(1)
        
        print("\nHardware PWM test completed successfully")
        
    except Exception as e:
        print(f"Error testing hardware PWM: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hardware_pwm()
