#!/usr/bin/env python3
"""
Visual test for hardware PWM on GPIO 18.
Creates a slow PWM signal that should be visible on LED indicators.
"""

import time
from rpi_hardware_pwm import HardwarePWM

def test_visual_pwm():
    """Test hardware PWM with visual verification using LED indicators"""
    print("Visual Hardware PWM Test on GPIO 18")
    print("=" * 40)
    print("This test will create a slow PWM signal that should be visible on LED indicators.")
    print("GPIO 18 LED should blink on and off at the specified frequency.")
    print()
    
    try:
        # Initialize hardware PWM on channel 0 (GPIO 18)
        print("Initializing Hardware PWM on GPIO 18 (channel 0)...")
        pwm = HardwarePWM(pwm_channel=0, hz=4, chip=0)
        print("✓ Hardware PWM initialized")
        print()
        
        # Test 1: Very slow blinking - 1Hz (1 second on, 1 second off)
        print("Test 1: 1Hz PWM (1 second on, 1 second off)")
        print("Watch GPIO 18 LED - it should blink slowly")
        pwm.start(50)  # 50% duty cycle
        pwm.change_frequency(1)
        print("Running for 10 seconds...")
        time.sleep(10)
        pwm.stop()
        print("✓ Test 1 complete")
        print()
        
        # Test 2: Medium blinking - 2Hz (0.5 seconds on, 0.5 seconds off)
        print("Test 2: 2Hz PWM (0.5 seconds on, 0.5 seconds off)")
        print("Watch GPIO 18 LED - it should blink faster")
        pwm.start(50)  # 50% duty cycle
        pwm.change_frequency(2)
        print("Running for 10 seconds...")
        time.sleep(10)
        pwm.stop()
        print("✓ Test 2 complete")
        print()
        
        # Test 3: Fast blinking - 4Hz (0.25 seconds on, 0.25 seconds off)
        print("Test 3: 4Hz PWM (0.25 seconds on, 0.25 seconds off)")
        print("Watch GPIO 18 LED - it should blink even faster")
        pwm.start(50)  # 50% duty cycle
        pwm.change_frequency(4)
        print("Running for 10 seconds...")
        time.sleep(10)
        pwm.stop()
        print("✓ Test 3 complete")
        print()
        
        # Test 4: Different duty cycles at 2Hz
        print("Test 4: Different duty cycles at 2Hz")
        duty_cycles = [25, 50, 75]
        
        for duty in duty_cycles:
            print(f"  Testing {duty}% duty cycle at 2Hz")
            print(f"  LED should be ON for {duty}% of each cycle")
            pwm.start(duty)
            pwm.change_frequency(2)
            time.sleep(5)
            pwm.stop()
            time.sleep(1)
        
        print("✓ Test 4 complete")
        print()
        
        print("Visual Hardware PWM test completed successfully!")
        print()
        print("Results:")
        print("- If you saw the GPIO 18 LED blinking at different speeds, hardware PWM is working")
        print("- If the LED didn't blink or stayed constant, there may be an issue with PWM setup")
        
    except Exception as e:
        print(f"Error during visual PWM test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_visual_pwm()
