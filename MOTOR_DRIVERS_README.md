# YawController Motor Driver Architecture

This document describes the extended YawController architecture that supports multiple motor implementations using the Strategy pattern.

## Overview

The YawController has been extended to support both the original Adafruit MotorKit and the new DRV8825 stepper motor controller. The implementation uses a driver-based architecture that allows easy addition of new motor types in the future.

## Architecture

### Motor Driver Pattern

The system uses the **Strategy Pattern** with the following components:

1. **MotorDriver (Abstract Base Class)**: Defines the common interface
2. **MotorKitDriver**: Implementation for Adafruit MotorKit (DC motor)
3. **DRV8825Driver**: Implementation for DRV8825 stepper motor controller
4. **YawController**: Uses the appropriate driver based on configuration

### Class Hierarchy

```
MotorDriver (ABC)
├── MotorKitDriver
└── DRV8825Driver
```

## Usage

### Basic Usage

```python
from yaw_controller import YawController

# Use MotorKit driver (default)
yaw_controller = YawController(motor_type="motorkit")

# Use DRV8825 driver
yaw_controller = YawController(motor_type="drv8825")
```

### With IOController Integration

```python
from yaw_controller import YawController
from io_controller import IOController

io_controller = IOController()

# Create YawController with DRV8825 support
yaw_controller = YawController(
    io_controller=io_controller,
    motor_type="drv8825"
)

# Start tracking
yaw_controller.start_tracking()
```

## Motor Driver Implementations

### MotorKitDriver

- **Type**: DC Motor Controller
- **Hardware**: Adafruit MotorKit
- **Control**: Continuous throttle control (-1.0 to 1.0)
- **Features**: 
  - Immediate and smooth speed changes
  - Bidirectional control
  - Variable speed control
  - Smooth speed transitions with configurable duration and divisions

### DRV8825Driver

- **Type**: Stepper Motor Controller
- **Hardware**: DRV8825 stepper driver board
- **Control**: Step-based movement with continuous stepping
- **GPIO Pins**:
  - Direction: GPIO 24
  - Step: GPIO 18
  - Enable: GPIO 4
  - Mode: GPIO 21, 22, 27
- **Features**:
  - Continuous stepping via background thread
  - Speed control via step delay timing
  - Fullstep mode operation
  - Thread-safe operation
  - Smooth speed transitions with linear interpolation

### DRV8825DriverPWM

- **Type**: Stepper Motor Controller (Hardware PWM)
- **Hardware**: DRV8825 stepper driver board with hardware PWM
- **Control**: Hardware-timed PWM for precise stepping
- **GPIO Pins**:
  - Direction: GPIO 24
  - Step: GPIO 18 or 19 (hardware PWM pins only)
  - Enable: GPIO 4
  - Mode: GPIO 21, 22, 27
- **Features**:
  - Hardware PWM for consistent timing
  - Eliminates GIL-related timing issues
  - Frequency-based speed control
  - Thread-safe operation
  - Smooth speed transitions with linear interpolation

#### DRV8825 Speed Mapping

The DRV8825 driver maps speed values (0.0-1.0) to step delays with a 40x speed range:
- Speed 0.1: 20ms delay (~28 steps/sec, slowest practical speed)
- Speed 0.5: 10ms delay (~49 steps/sec, medium speed)
- Speed 1.0: 0.5ms delay (~1000 steps/sec, fastest speed)
- Mapping: `delay = max_delay - (speed * (max_delay - min_delay))`

**Speed Range:** 0.0005s to 0.02s step delay (40x difference for noticeable speed variations)

## API Reference

### YawController Constructor

```python
YawController(io_controller=None, motor_type="motorkit")
```

**Parameters:**
- `io_controller`: IOController instance for event handling (optional)
- `motor_type`: Motor driver type ("motorkit" or "drv8825")

### Motor Driver Interface

All motor drivers implement the `MotorDriver` abstract base class:

```python
class MotorDriver(ABC):
    def start(self) -> bool:
        """Initialize and start the motor driver"""
        
    def stop(self):
        """Stop the motor and cleanup resources"""
        
    def set_speed(self, direction: str, speed: float, duration: float = 0.0, divisions: int = 10):
        """Set motor direction and speed with optional smooth transitions"""
        
    def is_enabled(self) -> bool:
        """Check if the motor driver is enabled"""
        
    def get_stats(self) -> Dict[str, Any]:
        """Get current motor statistics"""
```

#### Smooth Speed Transitions

