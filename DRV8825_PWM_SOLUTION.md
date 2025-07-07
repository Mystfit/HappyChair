# DRV8825 PWM Driver Solution

## Problem Description

The original DRV8825Driver implementation experienced timing inconsistencies when running inside the Flask server environment. The stepper motor would run at inconsistent speeds due to:

1. **Python GIL (Global Interpreter Lock)**: Multiple threads competing for execution time
2. **Thread Contention**: Flask request handlers, WebSocket connections, animation player, and detection processes all competing for CPU time
3. **Sleep Timing Issues**: `time.sleep()` calls in the stepping thread were affected by system scheduling and thread preemption
4. **Double Sleep Penalty**: Each step required two sleep calls (HIGH and LOW phases), doubling the timing uncertainty

## Solution: Hardware PWM Implementation

The new `DRV8825DriverPWM` class replaces software-timed stepping with hardware PWM control, providing:

- **Hardware Precision**: PWM frequency controlled by Raspberry Pi's hardware timers
- **GIL Independence**: Hardware PWM unaffected by Python thread scheduling
- **Consistent Timing**: No variability from sleep calls or thread preemption
- **Reduced CPU Load**: Hardware handles step pulse generation
- **Real-time Speed Control**: Dynamic frequency adjustment for speed changes

## Technical Implementation

### Key Changes

1. **PWM Frequency Control**: Converts speed (0.0-1.0) to PWM frequency (50-500 Hz)
2. **Hardware Timing**: Uses `lgpio.tx_pwm()` for precise step pulse generation
3. **50% Duty Cycle**: Provides proper HIGH/LOW timing for stepper driver
4. **Dynamic Frequency**: Real-time speed changes without stopping PWM

### Frequency Mapping

```python
# Speed to frequency conversion
min_frequency = 50   # Hz (slowest: 20ms period = 0.01s per half-step)
max_frequency = 500  # Hz (fastest: 2ms period = 0.001s per half-step)

frequency = min_frequency + (speed * (max_frequency - min_frequency))
```

### PWM Control Flow

```
Speed Change → Calculate Frequency → Update PWM → Hardware Steps Motor
     ↑                                                        ↓
User Input                                            Consistent Timing
```

## Files Modified/Created

### New Files
- `motor_drivers/drv8825_driver_pwm.py` - New PWM-based driver implementation
- `test_drv8825_pwm.py` - Test script for PWM driver
- `DRV8825_PWM_SOLUTION.md` - This documentation

### Modified Files
- `motor_drivers/__init__.py` - Added PWM driver import
- `yaw_controller.py` - Added support for "drv8825_pwm" motor type
- `anim_webapp.py` - Updated to use PWM driver by default

## Usage

### In Flask Server (Default)
The Flask server now uses the PWM driver by default:
```python
yaw_controller = YawController(io_controller, motor_type="drv8825_pwm")
```

### Manual Selection
You can still choose the driver type:
```python
# Original sleep-based driver
yaw_controller = YawController(io_controller, motor_type="drv8825")

# New PWM driver (recommended)
yaw_controller = YawController(io_controller, motor_type="drv8825_pwm")
```

### Testing
```bash
# Test PWM driver
python test_drv8825_pwm.py pwm

# Test original driver for comparison
python test_drv8825_pwm.py original

# Show timing consistency explanation
python test_drv8825_pwm.py consistency
```

## Performance Comparison

### Original Driver (Sleep-based)
- **Standalone**: Consistent timing
- **Flask Server**: Inconsistent timing due to GIL contention
- **CPU Usage**: Higher (tight loop with sleep calls)
- **Timing Accuracy**: Variable (±several milliseconds)

### PWM Driver (Hardware-timed)
- **Standalone**: Consistent timing
- **Flask Server**: Consistent timing (GIL independent)
- **CPU Usage**: Lower (hardware handles timing)
- **Timing Accuracy**: Precise (hardware timer accuracy)

## Hardware Requirements

- Raspberry Pi with hardware PWM support
- DRV8825 stepper motor driver
- Compatible stepper motor
- Proper GPIO pin connections

## GPIO Pin Configuration

Default pin configuration (can be customized):
```python
dir_pin = 24      # Direction control
step_pin = 18     # Step pulses (PWM output)
enable_pin = 4    # Motor enable/disable
mode_pins = (21, 22, 27)  # Microstepping mode
```

## Troubleshooting

### PWM Not Working
1. Ensure GPIO pin 18 supports hardware PWM
2. Check that no other process is using PWM
3. Verify lgpio library is properly installed

### Motor Not Moving
1. Check GPIO connections
2. Verify motor power supply
3. Ensure DRV8825 is properly configured
4. Check enable pin state

### Inconsistent Speed
1. Verify PWM frequency range is appropriate for your motor
2. Check power supply stability
3. Ensure proper motor current settings on DRV8825

## Future Enhancements

1. **Acceleration Control**: Gradual speed ramping for smoother motion
2. **Microstepping Support**: Dynamic microstepping mode changes
3. **Position Feedback**: Encoder integration for closed-loop control
4. **Multiple Motors**: Support for multiple PWM-controlled steppers

## Compatibility

- **Backward Compatible**: Original driver still available as "drv8825"
- **API Compatible**: Same interface as original driver
- **Drop-in Replacement**: No changes needed to existing YawController code

## Conclusion

The PWM-based solution eliminates timing inconsistencies in multi-threaded environments while maintaining full compatibility with existing code. The hardware-timed approach provides reliable, consistent stepper motor control regardless of system load or thread contention.
