# Clutch Control System for MotorKit Stepper

This document describes the electronically controlled clutch system implemented for the MotorKit stepper motor driver in the HappyChair animatronic controller.

## Overview

The clutch control system provides safe and reliable control of stepper motor engagement through GPIO-controlled clutch mechanisms and limit switches. This system prevents mechanical damage by automatically disengaging the clutch when rotation limits are reached and provides manual override capabilities for debugging and emergency situations.

## Features

- **Automatic Clutch Engagement**: Clutch automatically engages when motor starts and disengages when stopped
- **Rotation Limit Protection**: Reed switches detect maximum rotation limits and prevent further movement in blocked directions
- **Manual Clutch Lock**: Ability to manually lock/unlock the clutch for maintenance and debugging
- **Emergency Disengagement**: Immediate clutch disengagement with motor stop and lock
- **Frontend Control Interface**: Web-based controls for manual clutch operation
- **Real-time Status Monitoring**: Live status updates via WebSocket

## Hardware Requirements

### GPIO Pins
- **1x Output Pin**: Controls clutch engagement (HIGH = engaged, LOW = disengaged)
- **2x Input Pins**: Monitor rotation limit switches (HIGH = normal, LOW = limit reached)

### External Hardware
- **Electronically Controlled Clutch**: Activated by GPIO output signal
- **2x Reed Switches**: Positioned to detect maximum rotation limits in both directions
- **Pull-up Resistors**: For limit switch inputs (handled in software)

## Software Architecture

### Core Components

#### MotorKitStepperProxy (Enhanced)
The main stepper motor proxy class has been enhanced with clutch control capabilities:

```python
from motor_drivers.motorkit_stepper_proxy import MotorKitStepperProxy
from io_controller import IOController
from adafruit_motor import stepper

# Initialize with clutch control
io_controller = IOController()
motor = MotorKitStepperProxy(
    stepper_num=1,
    stepping_style=stepper.SINGLE,
    io_controller=io_controller,
    clutch_output_pin=14,      # GPIO pin for clutch control
    forward_limit_pin=23,      # GPIO pin for forward limit switch
    reverse_limit_pin=24       # GPIO pin for reverse limit switch
)
```

#### New Methods Added

**Clutch Control:**
- `set_clutch_lock(locked: bool)` - Manually lock/unlock clutch
- `emergency_disengage()` - Emergency stop with clutch lock
- `get_clutch_status()` - Get current clutch and limit switch status

**Internal Methods:**
- `_engage_clutch()` - Engage clutch (set GPIO HIGH)
- `_disengage_clutch()` - Disengage clutch (set GPIO LOW)
- `_is_direction_blocked(direction)` - Check if direction is blocked by limits
- `_handle_gpio_event(event)` - Process GPIO events from IOController

### Integration Points

#### IOController Integration
The clutch system integrates with the existing IOController for GPIO management:
- Registers clutch output pin and limit switch input pins
- Monitors GPIO events for limit switch state changes
- Handles pin configuration and cleanup

#### WebSocket Status Updates
Clutch status is included in the existing WebSocket status updates:
```javascript
{
  motor_stats: {
    // Existing motor stats...
    driver_clutch_enabled: true,
    driver_clutch_engaged: false,
    driver_clutch_locked: false,
    driver_forward_limit_active: false,
    driver_reverse_limit_active: false,
    // Additional clutch info...
  }
}
```

## API Endpoints

### Clutch Control Endpoints

#### Lock/Unlock Clutch
```http
POST /api/motor/clutch/lock
Content-Type: application/json

{
  "locked": true  // true to lock, false to unlock
}
```

#### Emergency Disengagement
```http
POST /api/motor/clutch/emergency-disengage
```

#### Get Clutch Status
```http
GET /api/motor/clutch/status
```

Response:
```json
{
  "success": true,
  "clutch_status": {
    "clutch_engaged": false,
    "clutch_locked": false,
    "forward_limit_active": false,
    "reverse_limit_active": false,
    "clutch_output_pin": 14,
    "forward_limit_pin": 23,
    "reverse_limit_pin": 24
  }
}
```

## Frontend Interface

### Clutch Control Panel
The IOPanel.js component has been enhanced with a clutch control section that displays:

- **Clutch Status**: Shows whether clutch is engaged or disengaged
- **Lock Status**: Shows whether clutch is manually locked
- **Limit Switches**: Shows status of forward and reverse rotation limits
- **Control Buttons**: 
  - Lock/Unlock Clutch toggle
  - Emergency Stop button

### Real-time Updates
All clutch status information is updated in real-time via WebSocket connection, providing immediate feedback on clutch state changes and limit switch activations.

## Safety Features

### Multiple Protection Layers

1. **Hardware Limit Switches**: Physical switches prevent mechanical over-rotation
2. **Software Limit Tracking**: Software prevents commands in blocked directions
3. **Automatic Clutch Control**: Clutch automatically disengages when motor stops
4. **Manual Override**: Manual clutch lock for maintenance and debugging
5. **Emergency Stop**: Immediate disengagement with lock for safety situations

