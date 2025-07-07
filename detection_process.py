#!/usr/bin/env python3
"""
Standalone detection process for person detection.
Runs GStreamer pipeline in a separate process to avoid GIL contention.
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import sys
import signal
import time
import multiprocessing
import numpy as np
import cv2
import hailo

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
    get_default_parser,
    detect_hailo_arch
)

from hailo_apps_infra.gstreamer_helper_pipelines import(
    QUEUE,
    SOURCE_PIPELINE,
    INFERENCE_PIPELINE,
    INFERENCE_PIPELINE_WRAPPER,
    TRACKER_PIPELINE,
    USER_CALLBACK_PIPELINE,
    DISPLAY_PIPELINE,
)
from hailo_apps_infra.gstreamer_app import (
    GStreamerApp,
    app_callback_class,
    dummy_callback
)

from shared_memory_manager import SharedFrameBuffer, DetectionResultsQueue


# -----------------------------------------------------------------------------------------------
# GStreamerDetectionHeadlessApp - copied from persondetection.py
# -----------------------------------------------------------------------------------------------

class GStreamerDetectionHeadlessApp(GStreamerApp):
    def __init__(self, app_callback, user_data, parser=None):
        if parser == None:
            parser = get_default_parser()
        parser.add_argument(
            "--labels-json",
            default=None,
            help="Path to costume labels JSON file",
        )
        # Call the parent class constructor
        super().__init__(parser, user_data)
        # Additional initialization code can be added here
        # Set Hailo parameters these parameters should be set based on the model used
        self.batch_size = 2
        nms_score_threshold = 0.3
        nms_iou_threshold = 0.45

        # Make streamer app headless by dumping video to a fake sink
        self.video_sink = "fakesink"
        self.user_data.use_frame = True

        # Determine the architecture if not specified
        if self.options_menu.arch is None:
            detected_arch = detect_hailo_arch()
            if detected_arch is None:
                raise ValueError("Could not auto-detect Hailo architecture. Please specify --arch manually.")
            self.arch = detected_arch
            print(f"Auto-detected Hailo architecture: {self.arch}")
        else:
            self.arch = self.options_menu.arch


        if self.options_menu.hef_path is not None:
            self.hef_path = self.options_menu.hef_path
        # Set the HEF file path based on the arch
        elif self.arch == "hailo8":
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8m.hef')
        else:  # hailo8l
            self.hef_path = os.path.join(self.current_path, '../resources/yolov8s_h8l.hef')

        # Set the post-processing shared object file
        self.post_process_so = os.path.join(self.current_path, '../resources/libyolo_hailortpp_postprocess.so')
        self.post_function_name = "filter_letterbox"
        # User-defined label JSON file
        self.labels_json = self.options_menu.labels_json

        self.app_callback = app_callback

        self.thresholds_str = (
            f"nms-score-threshold={nms_score_threshold} "
            f"nms-iou-threshold={nms_iou_threshold} "
            f"output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )

        self.create_pipeline()

    def get_pipeline_string(self):
        source_pipeline = SOURCE_PIPELINE(self.video_source, self.video_width, self.video_height)
        detection_pipeline = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            post_function_name=self.post_function_name,
            batch_size=self.batch_size,
            config_json=self.labels_json,
            additional_params=self.thresholds_str)
        detection_pipeline_wrapper = INFERENCE_PIPELINE_WRAPPER(detection_pipeline)
        tracker_pipeline = TRACKER_PIPELINE(class_id=1)
        user_callback_pipeline = USER_CALLBACK_PIPELINE()
        display_pipeline = DISPLAY_PIPELINE(video_sink=self.video_sink, sync=self.sync, show_fps=self.show_fps)

        pipeline_string = (
            f'{source_pipeline} ! '
            f'{detection_pipeline_wrapper} ! '
            f'{tracker_pipeline} ! '
            f'{user_callback_pipeline} ! '
            f'{display_pipeline}'
        )
        print(f"Detection process pipeline: {pipeline_string}")
        return pipeline_string


class DetectionCallbackHandler(app_callback_class):
    """
    Callback handler that manages shared memory and detection results.
    """
    
    def __init__(self, shared_buffer, results_queue):
        super().__init__()
        self.shared_buffer = shared_buffer
        self.results_queue = DetectionResultsQueue(results_queue)
        self.use_frame = True
        
        # Camera and control parameters
        self.camera_width = 1280
        self.camera_height = 720
        self.center_x = self.camera_width // 2  # 640px
        self.dead_zone_width = 400  # 400px total dead zone
        self.dead_zone_half = self.dead_zone_width // 2  # ±200px from center
        self.screen_margin = 100  # 100px margin on each side
        
        # Person tracking (moved from YawController)
        self.tracked_person_id = None
        
        # Visual debugging colors (BGR format for OpenCV)
        self.left_movement_color = (0, 255, 255)  # Yellow in BGR
        self.right_movement_color = (0, 165, 255)  # Orange in BGR
        self.tracked_person_color = (255, 255, 0)  # Cyan in BGR
        self.overlay_opacity = 0.25
        self.speed_bar_height = 40
        
        # Movement control parameters
        self.max_speed = 1.0
        self.min_speed = 0.1
        
        # Performance tracking
        self.frame_times = []
        self.last_stats_time = time.time()
        self.stats_interval = 1.0  # Report stats every second
        
    def update_fps_stats(self):
        """Update FPS statistics"""
        current_time = time.time()
        self.frame_times.append(current_time)
        
        # Keep only recent frame times (last 2 seconds)
        cutoff_time = current_time - 2.0
        self.frame_times = [t for t in self.frame_times if t > cutoff_time]
        
        # Calculate FPS
        if len(self.frame_times) > 1:
            time_span = self.frame_times[-1] - self.frame_times[0]
            fps = (len(self.frame_times) - 1) / time_span if time_span > 0 else 0
        else:
            fps = 0
            
        return fps
    
    def _find_target_person(self, detections):
        """Find the person to track based on tracking logic"""
        if not detections:
            return None
        
        # If we have a tracked person, try to find them
        if self.tracked_person_id is not None:
            for detection in detections:
                if detection.get('track_id') == self.tracked_person_id:
                    return detection
            
            # Tracked person not found, reset tracking
            print(f"DetectionProcess: Lost track of person {self.tracked_person_id}")
            self.tracked_person_id = None
        
        # No tracked person or lost track, find first available person
        for detection in detections:
            track_id = detection.get('track_id', 0)
            if track_id > 0:
                self.tracked_person_id = track_id
                print(f"DetectionProcess: Now tracking person {track_id}")
                return detection
        
        return None
    
    def _calculate_movement_parameters(self, detection):
        """Calculate movement direction and normalized speed for a person"""
        bbox = detection.get('bbox', (0, 0, 0, 0))
        x, y, w, h = bbox
        x *= self.camera_width  # Scale bounding box x position to camera width
        y *= self.camera_height   # Scale bounding box y position to camera height
        w *= self.camera_width  # Scale bounding box width to camera width
        h *= self.camera_height   # Scale bounding box height to camera height

        # Calculate person's center X position
        person_center_x = x + (w / 2)
        
        # Calculate distance from camera center
        distance_from_center = person_center_x - self.center_x
        
        # Check if person is in dead zone
        if abs(distance_from_center) <= self.dead_zone_half:
            # Person is in dead zone, no movement
            return "stopped", 0.0
        
        # Calculate movement speed based on distance from dead zone edge
        if distance_from_center < -self.dead_zone_half:
            # Person is on the left, should move left
            distance_from_dead_zone = abs(distance_from_center) - self.dead_zone_half
            # Apply screen margin to reduce max distance
            max_distance = (self.center_x - self.dead_zone_half) - self.screen_margin
            speed = self._calculate_normalized_speed(distance_from_dead_zone, max_distance)
            return "left", speed
            
        elif distance_from_center > self.dead_zone_half:
            # Person is on the right, should move right
            distance_from_dead_zone = distance_from_center - self.dead_zone_half
            # Apply screen margin to reduce max distance
            max_distance = (self.center_x - self.dead_zone_half) - self.screen_margin
            speed = self._calculate_normalized_speed(distance_from_dead_zone, max_distance)
            return "right", speed
        
        return "stopped", 0.0
    
    def _calculate_normalized_speed(self, distance_from_dead_zone, max_distance):
        """Calculate normalized speed based on distance from dead zone"""
        if max_distance <= 0:
            return self.max_speed
        
        # Normalize distance (0.0 to 1.0)
        normalized_distance = min(distance_from_dead_zone / max_distance, 1.0)
        
        # Apply speed scaling (min to max speed)
        speed = self.min_speed + (normalized_distance * (self.max_speed - self.min_speed))
        
        return min(speed, self.max_speed)
    
    def _draw_direction_indicator(self, frame, direction):
        """Draw semi-transparent rectangle for movement direction"""
        if direction == "stopped":
            return
        
        height, width = frame.shape[:2]
        overlay = frame.copy()
        
        if direction == "left":
            # Yellow overlay on left half
            cv2.rectangle(overlay, (0, 0), (width // 2, height), self.left_movement_color, -1)
        elif direction == "right":
            # Orange overlay on right half
            cv2.rectangle(overlay, (width // 2, 0), (width, height), self.right_movement_color, -1)
        
        # Blend with original frame
        cv2.addWeighted(overlay, self.overlay_opacity, frame, 1 - self.overlay_opacity, 0, frame)
    
    def _draw_speed_indicator(self, frame, direction, normalized_speed):
        """Draw speed indicator bar at bottom of frame"""
        if direction == "stopped" or normalized_speed <= 0:
            return
        
        height, width = frame.shape[:2]
        
        # Calculate bar dimensions
        bar_y = height - self.speed_bar_height - 10  # 10px from bottom
        bar_height = self.speed_bar_height
        
        # Calculate dead zone boundaries
        dead_zone_left = self.center_x - self.dead_zone_half
        dead_zone_right = self.center_x + self.dead_zone_half
        
        # Calculate active area boundaries (with margins)
        active_left = self.screen_margin
        active_right = width - self.screen_margin
        
        if direction == "left":
            # Bar starts from left edge of dead zone and extends left
            bar_right = dead_zone_left
            bar_width = int((dead_zone_left - active_left) * normalized_speed)
            bar_left = bar_right - bar_width
            color = self.left_movement_color
        else:  # direction == "right"
            # Bar starts from right edge of dead zone and extends right
            bar_left = dead_zone_right
            bar_width = int((active_right - dead_zone_right) * normalized_speed)
            bar_right = bar_left + bar_width
            color = self.right_movement_color
        
        # Draw the speed bar
        cv2.rectangle(frame, (bar_left, bar_y), (bar_right, bar_y + bar_height), color, -1)
        
        # Draw border around the bar
        cv2.rectangle(frame, (bar_left, bar_y), (bar_right, bar_y + bar_height), (255, 255, 255), 2)


def detection_callback(pad, info, user_data):
    """
    Main detection callback function.
    Processes frames and detections, writes to shared memory.
    """
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    # Increment frame counter
    user_data.increment()
    
    # Get the caps from the pad
    format, width, height = get_caps_from_pad(pad)
    
    # Get video frame
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)
    
    # Get detections from buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    # Process detections
    person_count = 0
    detection_list = []
    
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        
        if label == "person":
            # Get track ID
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            
            person_count += 1
            
            # Store detection info
            detection_info = {
                'bbox': (bbox.xmin(), bbox.ymin(), bbox.xmax() - bbox.xmin(), bbox.ymax() - bbox.ymin()),
                'confidence': confidence,
                'track_id': track_id
            }
            detection_list.append(detection_info)
    
    # Find target person to track
    target_person = user_data._find_target_person(detection_list)
    
    # Calculate movement parameters for tracked person
    movement_direction = "stopped"
    normalized_speed = 0.0
    
    if target_person:
        movement_direction, normalized_speed = user_data._calculate_movement_parameters(target_person)
    
    # Draw bounding boxes and visual debugging on frame
    if frame is not None:
        # Draw direction indicator (semi-transparent overlay)
        user_data._draw_direction_indicator(frame, movement_direction)
        
        # Draw all person bounding boxes
        for detection_info in detection_list:
            bbox = detection_info['bbox']
            track_id = detection_info['track_id']
            confidence = detection_info['confidence']
            
            # Convert normalized coordinates to pixel coordinates
            x = int(bbox[0] * width)
            y = int(bbox[1] * height)
            w = int(bbox[2] * width)
            h = int(bbox[3] * height)
            
            x_min, y_min = x, y
            x_max, y_max = x + w, y + h
            
            # Choose color based on whether this is the tracked person
            if target_person and track_id == target_person.get('track_id'):
                # Tracked person gets cyan color
                box_color = user_data.tracked_person_color
                label_text = f"TRACKED Person {track_id}: {confidence:.2f}"
            else:
                # Other persons get green color
                box_color = (0, 255, 0)
                label_text = f"Person {track_id}: {confidence:.2f}"
            
            # Draw bounding box
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), box_color, 2)
            
            # Draw label and confidence
            cv2.putText(frame, label_text, (x_min, y_min - 10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)
        
        # Draw speed indicator bar
        user_data._draw_speed_indicator(frame, movement_direction, normalized_speed)
    
    # Update FPS statistics
    fps = user_data.update_fps_stats()
    
    # Process frame for shared memory
    if frame is not None:
        # Add text overlays
        cv2.putText(frame, f"Persons: {person_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Add tracking info
        if target_person:
            tracking_text = f"Tracking: {user_data.tracked_person_id} | Dir: {movement_direction} | Speed: {normalized_speed:.2f}"
            cv2.putText(frame, tracking_text, (10, 110), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.putText(frame, "Detection Process", (10, height - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        # Convert RGB to BGR for consistency
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Write frame to shared memory
        user_data.shared_buffer.write_frame(frame_bgr)
    
    # Send detection results with movement parameters
    user_data.results_queue.put_detection_results(
        person_count, 
        detection_list, 
        fps,
        movement_direction=movement_direction,
        normalized_speed=normalized_speed,
        tracked_person_id=user_data.tracked_person_id
    )
    
    # Periodic stats reporting
    current_time = time.time()
    if current_time - user_data.last_stats_time > user_data.stats_interval:
        tracking_info = f", Tracking: {user_data.tracked_person_id}, Dir: {movement_direction}, Speed: {normalized_speed:.2f}" if target_person else ""
        print(f"Detection Process - Frame: {user_data.get_count()}, Persons: {person_count}, FPS: {fps:.1f}{tracking_info}")
        user_data.last_stats_time = current_time
    
    return Gst.PadProbeReturn.OK


def run_detection_process(shared_buffer_name, results_queue, stop_event):
    """
    Main function for the detection process.
    """
    print(f"Starting detection process (PID: {os.getpid()})")
    
    # Set up signal handling
    def signal_handler(signum, frame):
        print("Detection process received shutdown signal")
        stop_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create shared memory buffer
        shared_buffer = SharedFrameBuffer(shared_buffer_name)
        if not shared_buffer.create_buffer():
            print("Failed to create shared memory buffer")
            return
        
        # Create user data for callback
        user_data = DetectionCallbackHandler(shared_buffer, results_queue)
        
        # Create and run detection app with Pi camera input
        import sys
        sys.argv = ['detection_process.py', '--input', 'rpi', '--disable-sync']
        app = GStreamerDetectionHeadlessApp(detection_callback, user_data)
        
        print("Detection process starting GStreamer pipeline...")
        
        # Run the app in a separate thread so we can check stop_event
        import threading
        app_thread = threading.Thread(target=app.run)
        app_thread.daemon = True
        app_thread.start()
        
        # Wait for stop signal
        while not stop_event.is_set() and app_thread.is_alive():
            time.sleep(0.1)
        
        print("Detection process shutting down...")
        # GStreamerApp doesn't have a stop() method, so we'll let the thread finish naturally
        # The app will stop when the main loop exits
        
        # Wait for app thread to finish
        app_thread.join(timeout=5.0)
        
        # If thread is still alive, we'll let the process termination handle cleanup
        if app_thread.is_alive():
            print("App thread still running, process will terminate")
        
    except Exception as e:
        print(f"Error in detection process: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'shared_buffer' in locals():
            shared_buffer.close()
            # Unlink the shared memory since we created it
            shared_buffer.unlink()
        print("Detection process terminated")


if __name__ == "__main__":
    # This allows the script to be run standalone for testing
    import multiprocessing
    
    # Create test queue and event
    queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()
    
    try:
        run_detection_process("test_detection_buffer", queue, stop_event)
    except KeyboardInterrupt:
        print("Stopping detection process...")
        stop_event.set()
