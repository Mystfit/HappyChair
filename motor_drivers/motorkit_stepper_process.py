"""
MotorKit stepper driver subprocess implementation for isolated I2C control.
Runs in a separate process to avoid GIL-related timing issues.
"""

import os
import signal
import time
import multiprocessing
import board
from adafruit_motor import stepper
from adafruit_motorkit import MotorKit


class MotorKitStepperProcess:
    """
    Subprocess worker that handles actual MotorKit stepper control.
    Runs in isolation to avoid GIL interference with timing-critical operations.
    """
    
    def __init__(self, command_queue, stepper_num=1, stepping_style=stepper.SINGLE):
        self.command_queue = command_queue
        self.stepper_num = stepper_num
        self.stepping_style = stepping_style
        
        # MotorKit control
        self.motor_kit = None
        self.stepper_motor = None
        
        # Speed mapping parameters
        self.min_frequency = 50   # Hz (steps per second)
        self.max_frequency = 500  # Hz (steps per second)
        
        # Current state
        self.enabled = False
        self.current_speed = 0.0
        self.current_direction = "stopped"
        self.current_frequency = 0
        self.stepping_active = False
        
        # Process control
        self.running = True
        
        print(f"MotorKitStepperProcess: Initialized (PID: {os.getpid()})")
    
    def run(self):
        """Main process loop - handles commands from queue"""
        # Set up signal handling for clean shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print("MotorKitStepperProcess: Starting command processing loop")
        
        try:
            while self.running:
                try:
                    # Process commands with timeout to allow periodic checks
                    if not self.command_queue.empty():
                        command = self.command_queue.get(timeout=0.1)
                        self._process_command(command)
                    else:
                        # If stepping is active, continue stepping
                        if self.stepping_active:
                            self._perform_step()
                        else:
                            time.sleep(0.01)  # Small sleep to prevent busy waiting
                        
                except multiprocessing.TimeoutError:
                    # Timeout is normal, continue loop
                    continue
                except Exception as e:
                    print(f"MotorKitStepperProcess: Error processing command: {e}")
                    continue
                    
        except KeyboardInterrupt:
            print("MotorKitStepperProcess: Received keyboard interrupt")
        finally:
            self._cleanup()
            print("MotorKitStepperProcess: Process terminated")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"MotorKitStepperProcess: Received signal {signum}")
        self.running = False
    
    def _process_command(self, command):
        """Process a command from the queue"""
        if not isinstance(command, dict):
            print(f"MotorKitStepperProcess: Invalid command format: {command}")
            return
        
        action = command.get('action')
        params = command.get('params', {})
        
        try:
            if action == 'start':
                self._handle_start()
            elif action == 'stop':
                self._handle_stop()
            elif action == 'set_speed':
                direction = params.get('direction', 'stopped')
                speed = params.get('speed', 0.0)
                self._handle_set_speed(direction, speed)
            elif action == 'cleanup':
                self.running = False
            else:
                print(f"MotorKitStepperProcess: Unknown action: {action}")
                
        except Exception as e:
            print(f"MotorKitStepperProcess: Error handling {action}: {e}")
    
    def _handle_start(self):
        """Initialize MotorKit hardware"""
        if self.enabled:
            print("MotorKitStepperProcess: Already started")
            return
        
        try:
            # Initialize MotorKit
            self.motor_kit = MotorKit(i2c=board.I2C())
            
            # Get stepper motor reference
            if self.stepper_num == 1:
                self.stepper_motor = self.motor_kit.stepper1
            elif self.stepper_num == 2:
                self.stepper_motor = self.motor_kit.stepper2
            else:
                raise ValueError(f"Invalid stepper number: {self.stepper_num}. Use 1 or 2.")
            
            # Release stepper to ensure it's in a known state
            self.stepper_motor.release()
            
            self.enabled = True
            print("MotorKitStepperProcess: MotorKit initialized successfully")
            
        except Exception as e:
            print(f"MotorKitStepperProcess: Error initializing MotorKit: {e}")
            self._cleanup_motorkit()
    
    def _handle_stop(self):
        """Stop stepper motor"""
        if not self.enabled:
            return
        
        print("MotorKitStepperProcess: Stopping stepper motor")
        
        # Stop stepping
        self.stepping_active = False
        
        # Update state
        self.current_direction = "stopped"
        self.current_speed = 0.0
        self.current_frequency = 0
        
        # Release stepper motor
        try:
            if self.stepper_motor:
                self.stepper_motor.release()
        except Exception as e:
            print(f"MotorKitStepperProcess: Error releasing stepper: {e}")
    
    def _handle_set_speed(self, direction, speed):
        """Set stepper direction and speed"""
        if not self.enabled:
            print("MotorKitStepperProcess: Cannot set speed - not initialized")
            return
        
        # Clamp speed to valid range
        speed = max(0.0, min(1.0, speed))
        
        try:
            if direction == "stopped" or speed <= 0:
                self.stepping_active = False
                self.current_frequency = 0
                self.current_speed = speed
                self.current_direction = direction
                
                # Release stepper when stopped
                if self.stepper_motor:
                    self.stepper_motor.release()
            else:
                # Calculate step frequency from speed
                frequency = self.min_frequency + (speed * (self.max_frequency - self.min_frequency))
                self.current_frequency = frequency
                
                # Calculate step interval
                self.step_interval = 1.0 / frequency
                self.last_step_time = time.time()
                
                # Set direction for stepping
                if direction == "forward":
                    self.step_direction = stepper.FORWARD
                elif direction == "reverse":
                    self.step_direction = stepper.BACKWARD
                else:
                    print(f"MotorKitStepperProcess: Invalid direction: {direction}")
                    return
                
                # Update state
                self.current_speed = speed
                self.current_direction = direction
                self.stepping_active = True
            
            print(f"MotorKitStepperProcess: Set direction={direction}, speed={speed:.3f}, frequency={self.current_frequency:.1f}Hz")
            
        except Exception as e:
            print(f"MotorKitStepperProcess: Error setting speed: {e}")
    
    def _perform_step(self):
        """Perform a single step if enough time has elapsed"""
        if not self.stepping_active or not self.stepper_motor:
            return
        
        current_time = time.time()
        
        # Check if it's time for the next step
        if current_time - self.last_step_time >= self.step_interval:
            try:
                # Perform one step
                self.stepper_motor.onestep(
                    direction=self.step_direction,
                    style=self.stepping_style
                )
                self.last_step_time = current_time
                
            except Exception as e:
                print(f"MotorKitStepperProcess: Error performing step: {e}")
                self.stepping_active = False
        else:
            # Sleep for a short time to prevent busy waiting
            # Calculate how long to sleep (but not more than 1ms)
            sleep_time = min(0.001, (self.step_interval - (current_time - self.last_step_time)) * 0.5)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _cleanup_motorkit(self):
        """Cleanup MotorKit resources"""
        try:
            # Stop stepping
            self.stepping_active = False
            
            # Release stepper motor
            if self.stepper_motor:
                try:
                    self.stepper_motor.release()
                except Exception as e:
                    print(f"MotorKitStepperProcess: Error releasing stepper: {e}")
                finally:
                    self.stepper_motor = None
            
            # Clear MotorKit reference
            self.motor_kit = None
            
        except Exception as e:
            print(f"MotorKitStepperProcess: Error during MotorKit cleanup: {e}")
    
    def _cleanup(self):
        """Final cleanup before process termination"""
        print("MotorKitStepperProcess: Performing final cleanup")
        self._cleanup_motorkit()
        self.enabled = False


def run_motorkit_stepper_process(command_queue, stepper_num=1, stepping_style=stepper.SINGLE):
    """
    Entry point for the MotorKit stepper subprocess.
    """
    try:
        process = MotorKitStepperProcess(command_queue, stepper_num, stepping_style)
        process.run()
    except Exception as e:
        print(f"MotorKitStepperProcess: Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Test standalone execution
    import multiprocessing
    
    queue = multiprocessing.Queue()
    
    try:
        run_motorkit_stepper_process(queue)
    except KeyboardInterrupt:
        print("Process interrupted")
