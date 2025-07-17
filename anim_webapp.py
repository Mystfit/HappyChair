import signal
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, send_from_directory, Response
from flask_sock import Sock
from flask_bootstrap import Bootstrap
from flask_cors import CORS
from werkzeug.utils import secure_filename
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from Servo.Animation import ServoAnimationClip, ServoAnimationController, ServoAnimationLayer, Playlist
from pathlib import Path
from io_controller import IOController
from camera_controller import CameraController
from yaw_controller import YawController
from BehaviourTrees.implementations.chair_behaviour_tree import ChairBehaviourTree
import cv2
import numpy as np

import os, subprocess, json, time, sys

# Dictionary to store available animations (Animation objects)
available_animations = {}

# Animation layers are now stored directly in the AnimationController
playlists = {}
animation_controller = ServoAnimationController()

def shutdown(signum, frame):
    if chair_behaviour_tree:
        chair_behaviour_tree.shutdown()
    if yaw_controller:
        yaw_controller.shutdown()
    if io_controller:
        io_controller.shutdown()
    if camera_controller:
        camera_controller.shutdown()
    sys.exit()

def get_animation_paths(folder_path):
    json_files = []
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return json_files

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        if os.path.isfile(file_path) and filename.lower().endswith('.json'):
            json_files.append(Path(file_path))

    return json_files

def load_animation(anim_path):
    """Load an animation file into the available_animations dictionary"""
    global available_animations
    animation = ServoAnimationClip(anim_path)
    available_animations[anim_path.stem] = animation
    print(f"Loaded animation: {anim_path.stem}")
    
def create_animation_layer(animation_name, weight=0.0, loop=False):
    """Create an animation layer for the specified animation and add it to the player"""
    global available_animations, animation_controller
    if animation_name not in available_animations:
        print(f"Animation not found: {animation_name}")
        return None
    
    animation = available_animations[animation_name]
    # Use the player's create_layer method to create and add the layer
    return animation_controller.create_layer(animation, animation_name, weight, loop)
    
def activate_playlist(playlist_path):
    global playlists
    playlist = Playlist(playlist_path)
    playlists[playlist_path.stem] = playlist


