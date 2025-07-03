"""
IOController class for managing input/output operations on Raspberry Pi.
Handles camera detection, GPIO pin monitoring, and event dispatching.
"""

import threading
import time
import lgpio
from typing import Optional, Dict, Any, List, Callable
from detection_multiprocess import PersonDetectionMultiprocess


class IOController:
    """
    Controls input/output operations including camera detection and GPIO monitoring.
    Dispatches events to registered callbacks for decoupled system architecture.
    """
    
    def __init__(self, buffer_name: str = "happychair_detection_buffer"):
        self.buffer_name = buffer_name
        
        # Detection system (moved from YawController)
        self.person_detector = None
        
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
        
        # Statistics
        self.unique_people_seen = set()
        
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
    
    def register_pin(self, pin_number: int, name: str = None, bias: str = 'pull_up') -> bool:
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
                if bias == 'pull_up':
                    lgpio.gpio_claim_input(self.gpio_handle, pin_number, lgpio.SET_PULL_UP)
                elif bias == 'pull_down':
                    lgpio.gpio_claim_input(self.gpio_handle, pin_number, lgpio.SET_PULL_DOWN)
                else:  # floating
                    lgpio.gpio_claim_input(self.gpio_handle, pin_number, lgpio.SET_PULL_NONE)
                
                # Read initial state
                initial_state = lgpio.gpio_read(self.gpio_handle, pin_number)
                
                # Store pin configuration
                self.registered_pins[pin_number] = {
                    'name': name or f'Pin {pin_number}',
                    'bias': bias,
                    'state': initial_state,
                    'last_changed': time.time(),
                    'previous_state': initial_state
                }
                
                print(f"IOController: Registered pin {pin_number} ({name}) with {bias} bias, initial state: {initial_state}")
                
                # Start monitoring thread if not already running
                if not self.gpio_thread_running:
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
    
    # Camera detection methods (moved from YawController)
    def start_detection(self) -> bool:
        """Start the person detection system"""
        try:
            if not self.person_detector:
                self.person_detector = PersonDetectionMultiprocess(self.buffer_name)
            
            if self.person_detector.start_detection():
                print("IOController: Detection started successfully")
                return True
            else:
                print("IOController: Failed to start detection")
                return False
                
        except Exception as e:
            print(f"IOController: Error starting detection: {e}")
            return False
    
    def stop_detection(self) -> bool:
        """Stop the person detection system"""
        try:
            if self.person_detector and self.person_detector.stop_detection():
                print("IOController: Detection stopped successfully")
                return True
            else:
                print("IOController: Failed to stop detection or not running")
                return False
                
        except Exception as e:
            print(f"IOController: Error stopping detection: {e}")
            return False
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        if not self.person_detector:
            return {
                'person_count': 0,
                'unique_people': 0,
                'last_update': 0,
                'fps': 0,
                'detections': []
            }
        
        # Get base stats from detector
        stats = self.person_detector.get_detection_stats()
        
        # Update unique people count
        detections = stats.get('detections', [])
        for detection in detections:
            track_id = detection.get('track_id', 0)
            if track_id > 0:
                self.unique_people_seen.add(track_id)
        
        # Add IOController specific stats
        stats.update({
            'unique_people': len(self.unique_people_seen)
        })
        
        # Dispatch detection event if there are detections
        if detections:
            self.dispatch_event('person_detected', {
                'detections': detections,
                'person_count': stats.get('person_count', 0),
                'unique_people': len(self.unique_people_seen)
            })
        
        return stats
    
    def get_latest_frame(self):
        """Get the latest frame from detection system"""
        if self.person_detector:
            return self.person_detector.get_latest_frame()
        return None
    
    def is_detection_running(self) -> bool:
        """Check if detection is running"""
        if self.person_detector:
            return self.person_detector.is_running()
        return False
    
    def restart_detection(self) -> bool:
        """Restart the detection system"""
        if self.person_detector:
            return self.person_detector.restart_detection()
        return False
    
    def get_process_info(self) -> Dict:
        """Get detection process information"""
        if self.person_detector:
            return self.person_detector.get_process_info()
        return {'status': 'not_initialized'}
    
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
        
        # Stop detection
        if self.person_detector:
            self.person_detector.shutdown()
        
        print("IOController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()
