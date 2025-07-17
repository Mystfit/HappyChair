"""
IOController class for managing GPIO input/output operations on Raspberry Pi.
Handles GPIO pin monitoring and event dispatching.
"""

import threading
import time
import lgpio
from typing import Optional, Dict, Any, List, Callable


class IOController:
    """
    Controls GPIO input/output operations and pin monitoring.
    Dispatches events to registered callbacks for decoupled system architecture.
    """
    
    def __init__(self):
        # GPIO pin management
        self.registered_pins = {}  # pin_number: {name, bias, state, last_changed, callback}
        self.gpio_handle = None
        self.gpio_initialized = False
        
        # Event system
        self.event_callbacks = []  # List of callback functions
        
        # Threading for GPIO monitoring
        self.gpio_thread = None
        self.gpio_thread_running = False
        self.gpio_lock = threading.Lock()
        
        print("IOController initialized")
    
    def initialize_gpio(self):
        """Initialize GPIO system using lgpio for Raspberry Pi 5 compatibility"""
        if not self.gpio_initialized:
            try:
                # Open GPIO chip (gpiochip0 for Raspberry Pi)
                self.gpio_handle = lgpio.gpiochip_open(0)
                self.gpio_initialized = True
                print("IOController: GPIO initialized with lgpio")
                return True
            except Exception as e:
                print(f"IOController: Error initializing GPIO: {e}")
                return False
        return True
    
    def register_pin(self, pin_number: int, name: str = None, direction: str = 'input' ,bias: str = '') -> bool:
        """
        Register a GPIO pin for monitoring using lgpio
        
        Args:
            pin_number: GPIO pin number (BCM numbering)
            name: Optional name for the pin
            bias: 'pull_up', 'pull_down', or 'floating'
        """
        if not self.initialize_gpio():
            return False
        
        try:
            with self.gpio_lock:
                # Try to free the pin first in case it's already claimed
                try:
                    lgpio.gpio_free(self.gpio_handle, pin_number)
                    print(f"IOController: Freed previously claimed pin {pin_number}")
                except:
                    pass  # Pin wasn't claimed, which is fine
                
                # Configure pin based on bias using lgpio
                bias_flag = lgpio.SET_PULL_NONE
                if bias == 'pull_up':
                    bias_flag = lgpio.SET_PULL_UP
                elif bias == 'pull_down':
                    bias_flag = lgpio.SET_PULL_DOWN

                # Pin directionality
                if direction == 'output':
                    lgpio.gpio_claim_output(self.gpio_handle, pin_number, bias_flag)
                else:
                    lgpio.gpio_claim_input(self.gpio_handle, pin_number, bias_flag)
                
                # Read initial state
                initial_state = lgpio.gpio_read(self.gpio_handle, pin_number)
                
                # Store pin configuration
                self.registered_pins[pin_number] = {
                    'name': name or f'Pin {pin_number}',
                    'bias': bias,
                    'direction': direction,
                    'state': initial_state,
                    'last_changed': time.time(),
                    'previous_state': initial_state
                }
                
                print(f"IOController: Registered pin {pin_number} ({name}) with {bias} bias, initial state: {initial_state}")
                
                # Start monitoring thread if not already running
                if not self.gpio_thread_running and direction == 'input':
                    self._start_gpio_monitoring()
                
                # Dispatch initial pin state event
                self.dispatch_event('pin_registered', {
                    'pin': pin_number,
                    'name': self.registered_pins[pin_number]['name'],
                    'state': initial_state,
                    'bias': bias
                })
                
                return True
                
        except Exception as e:
            print(f"IOController: Error registering pin {pin_number}: {e}")
            return False
        
    def write_pin(self, pin_number: int, value: int) -> bool:
        """
        Write a value to a GPIO pin
        
        Args:
            pin_number: GPIO pin number (BCM numbering)
            value: 0 or 1 for output pins
        """
        if not self.gpio_initialized or self.gpio_handle is None:
            print("IOController: GPIO not initialized")
            return False
        
        try:
            with self.gpio_lock:
                if pin_number in self.registered_pins and self.registered_pins[pin_number]['direction'] == 'output':
                    lgpio.gpio_write(self.gpio_handle, pin_number, value)
                    print(f"IOController: Wrote {value} to pin {pin_number}")
                    return True
                else:
                    print(f"IOController: Pin {pin_number} is not registered as output")
                    return False
        except Exception as e:
            print(f"IOController: Error writing to pin {pin_number}: {e}")
            return False
    
    def _start_gpio_monitoring(self):
        """Start GPIO monitoring thread for lgpio alerts"""
        self.gpio_thread_running = True
        self.gpio_thread = threading.Thread(target=self._gpio_monitor_loop, daemon=True)
        self.gpio_thread.start()
        print("IOController: GPIO monitoring thread started")
    
    def _gpio_monitor_loop(self):
        """Monitor GPIO pin states by polling"""
        while self.gpio_thread_running and self.gpio_handle is not None:
            try:
                # Poll all registered pins for state changes
                with self.gpio_lock:
                    pins_to_check = list(self.registered_pins.keys())
                
                for pin_number in pins_to_check:
                    try:
                        current_state = lgpio.gpio_read(self.gpio_handle, pin_number)
                        self._handle_gpio_change(pin_number, current_state, int(time.time() * 1000000))
                    except Exception as e:
                        if self.gpio_thread_running:
                            print(f"IOController: Error reading pin {pin_number}: {e}")
                
                # Sleep for a short time to avoid excessive CPU usage
                time.sleep(0.05)  # 50ms polling interval
                    
            except Exception as e:
                if self.gpio_thread_running:  # Only log if we're supposed to be running
                    print(f"IOController: Error in GPIO monitor loop: {e}")
                time.sleep(0.1)
    
    def _handle_gpio_change(self, pin_number: int, new_state: int, timestamp: int):
        """Handle GPIO pin state change"""
        try:
            with self.gpio_lock:
                if pin_number in self.registered_pins:
                    pin_info = self.registered_pins[pin_number]
                    old_state = pin_info['state']
                    
                    if new_state != old_state:
                        # Update pin state
                        pin_info['state'] = new_state
                        pin_info['previous_state'] = old_state
                        pin_info['last_changed'] = time.time()
                        
                        print(f"IOController: Pin {pin_number} ({pin_info['name']}) changed: {old_state} -> {new_state}")
                        
                        # Dispatch pin change event
                        self.dispatch_event('pin_changed', {
                            'pin': pin_number,
                            'name': pin_info['name'],
                            'state': new_state,
                            'previous_state': old_state,
                            'timestamp': pin_info['last_changed']
                        })
                        
        except Exception as e:
            print(f"IOController: Error handling GPIO change for pin {pin_number}: {e}")
    
    def get_pin_states(self) -> Dict[int, Dict]:
        """Get current states of all registered pins"""
        with self.gpio_lock:
            return {
                pin: {
                    'name': info['name'],
                    'direction': info['direction'],
                    'state': info['state'],
                    'bias': info['bias'],
                    'last_changed': info['last_changed']
                }
                for pin, info in self.registered_pins.items()
            }
    
    def register_event_callback(self, callback: Callable):
        """Register a callback function for events"""
        if callback not in self.event_callbacks:
            self.event_callbacks.append(callback)
            print(f"IOController: Registered event callback: {callback.__name__}")
    
    def unregister_event_callback(self, callback: Callable):
        """Unregister a callback function"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
            print(f"IOController: Unregistered event callback: {callback.__name__}")
    
    def dispatch_event(self, event_type: str, data: Dict[str, Any]):
        """Dispatch an event to all registered callbacks"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        }
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"IOController: Error in event callback {callback.__name__}: {e}")
    
    def shutdown(self):
        """Shutdown the IOController and cleanup resources"""
        print("IOController: Shutting down...")
        
        # Stop GPIO monitoring
        self.gpio_thread_running = False
        if self.gpio_thread and self.gpio_thread.is_alive():
            self.gpio_thread.join(timeout=2.0)
        
        # Cleanup GPIO
        if self.gpio_handle is not None:
            try:
                # Close GPIO handle (this automatically frees claimed pins)
                lgpio.gpiochip_close(self.gpio_handle)
                self.gpio_handle = None
                print("IOController: GPIO cleaned up")
            except Exception as e:
                print(f"IOController: Error cleaning up GPIO: {e}")
        
        print("IOController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()