# Set up flask app
app = Flask(__name__, static_folder='./react-frontend/build', static_url_path='/')
app.debug = False  # Disable debug mode to prevent GPIO conflicts on restart
app.config['PLAYLIST_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Playlists"
app.config['UPLOAD_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Animations"
app.config['SECRET_KEY'] = 'HappyChairAnimations'
Bootstrap(app)
CORS(app)  # Enable CORS for all routes

# Set up socketIO runner for flask app
sock = Sock(app)

# Initialize IOController to handle GPIO only
io_controller = IOController()
io_controller.register_pin(14, "seatsensor", "input", "pull_up")
io_controller.register_pin(15, "spinclutch", "output")

# Initialize CameraController to handle camera detection
camera_controller = CameraController()

# Initialize YawController with DRV8825 PWM multiprocess driver to control chair base rotation
yaw_controller = YawController(motor_type="drv8825_pwm_multiprocess")

# Initialize ChairBehaviourTree with all controllers
chair_behaviour_tree = None

current_layer = None
# Load all animations but don't create layers for them
for anim_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Animations"):
    load_animation(anim_path)
    
for playlist_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Playlists"):
    activate_playlist(playlist_path)
    
# We've removed the automatic base idle layer to fix layer management issues
# Animation layers will now only be created when animations are played
#animations = {anim_path.stem: Animation(anim_path) for anim_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Animations")}

# Define your animations
#animations = {
#    'Excited': Animation(Path( __file__ ).absolute().parent /  "Animations" / "excited.json"),
#    'Wave': Animation(Path( __file__ ).absolute().parent /  "Animations" / "wave_only.json"),
#    'Beckon': Animation(Path( __file__ ).absolute().parent / "Animations" / "ServoArm_RightBeckon.json")
    # Add more animations here
#}

# Set initial weights and add layers
#for anim_name, animation in animations.items():
#    layer = AnimationLayer(animation, True, 0.0 if len(anim_layers) else 1.0)
#    anim_layers[anim_name] = layer
#    player.add_layer(layer)

    
# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# Legacy template route for backward compatibility
@app.route('/legacy')
def legacy_interface():
    animation_names = list(available_animations.keys())
    playlist_names = list(playlists.keys())
    return render_template('index.html', 
                          animation_names=animation_names, 
                          playlist_names=playlist_names,
                          global_framerate=animation_controller.framerate,
                          transport_playing=animation_controller.is_playing(),
                          playlist_transport_playing=False,
                          animation_mode=animation_controller.animation_mode(),
                          active_tab='#transport-tab')

# API Endpoints
@app.route('/api/animations', methods=['GET'])
def get_animations():
    return jsonify({
        'animations': list(available_animations.keys()),
        'global_framerate': animation_controller.framerate,
        'transport_playing': animation_controller.is_playing(),
        'animation_mode': animation_controller.animation_mode()
    })

@app.route('/api/playlists', methods=['GET'])
def get_playlists():
    return jsonify({
        'playlists': list(playlists.keys()),
        'playlist_transport_playing': False
    })

@app.route('/api/transport', methods=['POST'])
def api_set_transport():
    global animation_controller
    data = request.json
    transport_status = data.get('transport')
    
    if transport_status == "play":
        animation_controller.play()
    elif transport_status == "pause":
        animation_controller.pause()
    elif transport_status == "stop":
        animation_controller.stop()
    
    if 'global_framerate' in data:
        animation_controller.framerate = float(data['global_framerate'])
    
    return jsonify({
        'success': True,
        'transport_playing': animation_controller.is_playing(),
        'global_framerate': animation_controller.framerate
    })

@app.route('/api/animation/play', methods=['POST'])
def api_play_animation():
    global animation_controller, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    animation_weight = data.get('weight')
    interp_duration = data.get('interpolation_duration')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists, or create a new one
        layer = animation_controller.get_layer_by_name(animation_name)
        
        if not layer:
            print(f"Creating new layer for animation: {animation_name}")
            # Non-looping by default in dynamic mode
            layer = create_animation_layer(animation_name, float(animation_weight), False)
            if not layer:
                return jsonify({'success': False, 'error': 'Failed to create animation layer'}), 500
        else:
            # Ensure existing layers are non-looping if playing again
            layer.looping = False
        
        print(f"Starting animation: {animation_name} with looping={layer.looping}")
        animation_controller.animate_layer_weight(layer, float(animation_weight), float(interp_duration))
        # Play but preserve the non-looping setting
        layer.play(loop=False)
        
        return jsonify({
            'success': True,
            'animation': animation_name,
            'weight': animation_weight,
            'duration': interp_duration
        })
    
    return jsonify({'success': False, 'error': 'Animation not found'}), 404

@app.route('/api/animation/pause', methods=['POST'])
def api_pause_animation():
    global animation_controller, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists
        layer = animation_controller.get_layer_by_name(animation_name)
        
        if layer:
            print(f"Pausing animation: {animation_name}")
            layer.pause()
            return jsonify({
                'success': True,
                'animation': animation_name,
                'message': f'Animation {animation_name} paused'
            })
        else:
            return jsonify({'success': False, 'error': 'Animation layer not created yet'}), 400
    
    return jsonify({'success': False, 'error': 'Animation not found'}), 404

@app.route('/api/animation/rewind', methods=['POST'])
def api_rewind_animation():
    global animation_controller, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists
        layer = animation_controller.get_layer_by_name(animation_name)
        
        if layer:
            print(f"Rewinding animation: {animation_name}")
            # Reset the animation to frame 0
            layer.current_frame = 0
            return jsonify({
                'success': True,
                'animation': animation_name,
                'message': f'Animation {animation_name} rewound to start'
            })
        else:
            return jsonify({'success': False, 'error': 'Animation layer not created yet'}), 400
    
    return jsonify({'success': False, 'error': 'Animation not found'}), 404
    
@app.route('/api/poweroff', methods=['POST'])
def api_power_off():
    subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
    return jsonify({'success': True, 'message': 'Power off in process'})
    
@app.route('/api/animation/add', methods=['POST'])
def api_add_animation():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400
    
    if file and os.path.splitext(file.filename)[-1] == ".json":
        print(f"Saving {file.filename}") 
        filename = secure_filename(file.filename)
        dest_filename = Path(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        file.save(dest_filename)
        
        # Load the animation into available_animations
        load_animation(dest_filename)
        
        return jsonify({
            'success': True, 
            'message': f'Uploaded {dest_filename.stem}',
            'animation_name': dest_filename.stem
        })
    else:
        return jsonify({'success': False, 'error': 'Invalid animation file extension. Accepts .json'}), 400


@app.route('/api/playlist/add', methods=['POST'])
def api_add_playlist():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400
    
    if file and os.path.splitext(file.filename)[-1] == ".json":
        print(f"Saving {file.filename}") 
        filename = secure_filename(file.filename)
        dest_filename = Path(os.path.join(app.config['PLAYLIST_FOLDER'], filename))
        file.save(dest_filename)
        
        activate_playlist(dest_filename)
        return jsonify({
            'success': True, 
            'message': f'Uploaded {dest_filename.stem}',
            'playlist_name': dest_filename.stem
        })
    else:
        return jsonify({'success': False, 'error': 'Invalid playlist file extension. Accepts .json'}), 400

@app.route('/api/playlist/transport', methods=['POST'])
def api_set_playlist_transport():
    global animation_controller
    data = request.json
    transport_status = data.get('transport')
    playlist_name = data.get('playlist_name')
    
    if playlist_name not in playlists:
        return jsonify({'success': False, 'error': 'Playlist not found'}), 404
    
    playlist = playlists[playlist_name]
    print(f'Playlist transport status changed to: {transport_status}. Does it match? {transport_status == "play"}')

    if transport_status == "play":
        animation_controller.set_playlist(playlist)
    elif transport_status == "pause":
        pass  # Currently not implemented in the backend
    elif transport_status == "stop":
        animation_controller.stop()
        animation_controller.reset_playlist()
    
    return jsonify({
        'success': True,
        'transport_status': transport_status,
        'playlist_name': playlist_name
    })

# Camera API Endpoints (now using CameraController)
@app.route('/api/camera/start', methods=['POST'])
def api_start_camera():
    global camera_controller
    try:
        if camera_controller.start_detection():
            return jsonify({
                'success': True,
                'message': 'Camera started successfully',
                'process_info': camera_controller.get_process_info()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Camera is already running'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to start camera: {str(e)}'
        }), 500

@app.route('/api/camera/stop', methods=['POST'])
def api_stop_camera():
    global camera_controller
    try:
        if camera_controller and camera_controller.stop_detection():
            return jsonify({
                'success': True,
                'message': 'Camera stopped successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Camera is not running'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to stop camera: {str(e)}'
        }), 500

@app.route('/api/camera/status', methods=['GET'])
def api_camera_status():
    global camera_controller, yaw_controller
    try:
        if camera_controller:
            detection_stats = camera_controller.get_detection_stats()
            motor_stats = yaw_controller.get_motor_stats() if yaw_controller else {}
            
            # Combine stats
            stats = {**detection_stats, **motor_stats}
            
            return jsonify({
                'success': True,
                'running': camera_controller.is_detection_running(),
                'stats': stats
            })
        else:
            return jsonify({
                'success': True,
                'running': False,
                'stats': {
                    'person_count': 0,
                    'unique_people': 0,
                    'last_update': 0,
                    'fps': 0,
                    'tracked_person_id': None,
                    'motor_direction': 'stopped',
                    'motor_speed': 0.0,
                    'tracking_enabled': False
                }
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get camera status: {str(e)}'
        }), 500

@app.route('/api/camera/restart', methods=['POST'])
def api_restart_camera():
    global camera_controller
    try:
        if camera_controller:
            if camera_controller.restart_detection():
                return jsonify({
                    'success': True,
                    'message': 'Camera restarted successfully',
                    'process_info': camera_controller.get_process_info()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to restart camera'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Camera not initialized'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to restart camera: {str(e)}'
        }), 500

@app.route('/api/camera/process-info', methods=['GET'])
def api_camera_process_info():
    global camera_controller
    try:
        if camera_controller:
            return jsonify({
                'success': True,
                'process_info': camera_controller.get_process_info(),
                'running': camera_controller.is_detection_running()
            })
        else:
            return jsonify({
                'success': True,
                'process_info': {'status': 'not_initialized'},
                'running': False
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get process info: {str(e)}'
        }), 500

@app.route('/api/camera/stream')
def api_camera_stream():
    global camera_controller
    
    def generate_frames():
        last_frame_time = time.time()
        frame_interval = 1.0 / 30.0  # Target 30 FPS for stream
        
        while True:
            try:
                current_time = time.time()
                
                if camera_controller and camera_controller.is_detection_running():
                    frame = camera_controller.get_latest_frame()
                    if frame is not None:
                        # Encode frame as JPEG with optimized quality
                        encode_params = [
                            cv2.IMWRITE_JPEG_QUALITY, 80,
                            cv2.IMWRITE_JPEG_OPTIMIZE, 1
                        ]
                        _, buffer = cv2.imencode('.jpg', frame, encode_params)
                        
                        # Yield frame in multipart format
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               buffer.tobytes() + b'\r\n')
                        
                        last_frame_time = current_time
                    else:
                        # No frame available, send a waiting message
                        waiting_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(waiting_frame, "Waiting for frames...", (180, 240), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                        
                        _, buffer = cv2.imencode('.jpg', waiting_frame)
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               buffer.tobytes() + b'\r\n')
                else:
                    # Send a blank frame if camera is not running
                    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(blank_frame, "Camera Not Active", (200, 240), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(blank_frame, "CameraController Mode", (180, 280), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
                    
                    _, buffer = cv2.imencode('.jpg', blank_frame)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           buffer.tobytes() + b'\r\n')
                
                # Control frame rate to prevent overwhelming the client
                elapsed = time.time() - current_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Error in camera stream: {e}")
                time.sleep(0.1)  # Brief pause on error
    
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

# GPIO API Endpoints
@app.route('/api/gpio/pins', methods=['GET'])
def api_gpio_pins():
    global io_controller
    try:
        if io_controller:
            pin_states = io_controller.get_pin_states()
            return jsonify({
                'success': True,
                'pins': pin_states
            })
        else:
            return jsonify({
                'success': True,
                'pins': {}
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get GPIO pin states: {str(e)}'
        }), 500

# Yaw Control API Endpoints
@app.route('/api/yaw/start-tracking', methods=['POST'])
def api_start_yaw_tracking():
    global yaw_controller
    try:
        if yaw_controller:
            if yaw_controller.start_tracking():
                return jsonify({
                    'success': True,
                    'message': 'Yaw tracking started successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to start yaw tracking or already running'
                }), 400
        else:
            return jsonify({
                'success': False,
                'error': 'YawController not initialized'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to start yaw tracking: {str(e)}'
        }), 500

@app.route('/api/yaw/stop-tracking', methods=['POST'])
def api_stop_yaw_tracking():
    global yaw_controller
    try:
        if yaw_controller:
            yaw_controller.stop_tracking()
            return jsonify({
                'success': True,
                'message': 'Yaw tracking stopped successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'YawController not initialized'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to stop yaw tracking: {str(e)}'
        }), 500

@app.route('/api/yaw/status', methods=['GET'])
def api_yaw_status():
    global yaw_controller
    try:
        if yaw_controller:
            stats = yaw_controller.get_motor_stats()
            return jsonify({
                'success': True,
                'tracking_enabled': yaw_controller.is_tracking_enabled(),
                'motor_direction': stats.get('motor_direction', 'stopped'),
                'motor_speed': stats.get('motor_speed', 0.0),
                'tracked_person_id': stats.get('tracked_person_id', None)
            })
        else:
            return jsonify({
                'success': True,
                'tracking_enabled': False,
                'motor_direction': 'stopped',
                'motor_speed': 0.0,
                'tracked_person_id': None
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get yaw status: {str(e)}'
        }), 500


# Behaviour Tree API Endpoints
@app.route('/api/behaviour/start', methods=['POST'])
def api_start_behaviour_tree():
    global chair_behaviour_tree
    try:
        if chair_behaviour_tree and chair_behaviour_tree.start():
            return jsonify({'success': True, 'message': 'Behaviour tree started'})
        else:
            return jsonify({'success': False, 'error': 'Failed to start behaviour tree'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/behaviour/stop', methods=['POST'])
def api_stop_behaviour_tree():
    global chair_behaviour_tree
    try:
        if chair_behaviour_tree:
            chair_behaviour_tree.stop()
            return jsonify({'success': True, 'message': 'Behaviour tree stopped'})
        else:
            return jsonify({'success': False, 'error': 'Behaviour tree not initialized'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/behaviour/status', methods=['GET'])
def api_behaviour_tree_status():
    global chair_behaviour_tree
    try:
        if chair_behaviour_tree:
            status = chair_behaviour_tree.get_tree_status()
            blackboard_data = chair_behaviour_tree.get_blackboard_data()
            return jsonify({
                'success': True, 
                'status': status,
                'blackboard': blackboard_data,
                'running': chair_behaviour_tree.is_running()
            })
        else:
            return jsonify({
                'success': True,
                'status': {'nodes': [], 'currently_running': [], 'changed': False, 'tree_running': False},
                'blackboard': {},
                'running': False
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/behaviour/graph', methods=['GET'])
def api_behaviour_tree_graph():
    global chair_behaviour_tree
    try:
        if chair_behaviour_tree:
            ascii_graph = chair_behaviour_tree.generate_ascii_graph()
            return jsonify({'success': True, 'ascii_graph': ascii_graph})
        else:
            return jsonify({'success': False, 'error': 'Behaviour tree not initialized'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# WebSocket routes
@sock.route('/api/ws/status')
def animation_status(ws):
    global animation_controller, io_controller, camera_controller, yaw_controller, chair_behaviour_tree
    try:
        # Check if the WebSocket is still connected
        while ws.connected:
            # Get animation mode from player
            anim_mode = animation_controller.animation_mode()
            # print(f"Current animation mode: {anim_mode}")
            
            # Get active animations directly from the player
            active_animations = animation_controller.get_active_layers()
            
            # Get controller data
            gpio_pins = {}
            camera_stats = {}
            motor_stats = {}
            behaviour_status = {}
            blackboard_data = {}
            graph_data = {}
            
            if io_controller:
                gpio_pins = io_controller.get_pin_states()
            
            if camera_controller:
                camera_stats = camera_controller.get_detection_stats()
            
            if yaw_controller:
                motor_stats = yaw_controller.get_motor_stats()
            
            if chair_behaviour_tree:
                behaviour_status = chair_behaviour_tree.get_tree_status()
                blackboard_data = chair_behaviour_tree.get_blackboard_data()
                graph_data = chair_behaviour_tree.last_executed_ascii_graph
                      
            # Debug print
            # print(f"Active animations: {len(active_animations)}")
            # for anim in active_animations:
            #     print(f"  {anim['name']}: playing={anim['is_playing']}, weight={anim['weight']}, frame={anim['current_frame']}/{anim['total_frames']}")
            
            status = {
                'is_playing': animation_controller.is_playing(),
                'animation_mode': animation_controller.animation_mode(),
                'global_framerate': animation_controller.framerate,
                'active_animations': active_animations,
                'gpio_pins': gpio_pins,
                'camera_stats': camera_stats,
                'motor_stats': motor_stats,
                'behaviour_status': behaviour_status,
                'blackboard_data': blackboard_data,
                'graph_data': graph_data,
            }
            
            try:
                ws.send(json.dumps(status))
                time.sleep(1 / animation_controller.framerate * 0.5)  # Update at framerate
            except Exception as inner_e:
                print(f"WebSocket send error: {inner_e}")
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket connection closed")

@sock.route('/')
def handle_blender_index(ws):
    while not ws.closed:
        message = ws.receive()
        if message:    
            print("Received connect message" + str(message))
    
@sock.route('/live')
def handle_blender_live(ws):
    global animation_controller
    while True:
        message = ws.receive()
        command_start = message[0]
        if command_start == 0x3c:
            servo_id = int(message[1])
            angle = int.from_bytes(message[2:4], byteorder='big')
            command_end = message[4]
            # print("Raw message: " + str(message )+ ", Servo ID: " + str(servo_id) + ", value: " + str(angle))
            animation_controller.rotate_servo(servo_id, angle)
            


# Create a single base layer that we can return to when animations finish playing
base_layer = create_animation_layer("idle", 1.0, True)
base_layer.play()
animation_controller.start()

# Initialize ChairBehaviourTree after all controllers are set up
# Pass available_animations to the animation_controller for access
animation_controller.available_animations = available_animations
chair_behaviour_tree = ChairBehaviourTree(animation_controller, yaw_controller, camera_controller, io_controller)

if __name__ == '__main__':
    # Set up signal handler for SIGINT (Ctrl-C)
    signal.signal(signal.SIGINT, shutdown)
        
    #player = AnimationController().start()
    animation_controller.add_servo(15, "shoulder.R", None,  (500, 2500))
    animation_controller.add_servo(14, "elbow.R", None,  (500, 2500))
    animation_controller.add_servo(13, "hand.R", None,  (500, 2500))
    animation_controller.add_servo(11, "shoulder.L", None,  (500, 2500))
    animation_controller.add_servo(10, "elbow.L", None,  (500, 2500))
    animation_controller.add_servo(12, "hand.L", None,  (500, 2500))
    
    #player.play()
    #server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    #server.serve_forever()
    app.run(host='0.0.0.0', port=5000)
