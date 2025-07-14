# MotorKit Stepper Driver with Multiprocess Architecture

This document describes the implementation of the MotorKit stepper driver using a multiprocess architecture to achieve smooth stepper motor control while avoiding GIL-related timing issues.

## Overview

The MotorKit stepper driver has been upgraded from DC motor control to stepper motor control using the same multiprocess pattern successfully implemented in the DRV8825 driver. This ensures smooth, precise stepper movements by isolating timing-critical I2C operations in a separate process.

## Architecture

### Components

1. **MotorKitStepperProcess** (`motorkit_stepper_process.py`)
   - Subprocess worker that handles actual stepper control
   - Manages MotorKit I2C communication
   - Implements continuous stepping loop with precise timing

2. **MotorKitStepperProxy** (`motorkit_stepper_proxy.py`)
   - Main API interface that inherits from `MotorDriver`
   - Manages subprocess lifecycle
   - Forwards commands to subprocess via queue
   - Maintains API compatibility with existing code

3. **Test Scripts**
   - `test_motorkit_stepper.py` - Comprehensive testing
   - `example_motorkit_stepper_usage.py` - Usage examples

## Key Features

### Speed Control
- **Speed Range**: 0.0 (stopped) to 1.0 (maximum speed)
- **Frequency Mapping**: 50-500 Hz (steps per second)
- **Calculation**: `frequency = 50 + (speed * 450)`

### Stepping Configuration
- **Stepper**: stepper1 (configurable for stepper2)
- **Style**: `stepper.SINGLE` (smoothest operation)
- **Direction**: `stepper.FORWARD` / `stepper.BACKWARD`

### Process Isolation
- I2C operations run in separate process
- Avoids GIL interference with main application
- Precise timing control for step intervals
- Robust error handling and cleanup

## Implementation Details

### Speed-to-Timing Conversion

```python
# Convert 0.0-1.0 speed to step frequency
min_frequency = 50   # Hz
max_frequency = 500  # Hz
frequency = min_frequency + (speed * (max_frequency - min_frequency))

# Calculate step interval
step_interval = 1.0 / frequency
```

### Stepping Loop

The subprocess implements a continuous stepping loop:

```python
def _perform_step(self):
    current_time = time.time()
    
    if current_time - self.last_step_time >= self.step_interval:
        self.stepper_motor.onestep(
            direction=self.step_direction,
            style=self.stepping_style
        )
        self.last_step_time = current_time
```

### Command Processing

Commands are sent via multiprocessing queue:
- `start` - Initialize MotorKit hardware
- `stop` - Stop stepping and release motor
- `set_speed` - Set direction and speed
- `cleanup` - Graceful shutdown

## Usage

### Basic Usage

```python
from motor_drivers import MotorKitStepperProxy

# Create and start driver
stepper = MotorKitStepperProxy()
stepper.start()

# Move forward at 50% speed
stepper.set_speed("forward", 0.5)

# Move reverse at 30% speed  
stepper.set_speed("reverse", 0.3)

# Stop
stepper.set_speed("stopped", 0.0)

# Cleanup
stepper.stop()
```

### Smooth Transitions

```python
# Smooth acceleration over 2 seconds
stepper.set_speed("forward", 0.8, duration=2.0)

# Smooth deceleration over 1.5 seconds
stepper.set_speed("stopped", 0.0, duration=1.5)
```

### Drop-in Replacement

The new driver is a drop-in replacement for the existing MotorKitDriver:

```python
# OLD:
# from motor_drivers import MotorKitDriver
# motor = MotorKitDriver()

# NEW:
from motor_drivers import MotorKitStepperProxy
motor = MotorKitStepperProxy()

# Same API - no other changes needed!
```

## Integration with Existing Code

### YawController Integration

To integrate with your existing YawController:

```python
# In yaw_controller.py, change:
# from motor_drivers import MotorKitDriver
# self.motor_driver = MotorKitDriver()

# To:
from motor_drivers import MotorKitStepperProxy
self.motor_driver = MotorKitStepperProxy()
```

All other code remains unchanged due to API compatibility.

## Testing

### Run Basic Tests

```bash
python test_motorkit_stepper.py
```

### Run Speed Range Tests Only

```bash
python test_motorkit_stepper.py --speed-only
```

### Run Usage Examples

```bash
python example_motorkit_stepper_usage.py
```

## Configuration Options

### Constructor Parameters

```python
MotorKitStepperProxy(
    stepper_num=1,              # Use stepper1 or stepper2
    stepping_style=stepper.SINGLE  # Stepping style
)
```

### Available Stepping Styles

- `stepper.SINGLE` - Single coil (smoothest, default)
- `stepper.DOUBLE` - Double coil (more torque)
- `stepper.INTERLEAVE` - Interleaved (higher resolution)
- `stepper.MICROSTEP` - Microstep (highest resolution)

## Performance Characteristics

### Speed Mapping
- **0.1 speed** = 95 Hz (95 steps/sec)
- **0.5 speed** = 275 Hz (275 steps/sec)  
- **1.0 speed** = 500 Hz (500 steps/sec)

### Timing Precision
- Step timing controlled in isolated process
- Adaptive sleep to prevent busy waiting
- Sub-millisecond timing accuracy

### Resource Usage
- Minimal CPU overhead in main process
- I2C operations isolated to subprocess
- Graceful cleanup on exit

## Error Handling

### Subprocess Management
- Automatic subprocess termination on exit
- Graceful shutdown with cleanup commands
- Force kill if subprocess becomes unresponsive

### I2C Error Isolation
- I2C communication errors contained in subprocess
- Main application remains stable
- Automatic retry and recovery mechanisms

### Hardware Initialization
- Proper MotorKit initialization sequence
- Stepper release on startup and shutdown
- Error reporting for hardware issues

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure `adafruit-circuitpython-motorkit` is installed
   - Check I2C is enabled on Raspberry Pi

2. **Permission Issues**
   - Run with appropriate permissions for I2C access
   - Check user is in `i2c` group

3. **Hardware Issues**
   - Verify MotorKit HAT is properly connected
   - Check stepper motor wiring
   - Ensure adequate power supply

### Debug Information

The driver provides detailed statistics:

```python
stats = stepper.get_stats()
print(stats)
```

Output includes:
- Current speed and direction
- Step frequency
- Subprocess status
- Process ID
- Stepping style and configuration

## Future Enhancements

### Potential Improvements
- Position tracking and homing
- Multiple stepper support
- Custom stepping patterns
- Reed switch integration for limits
- Acceleration/deceleration curves

### Configuration Expansion
- Adjustable frequency ranges
- Custom stepping sequences
- Dynamic style switching
- Power management options

## Conclusion

The MotorKit stepper driver provides smooth, precise stepper motor control while maintaining full API compatibility with existing code. The multiprocess architecture ensures reliable operation without GIL interference, making it suitable for timing-critical applications like the HappyChair project.

The implementation follows the same proven patterns as the DRV8825 driver, providing consistency across the motor driver ecosystem while adapting to the specific requirements of I2C-based stepper control.
