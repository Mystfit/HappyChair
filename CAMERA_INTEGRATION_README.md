# Camera Integration - Person Detection with Flask WebServer

This document describes the integration of Hailo-based person detection into the HappyChair Flask web server with HTTP streaming.

## Overview

The camera integration adds real-time person detection capabilities to the existing animation control system. It uses:

- **PersonDetection Class**: Encapsulates Hailo detection pipeline
- **HTTP Streaming**: Real-time video feed via multipart HTTP response
- **React Frontend**: New "Camera" tab for control and visualization
- **Threading**: Non-blocking operation alongside existing animation system

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React App     │    │   Flask Server   │    │ PersonDetection │
│   (Camera Tab)  │◄──►│  (anim_webapp)   │◄──►│     Class       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  HTTP Streaming  │    │ Hailo Pipeline  │
                       │   (MJPEG over    │    │   (GStreamer)   │
                       │     HTTP)        │    └─────────────────┘
                       └──────────────────┘
```

## Files Added/Modified

### New Files:
- `persondetection.py` - PersonDetection class
- `react-frontend/src/components/CameraPanel.js` - Camera UI component
- `test_camera.py` - Standalone test script
- `CAMERA_INTEGRATION_README.md` - This documentation

### Modified Files:
- `anim_webapp.py` - Added camera API endpoints
- `react-frontend/src/App.js` - Added Camera tab integration

## Setup and Usage

### Prerequisites

1. **Environment Setup**: Source the setup environment
   ```bash
   source setup_env.sh
   ```

2. **Dependencies**: All required dependencies are already in `requirements.txt`

### Testing the Camera (Standalone)

Before running the full web server, test the camera functionality:

```bash
# Make sure environment is set up
source setup_env.sh

# Run the test script
python test_camera.py
```

This will:
- Test PersonDetection class initialization
- Run detection for 30 seconds
- Display real-time statistics
- Verify frame capture and processing

### Running the Full Web Server

```bash
# Start the Flask server with camera integration
source setup_env.sh && python anim_webapp.py
```

The server will start on `http://localhost:5000` with the new Camera tab available.

## API Endpoints

### Camera Control

- **POST** `/api/camera/start` - Start person detection
- **POST** `/api/camera/stop` - Stop person detection
- **GET** `/api/camera/status` - Get detection status and statistics

### Camera Streaming

- **GET** `/api/camera/stream` - HTTP video stream (MJPEG format)

### Example API Usage

```bash
# Start camera
curl -X POST http://localhost:5000/api/camera/start

# Get status
curl http://localhost:5000/api/camera/status

# Stop camera
curl -X POST http://localhost:5000/api/camera/stop
```

## Frontend Usage

### Camera Tab

1. **Navigate** to the Camera tab in the web interface
2. **Start Camera** - Click "Start Camera" button
3. **View Stream** - Live video feed with person detection overlays
4. **Monitor Stats** - Real-time detection statistics
5. **Stop Camera** - Click "Stop Camera" when done

### Features

- **Live Video Stream**: Real-time camera feed with bounding boxes
- **Person Detection**: Automatic person detection and counting
- **Statistics Display**: 
  - Current person count
  - Total detections
  - Processing FPS
  - Last update timestamp
- **Status Indicators**: Visual feedback for camera state
- **Error Handling**: Graceful error display and recovery

## Technical Details

### PersonDetection Class

```python
class PersonDetection(app_callback_class):
    def start_detection()     # Start detection in separate thread
    def stop_detection()      # Stop detection and cleanup
    def get_latest_frame()    # Get most recent processed frame
    def get_detection_stats() # Get current statistics
    def is_running()          # Check if detection is active
```

### Frame Processing Pipeline

1. **GStreamer Pipeline**: Captures video from camera
2. **Hailo Processing**: AI-based person detection
3. **OpenCV Overlay**: Draws bounding boxes and labels
4. **Frame Queue**: Buffers frames for streaming (max 3 frames)
5. **HTTP Streaming**: Serves frames as MJPEG stream

### Threading Architecture

- **Main Thread**: Flask web server and animation system
- **Detection Thread**: GStreamer pipeline and Hailo processing
- **Frame Queue**: Thread-safe communication between threads

## Performance Characteristics

- **Latency**: ~100-200ms (local network)
- **Bandwidth**: ~1-3 Mbps (depending on resolution/quality)
- **CPU Usage**: Moderate (Hailo handles AI processing)
- **Memory**: Controlled by 3-frame queue limit
- **FPS**: Target ~30 FPS, actual depends on processing capability

## Troubleshooting

### Common Issues

1. **Camera Not Starting**
   - Ensure `setup_env.sh` is sourced
   - Check camera permissions and availability
   - Verify Hailo device connection

2. **No Video Stream**
   - Check browser compatibility (modern browsers required)
   - Verify network connectivity
   - Check Flask server logs for errors

3. **Poor Performance**
   - Reduce video quality in camera settings
   - Check system resource usage
   - Ensure adequate lighting for detection

### Debug Commands

```bash
# Test camera independently
python test_camera.py

# Check Hailo device
hailortcli fw-control identify

# Test original detection script
source setup_env.sh && python detection.py --input rpi

# Check Flask server logs
source setup_env.sh && python anim_webapp.py
```

### Log Analysis

- **PersonDetection logs**: Printed to console during operation
- **Flask logs**: Standard Flask request/response logging
- **GStreamer logs**: Pipeline status and errors
- **Browser console**: Frontend errors and network issues

## Integration with Animation System

The camera system runs independently of the animation system:

- **Non-blocking**: Camera runs in separate thread
- **Resource sharing**: Both systems can run simultaneously
- **Status integration**: Camera status appears in main status indicator
- **Clean shutdown**: Proper cleanup when server stops

## Future Enhancements

Potential improvements for future versions:

1. **WebRTC Integration**: Lower latency streaming
2. **Recording Capability**: Save detection sessions
3. **Motion Triggers**: Trigger animations based on person detection
4. **Multiple Cameras**: Support for multiple camera inputs
5. **Advanced Analytics**: Person tracking, behavior analysis
6. **Mobile Optimization**: Better mobile device support

## Security Considerations

- **Local Network**: Designed for local network use
- **No Authentication**: Currently no user authentication
- **Camera Access**: Direct camera access requires appropriate permissions
- **Resource Limits**: Frame queue prevents memory exhaustion

## Support

For issues or questions:

1. Check this documentation
2. Run the test script (`test_camera.py`)
3. Check Flask server logs
4. Verify Hailo setup and environment
5. Test original detection script for baseline functionality
