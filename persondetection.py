import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo
import threading
import time
import multiprocessing

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


# -----------------------------------------------------------------------------------------------
# User Gstreamer Application
# -----------------------------------------------------------------------------------------------

# This class inherits from the hailo_rpi_common.GStreamerApp class
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
        print(pipeline_string)
        return pipeline_string




# -----------------------------------------------------------------------------------------------
# PersonDetection class - encapsulates camera logic for Flask integration
# -----------------------------------------------------------------------------------------------
class PersonDetection(app_callback_class):
    def __init__(self):
        super().__init__()
        self.detection_thread = None
        self.gstreamer_app = None
        self.running = False
        self.use_frame = True  # Enable frame capture
        self.detection_stats = {
            'person_count': 0,
            'total_detections': 0,
            'last_update': time.time(),
            'fps': 0
        }
        self._stats_lock = threading.Lock()
        
    def start_detection(self):
        """Start the detection pipeline in a separate thread"""
        if not self.running:
            print("Starting person detection...")
            self.running = True
            self.detection_thread = threading.Thread(target=self._run_detection)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            return True
        return False
    
    def stop_detection(self):
        """Stop the detection pipeline"""
        if self.running:
            print("Stopping person detection...")
            self.running = False
            if self.gstreamer_app:
                self.gstreamer_app.stop()
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=5.0)
            return True
        return False
    
    def _run_detection(self):
        """Run the GStreamer detection pipeline"""
        try:
            # Monkey-patch signal.signal to avoid thread issues
            import signal
            original_signal = signal.signal
            
            def thread_safe_signal(signum, handler):
                # Only set signal handlers if we're in the main thread
                try:
                    return original_signal(signum, handler)
                except ValueError as e:
                    if "main thread" in str(e):
                        print(f"Warning: Skipping signal handler setup in thread: {e}")
                        return None
                    else:
                        raise
            
            # Temporarily replace signal.signal
            signal.signal = thread_safe_signal
            
            try:
                self.gstreamer_app = GStreamerDetectionHeadlessApp(self.app_callback, self)
                # Override video sink to use fakesink instead of autovideosink
                # This prevents KMS permission errors since we don't need local display
                self.gstreamer_app.run()
            finally:
                # Restore original signal function
                signal.signal = original_signal
                
        except Exception as e:
            print(f"Error in detection pipeline: {e}")
        finally:
            self.running = False
    
    def get_latest_frame(self):
        """Get the most recent frame from the queue (non-blocking)"""
        return self.get_frame()  # Uses parent class method
    
    def get_detection_stats(self):
        """Get current detection statistics (thread-safe)"""
        with self._stats_lock:
            return self.detection_stats.copy()
    
    def is_running(self):
        """Check if detection is currently running"""
        return self.running
    
    def app_callback(self, pad, info, user_data):
        """
        Modified callback function from detection.py
        This is called when data is available from the pipeline
        """
        # Get the GstBuffer from the probe info
        buffer = info.get_buffer()
        # Check if the buffer is valid
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # Using the user_data to count the number of frames
        user_data.increment()
        
        # Get the caps from the pad
        format, width, height = get_caps_from_pad(pad)

        # Get video frame if format is available
        frame = None
        if user_data.use_frame and format is not None and width is not None and height is not None:
            # Get video frame
            frame = get_numpy_from_buffer(buffer, format, width, height)

        # Get the detections from the buffer
        roi = hailo.get_roi_from_buffer(buffer)
        detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

        # Parse the detections
        detection_count = 0
        current_time = time.time()
        
        for detection in detections:
            label = detection.get_label()
            bbox = detection.get_bbox()
            confidence = detection.get_confidence()
            
            if label == "person":
                # Get track ID if available
                track_id = 0
                track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
                if len(track) == 1:
                    track_id = track[0].get_id()
                
                detection_count += 1
                
                # Draw bounding box on frame if available
                if frame is not None:
                    # Convert normalized coordinates to pixel coordinates
                    x_min = int(bbox.xmin() * width)
                    y_min = int(bbox.ymin() * height)
                    x_max = int(bbox.xmax() * width)
                    y_max = int(bbox.ymax() * height)
                    
                    # Draw bounding box
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                    
                    # Draw label and confidence
                    label_text = f"Person {track_id}: {confidence:.2f}"
                    cv2.putText(frame, label_text, (x_min, y_min - 10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Update detection statistics (thread-safe)
        with self._stats_lock:
            self.detection_stats['person_count'] = detection_count
            self.detection_stats['total_detections'] += detection_count
            self.detection_stats['last_update'] = current_time
            
            # Calculate FPS (simple moving average)
            time_diff = current_time - getattr(self, '_last_frame_time', current_time)
            if time_diff > 0:
                current_fps = 1.0 / time_diff
                self.detection_stats['fps'] = (self.detection_stats['fps'] * 0.9 + current_fps * 0.1)
            self._last_frame_time = current_time

        # Process frame for streaming
        if frame is not None:
            # Add detection count overlay
            cv2.putText(frame, f"Persons: {detection_count}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Add FPS overlay
            cv2.putText(frame, f"FPS: {self.detection_stats['fps']:.1f}", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Convert the frame to BGR for OpenCV compatibility
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Set the frame in the queue (uses parent class method)
            user_data.set_frame(frame)

        return Gst.PadProbeReturn.OK

# -----------------------------------------------------------------------------------------------
# Standalone test function (for debugging)
# -----------------------------------------------------------------------------------------------
def test_person_detection():
    """Test function to run PersonDetection standalone"""
    detector = PersonDetection()
    
    try:
        detector.start_detection()
        print("Detection started. Press Ctrl+C to stop...")
        
        while detector.is_running():
            time.sleep(1)
            stats = detector.get_detection_stats()
            print(f"Stats: {stats}")
            
            # Get and display frame (for testing)
            frame = detector.get_latest_frame()
            if frame is not None:
                cv2.imshow("Person Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
    except KeyboardInterrupt:
        print("\nStopping detection...")
    finally:
        detector.stop_detection()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    test_person_detection()