### Error Handling

- **GPIO Initialization Failures**: Graceful degradation if GPIO setup fails
- **Limit Switch Malfunctions**: Continues operation with logging of issues
- **Clutch Engagement Failures**: Motor commands are blocked if clutch fails to engage
- **IOController Unavailable**: System operates without clutch control if IOController is not available

## Usage Examples

### Basic Usage with Clutch Control

```python
#!/usr/bin/env python3
import time
from adafruit_motor import stepper
from io_controller import IOController
from motor_drivers.motorkit_stepper_proxy import MotorKitStepperProxy

# Initialize components
io_controller = IOController()
motor = MotorKitStepperProxy(
    stepper_num=1,
    stepping_style=stepper.SINGLE,
    io_controller=io_controller,
    clutch_output_pin=14,
    forward_limit_pin=23,
    reverse_limit_pin=24
)

try:
    # Start motor driver
    motor.start()
    
    # Normal operation - clutch automatically engages/disengages
    motor.set_speed("forward", 0.5)  # Clutch engages automatically
    time.sleep(3)
    motor.set_speed("stopped", 0.0)  # Clutch disengages automatically
    
    # Manual clutch control
    motor.set_clutch_lock(True)      # Lock clutch manually
    motor.set_speed("forward", 0.3)  # This will fail - clutch is locked
    motor.set_clutch_lock(False)     # Unlock clutch
    motor.set_speed("forward", 0.3)  # This will work
    
    # Emergency stop
    motor.emergency_disengage()      # Immediate stop and lock
    
finally:
    motor.stop()
    io_controller.shutdown()
```

### Integration with YawController

The clutch system can be integrated with the existing YawController by using a MotorKitStepperProxy with clutch control:

```python
# In yaw_controller.py initialization
if self.motor_type == "motorkit_stepper_clutch":
    self.motor_driver = MotorKitStepperProxy(
        stepper_num=1,
        stepping_style=stepper.SINGLE,
        io_controller=io_controller,  # Pass IOController instance
        clutch_output_pin=14,
        forward_limit_pin=23,
        reverse_limit_pin=24
    )
```

## Testing

### Test Script
Use the provided test script to verify clutch functionality:

```bash
# Test with clutch control
python3 test_clutch_stepper.py

# Test without clutch control (for comparison)
python3 test_clutch_stepper.py --no-clutch
```

### Test Scenarios
The test script covers:
1. Basic motor movement with automatic clutch control
2. Manual clutch lock/unlock functionality
3. Emergency disengagement
4. Direction reversal with clutch control
5. Limit switch simulation (if hardware is connected)

## Configuration

### GPIO Pin Configuration
Adjust the GPIO pin assignments in your initialization code to match your hardware setup:

```python
# Example pin assignments (adjust for your hardware)
clutch_output_pin = 14      # GPIO pin to control clutch
forward_limit_pin = 23      # GPIO pin for forward limit switch  
reverse_limit_pin = 24      # GPIO pin for reverse limit switch
```

### Hardware Setup
1. Connect clutch control circuit to the specified output GPIO pin
2. Connect reed switches to the specified input GPIO pins
3. Ensure proper pull-up resistor configuration (handled in software)
4. Test limit switch operation before running motor

## Troubleshooting

### Common Issues

**Clutch Not Engaging:**
- Check GPIO pin connections
- Verify IOController initialization
- Check clutch lock status
- Review console logs for error messages

**Limit Switches Not Working:**
- Verify GPIO pin assignments
- Check reed switch connections
- Test switch operation manually
- Check pull-up resistor configuration

**Motor Won't Move:**
- Check if clutch is manually locked
- Verify limit switch states
- Check for GPIO initialization errors
- Review motor driver status

### Debug Information
Enable debug logging to troubleshoot issues:
- Check console output for clutch engagement/disengagement messages
- Monitor GPIO event logs for limit switch activations
- Use the web interface to view real-time clutch status
- Check motor driver statistics for detailed information

## Future Enhancements

Potential improvements to the clutch control system:

1. **Multiple Clutch Support**: Support for multiple stepper motors with individual clutch control
2. **Configurable Limit Behavior**: Different responses to limit switch activation
3. **Clutch Health Monitoring**: Detection of clutch mechanism failures
4. **Advanced Safety Features**: Integration with other safety systems
5. **Performance Optimization**: Reduced GPIO polling overhead
6. **Configuration File Support**: External configuration for pin assignments

## Conclusion

The clutch control system provides a robust and safe method for controlling stepper motor engagement in the HappyChair animatronic controller. With automatic clutch management, limit switch protection, and manual override capabilities, it ensures reliable operation while preventing mechanical damage.

The system integrates seamlessly with the existing architecture and provides both programmatic and web-based control interfaces for maximum flexibility and ease of use.