All motor drivers now support smooth speed transitions with the following parameters:

- `duration` (float): Time in seconds to reach the target speed (default: 0.0 for immediate change)
- `divisions` (int): Number of intermediate steps during the transition (default: 10)

**Examples:**

```python
# Immediate speed change (traditional behavior)
motor.set_speed("forward", 0.8)

# Smooth acceleration over 2 seconds with 8 steps
motor.set_speed("forward", 0.8, duration=2.0, divisions=8)

# Smooth direction change with transition
motor.set_speed("reverse", 0.6, duration=1.5, divisions=6)

# Gradual stop over 1 second
motor.set_speed("stopped", 0.0, duration=1.0, divisions=5)
```

#### Direction Change Behavior

When changing direction with a duration > 0, the motor will:
1. **First Phase**: Smoothly decelerate to zero speed in the current direction
2. **Brief Pause**: 50ms pause at zero speed
3. **Second Phase**: Smoothly accelerate to target speed in the new direction

This prevents abrupt direction changes that could damage motors or cause mechanical stress.

### Direction Values

- `"forward"`: Move motor forward
- `"reverse"`: Move motor in reverse
- `"stopped"`: Stop motor movement

### Speed Values

- Range: 0.0 to 1.0
- 0.0: Stopped
- 1.0: Maximum speed

## Configuration

### Default GPIO Pins (DRV8825)

```python
dir_pin = 24      # Direction control
step_pin = 18     # Step pulse
enable_pin = 4    # Enable/disable motor
mode_pins = (21, 22, 27)  # Microstepping mode pins
```

### Custom GPIO Configuration

```python
from motor_drivers import DRV8825Driver

# Create custom DRV8825 driver
custom_driver = DRV8825Driver(
    dir_pin=25,
    step_pin=19,
    enable_pin=5,
    mode_pins=(20, 21, 26)
)
```

## Testing

### YawController Testing

Use the provided test script to verify both motor implementations:

```bash
# Test all motor types
python test_yaw_controller.py

# Test specific motor type
python test_yaw_controller.py motorkit
python test_yaw_controller.py drv8825
python test_yaw_controller.py invalid
```

### Smooth Transition Testing

Test the new smooth speed transition functionality:

```bash
# Test smooth transitions with all available drivers
python test_motor_transitions.py

# Test continuous target-based transitions (recommended)
python test_continuous_transitions.py

# Run the example demonstrating smooth control
python example_smooth_motor_control.py
```

The test scripts will demonstrate:
- Immediate speed changes (traditional behavior)
- Smooth acceleration and deceleration
- Direction changes with smooth transitions
- Gradual stopping
- Different division settings for transition smoothness
- **Continuous transitions**: Target updates without thread cancellation
- **YawController simulation**: Frequent updates like real tracking applications

## Error Handling

The system includes comprehensive error handling:

- **Invalid motor type**: Graceful failure with error message
- **Hardware initialization errors**: Logged with specific error details
- **Runtime errors**: Caught and logged without crashing the system
- **Thread safety**: All motor operations are thread-safe

## Extending the System

### Adding New Motor Drivers

1. Create a new driver class inheriting from `MotorDriver`
2. Implement all abstract methods
3. Add the driver to `motor_drivers/__init__.py`
4. Update `YawController.start_motor_control()` to handle the new type

Example:

```python
from motor_drivers.base_driver import MotorDriver

class CustomMotorDriver(MotorDriver):
    def start(self) -> bool:
        # Initialize your motor hardware
        pass
        
    def stop(self):
        # Stop and cleanup
        pass
        
    def set_speed(self, direction: str, speed: float):
        # Control motor speed and direction
        pass
        
    def is_enabled(self) -> bool:
        # Return motor status
        pass
```

## Backward Compatibility

The extended YawController maintains full backward compatibility:

- Default motor type is "motorkit" (existing behavior)
- All existing YawController methods work unchanged
- No changes required to existing code using YawController

## Performance Considerations

### MotorKit Driver
- Immediate response to speed changes
- Low CPU overhead
- Direct hardware control

### DRV8825 Driver
- Background stepping thread (minimal CPU impact)
- Thread-safe operation
- Continuous stepping for smooth movement
- Configurable step timing for speed control

## Troubleshooting

### Common Issues

1. **GPIO Permission Errors**: Ensure the script runs with appropriate GPIO permissions
2. **Hardware Not Found**: Check wiring and GPIO pin assignments
3. **Import Errors**: Verify all dependencies are installed
4. **Threading Issues**: The DRV8825 driver handles threading automatically

