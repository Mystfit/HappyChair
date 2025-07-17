"""
AnalogController class for managing analog sensor input operations using ADS1015 ADC.
Handles analog channel monitoring and event dispatching.
"""

import threading
import time
import board
import busio
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from collections import deque
from typing import Optional, Dict, Any, List, Callable
import statistics


class AnalogController:
    """
    Controls analog sensor input operations using ADS1015 ADC.
    Dispatches events to registered callbacks for decoupled system architecture.
    """
    
    def __init__(self):
        # I2C and ADC management
        self.i2c = None
        self.ads = None
        self.adc_initialized = False
        
        # Channel management
        self.registered_channels = {}  # channel_number: {name, gain, data_rate, analog_in, current_value, history, stats}
        
        # Event system
        self.event_callbacks = []  # List of callback functions
        
        # Threading for analog monitoring
        self.analog_thread = None
        self.analog_thread_running = False
        self.analog_lock = threading.Lock()
        
        # Configuration
        self.default_history_size = 100
        self.default_threshold = 0.01  # Minimum change to trigger event
        self.sampling_interval = 0.01  # 5ms between samples
        
        print("AnalogController initialized")
    
    def initialize_adc(self):
        """Initialize I2C bus and ADS1015 ADC"""
        if not self.adc_initialized:
            try:
                # Create the I2C bus
                self.i2c = busio.I2C(board.SCL, board.SDA)
                
                # Create the ADC object using the I2C bus
                self.ads = ADS.ADS1015(self.i2c)
                
                self.adc_initialized = True
                print("AnalogController: ADC initialized with ADS1015")
                return True
            except Exception as e:
                print(f"AnalogController: Error initializing ADC: {e}")
                return False
        return True
    
    def register_channel(self, channel: int, name: str = None, gain: int = 1, 
                        data_rate: int = 128, history_size: int = None, 
                        threshold: float = None) -> bool:
        """
        Register an analog channel for monitoring using ADS1015
        
        Args:
            channel: ADC channel number (0-3 for ADS1015)
            name: Optional name for the channel
            gain: PGA gain (1, 2, 4, 8, 16)
            data_rate: Samples per second (128, 250, 490, 920, 1600, 2400, 3300)
            history_size: Number of historical values to keep
            threshold: Minimum change to trigger events
        """
        if not self.initialize_adc():
            return False
        
        if channel < 0 or channel > 3:
            print(f"AnalogController: Invalid channel {channel}. Must be 0-3")
            return False
        
        try:
            with self.analog_lock:
                # Set default values
                if history_size is None:
                    history_size = self.default_history_size
                if threshold is None:
                    threshold = self.default_threshold
                
                # Create analog input for the channel
                channel_pins = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
                analog_in = AnalogIn(self.ads, channel_pins[channel])
                
                # Configure gain and data rate
                self.ads.gain = gain
                self.ads.data_rate = data_rate
                
                # Read initial value
                initial_raw = analog_in.value
                initial_voltage = analog_in.voltage
                
                # Store channel configuration
                self.registered_channels[channel] = {
                    'name': name or f'Channel {channel}',
                    'gain': gain,
                    'data_rate': data_rate,
                    'analog_in': analog_in,
                    'current_raw': initial_raw,
                    'current_voltage': initial_voltage,
                    'last_changed': time.time(),
                    'threshold': threshold,
                    'history_raw': deque(maxlen=history_size),
                    'history_voltage': deque(maxlen=history_size),
                    'stats': {
                        'min_raw': initial_raw,
                        'max_raw': initial_raw,
                        'min_voltage': initial_voltage,
                        'max_voltage': initial_voltage,
                        'avg_raw': initial_raw,
                        'avg_voltage': initial_voltage
                    }
                }
                
                # Add initial values to history
                self.registered_channels[channel]['history_raw'].append(initial_raw)
                self.registered_channels[channel]['history_voltage'].append(initial_voltage)
                
                print(f"AnalogController: Registered channel {channel} ({name}) - Initial: {initial_raw} raw, {initial_voltage:.3f}V")
                
                # Start monitoring thread if not already running
                if not self.analog_thread_running:
                    self._start_analog_monitoring()
                
                # Dispatch initial channel registered event
                self.dispatch_event('channel_registered', {
                    'channel': channel,
                    'name': self.registered_channels[channel]['name'],
                    'raw_value': initial_raw,
                    'voltage': initial_voltage,
                    'gain': gain,
                    'data_rate': data_rate
                })
                
                return True
                
        except Exception as e:
            print(f"AnalogController: Error registering channel {channel}: {e}")
            return False
    
    def _start_analog_monitoring(self):
        """Start analog monitoring thread"""
        self.analog_thread_running = True
        self.analog_thread = threading.Thread(target=self._analog_monitor_loop, daemon=True)
        self.analog_thread.start()
        print("AnalogController: Analog monitoring thread started")
    
    def _analog_monitor_loop(self):
        """Monitor analog channel values by sampling"""
        while self.analog_thread_running and self.ads is not None:
            try:
                # Sample all registered channels
                with self.analog_lock:
                    channels_to_check = list(self.registered_channels.keys())
                
                for channel in channels_to_check:
                    try:
                        self._sample_channel(channel)
                    except Exception as e:
                        if self.analog_thread_running:
                            print(f"AnalogController: Error sampling channel {channel}: {e}")
                
                # Sleep for sampling interval
                time.sleep(self.sampling_interval)
                    
            except Exception as e:
                if self.analog_thread_running:
                    print(f"AnalogController: Error in analog monitor loop: {e}")
                time.sleep(0.1)
    
    def _sample_channel(self, channel: int):
        """Sample a single analog channel and update values"""
        try:
            with self.analog_lock:
                if channel in self.registered_channels:
                    channel_info = self.registered_channels[channel]
                    analog_in = channel_info['analog_in']
                    
                    # Read current values
                    new_raw = analog_in.value
                    new_voltage = analog_in.voltage
                    
                    old_raw = channel_info['current_raw']
                    old_voltage = channel_info['current_voltage']
                    
                    # Check if change exceeds threshold
                    voltage_change = abs(new_voltage - old_voltage)
                    if voltage_change >= channel_info['threshold']:
                        # Update current values
                        channel_info['current_raw'] = new_raw
                        channel_info['current_voltage'] = new_voltage
                        channel_info['last_changed'] = time.time()
                        
                        # Add to history
                        channel_info['history_raw'].append(new_raw)
                        channel_info['history_voltage'].append(new_voltage)
                        
                        # Update statistics
                        self._update_channel_stats(channel, new_raw, new_voltage)
                        
                        # Dispatch value changed event
                        self.dispatch_event('channel_changed', {
                            'channel': channel,
                            'name': channel_info['name'],
                            'raw_value': new_raw,
                            'voltage': new_voltage,
                            'previous_raw': old_raw,
                            'previous_voltage': old_voltage,
                            'change': voltage_change,
                            'timestamp': channel_info['last_changed']
                        })
                    else:
                        # Still add to history even if no significant change
                        channel_info['history_raw'].append(new_raw)
                        channel_info['history_voltage'].append(new_voltage)
                        
                        # Update current values for small changes
                        channel_info['current_raw'] = new_raw
                        channel_info['current_voltage'] = new_voltage
                        
                        # Update statistics
                        self._update_channel_stats(channel, new_raw, new_voltage)
                        
        except Exception as e:
            print(f"AnalogController: Error sampling channel {channel}: {e}")
    
    def _update_channel_stats(self, channel: int, raw_value: int, voltage: float):
        """Update statistical information for a channel"""
        try:
            channel_info = self.registered_channels[channel]
            stats = channel_info['stats']
            
            # Update min/max
            stats['min_raw'] = min(stats['min_raw'], raw_value)
            stats['max_raw'] = max(stats['max_raw'], raw_value)
            stats['min_voltage'] = min(stats['min_voltage'], voltage)
            stats['max_voltage'] = max(stats['max_voltage'], voltage)
            
            # Calculate averages from history
            if len(channel_info['history_raw']) > 0:
                stats['avg_raw'] = statistics.mean(channel_info['history_raw'])
                stats['avg_voltage'] = statistics.mean(channel_info['history_voltage'])
            
        except Exception as e:
            print(f"AnalogController: Error updating stats for channel {channel}: {e}")
    
    def get_channel_readings(self) -> Dict[int, Dict]:
        """Get current readings of all registered channels"""
        with self.analog_lock:
            return {
                channel: {
                    'name': info['name'],
                    'raw_value': info['current_raw'],
                    'voltage': info['current_voltage'],
                    'gain': info['gain'],
                    'data_rate': info['data_rate'],
                    'last_changed': info['last_changed'],
                    'stats': info['stats'].copy()
                }
                for channel, info in self.registered_channels.items()
            }
    
    def get_channel_history(self, channel: int, samples: int = None) -> Dict[str, List]:
        """Get historical data for a specific channel"""
        with self.analog_lock:
            if channel not in self.registered_channels:
                return {'raw': [], 'voltage': [], 'timestamps': []}
            
            channel_info = self.registered_channels[channel]
            raw_history = list(channel_info['history_raw'])
            voltage_history = list(channel_info['history_voltage'])
            
            # Limit samples if requested
            if samples and samples < len(raw_history):
                raw_history = raw_history[-samples:]
                voltage_history = voltage_history[-samples:]
            
            # Generate approximate timestamps (assuming regular sampling)
            now = time.time()
            timestamps = [
                now - (len(raw_history) - i - 1) * self.sampling_interval 
                for i in range(len(raw_history))
            ]
            
            return {
                'raw': raw_history,
                'voltage': voltage_history,
                'timestamps': timestamps
            }
    
    def get_all_channel_history(self, samples: int = None) -> Dict[int, Dict]:
        """Get historical data for all channels"""
        return {
            channel: self.get_channel_history(channel, samples)
            for channel in self.registered_channels.keys()
        }
    
    def register_event_callback(self, callback: Callable):
        """Register a callback function for events"""
        if callback not in self.event_callbacks:
            self.event_callbacks.append(callback)
            print(f"AnalogController: Registered event callback: {callback.__name__}")
    
    def unregister_event_callback(self, callback: Callable):
        """Unregister a callback function"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
            print(f"AnalogController: Unregistered event callback: {callback.__name__}")
    
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
                print(f"AnalogController: Error in event callback {callback.__name__}: {e}")
    
    def shutdown(self):
        """Shutdown the AnalogController and cleanup resources"""
        print("AnalogController: Shutting down...")
        
        # Stop analog monitoring
        self.analog_thread_running = False
        if self.analog_thread and self.analog_thread.is_alive():
            self.analog_thread.join(timeout=2.0)
        
        # Cleanup I2C and ADC
        if self.ads is not None:
            try:
                # ADS1015 doesn't require explicit cleanup, but we can clear the reference
                self.ads = None
                self.i2c = None
                print("AnalogController: ADC cleaned up")
            except Exception as e:
                print(f"AnalogController: Error cleaning up ADC: {e}")
        
        print("AnalogController: Shutdown complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.shutdown()