### Debug Information

Enable debug output by checking motor stats:

```python
stats = yaw_controller.get_motor_stats()
print(f"Motor stats: {stats}")
```

The stats include:
- Motor type and status
- Current speed and direction
- Driver-specific information
- Thread status (for DRV8825)

## Dependencies

- `lgpio`: For GPIO control (DRV8825 driver, Raspberry Pi 5 compatible)
- `adafruit_motorkit`: For MotorKit support
- `threading`: For background stepping (DRV8825 driver)
- `time`: For timing control

## GPIO Handle Sharing

The DRV8825 driver supports sharing GPIO handles with the IOController to avoid conflicts:

- **Standalone Mode**: DRV8825 creates its own GPIO handle
- **Shared Mode**: DRV8825 uses the IOController's GPIO handle when available

```python
# Standalone usage (DRV8825 creates its own handle)
yaw_controller = YawController(motor_type="drv8825")

# Shared usage (uses IOController's handle)
io_controller = IOController()
yaw_controller = YawController(
    io_controller=io_controller,
    motor_type="drv8825"
)
```

This prevents GPIO pin conflicts and ensures proper resource management.

## Smooth Transition Implementation Details

### Continuous Target-Based System

The new implementation uses a continuous target-based approach instead of discrete transitions:

```python
# Single continuous thread per motor driver
def _continuous_transition_loop(self):
    while self.transition_active:
        # Check current target vs actual speed/direction
        # Take one step toward target
        # Sleep briefly (20Hz update rate)
```

### Key Advantages

- **No Thread Cancellation**: Frequent `set_speed` calls update targets instead of restarting threads
- **Smooth Adaptation**: Motor smoothly adjusts to new targets mid-transition
- **Perfect for Tracking**: Ideal for applications like yaw_controller that make frequent updates
- **Resource Efficient**: Single thread per motor driver, not per transition

### Target Update Mechanism

When `set_speed` is called with duration > 0:
1. Updates the target speed, direction, duration, and divisions
2. Sets a flag indicating the target was updated
3. The continuous loop adapts to the new target on the next iteration
4. No existing transitions are canceled or interrupted

### Thread Safety

- Single continuous transition thread per motor driver
- Thread-safe target updates using locks
- Proper cleanup ensures threads are stopped when motors are stopped
- No race conditions from multiple concurrent transitions

### Performance Considerations

- **Update Rate**: 20Hz (50ms) internal update rate for smooth motion
- **Duration**: Longer durations provide smoother transitions
- **Divisions**: Used to calculate step size, more divisions = finer control
- **CPU Usage**: Minimal - single thread per driver running at 20Hz
- **Recommended**: 4-10 divisions, 0.5-3 seconds duration for most applications

## Example Usage Scenarios

### Gentle Acceleration for Delicate Mechanisms

```python
# Slowly ramp up to avoid mechanical shock
motor.set_speed("forward", 0.8, duration=3.0, divisions=12)
```

### Quick Direction Changes

```python
# Fast but smooth direction change
motor.set_speed("reverse", 0.6, duration=0.5, divisions=4)
```

### Precise Stopping

```python
# Gradually come to a complete stop
motor.set_speed("stopped", 0.0, duration=2.0, divisions=8)
```

### Tracking Applications (YawController Pattern)

```python
# Frequent updates - targets update smoothly without thread cancellation
while tracking:
    # Calculate new speed/direction based on person position
    new_speed = calculate_tracking_speed()
    new_direction = calculate_tracking_direction()
    
    # Update target - motor smoothly adapts to new target
    motor.set_speed(new_direction, new_speed, duration=2.0, divisions=10)
    
    time.sleep(0.2)  # 5Hz update rate - no problem!
```

### Dynamic Target Updates

```python
# Start moving forward
motor.set_speed("forward", 0.5, duration=2.0, divisions=8)
time.sleep(0.5)

# Change target mid-transition - motor smoothly adapts
motor.set_speed("forward", 0.8, duration=1.5, divisions=6)
time.sleep(0.3)

# Change direction - motor will slow down then reverse
motor.set_speed("reverse", 0.6, duration=2.0, divisions=8)
```

## Future Enhancements

Potential future improvements:
- Support for additional stepper motor drivers
- Configurable microstepping modes
- Non-linear acceleration curves (S-curves, exponential)
- Position feedback and closed-loop control
- Multiple motor support
- Acceleration/deceleration limits
- Speed profiling and motion planning
