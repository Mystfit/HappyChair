from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, send_from_directory
from flask_sock import Sock
from flask_bootstrap import Bootstrap
from flask_cors import CORS
from werkzeug.utils import secure_filename
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from Servo.Animation import Animation, AnimationPlayer, AnimationLayer, Playlist
from pathlib import Path

import os, subprocess, json, time

# Dictionary to store available animations (Animation objects)
available_animations = {}
# Animation layers are now stored directly in the AnimationPlayer
playlists = {}
player = AnimationPlayer().start()


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
    animation = Animation(anim_path)
    available_animations[anim_path.stem] = animation
    print(f"Loaded animation: {anim_path.stem}")
    
def create_animation_layer(animation_name, weight=0.0, loop=False):
    """Create an animation layer for the specified animation and add it to the player"""
    global available_animations, player
    if animation_name not in available_animations:
        print(f"Animation not found: {animation_name}")
        return None
    
    animation = available_animations[animation_name]
    # Use the player's create_layer method to create and add the layer
    return player.create_layer(animation, animation_name, weight, loop)
    
def activate_playlist(playlist_path):
    global playlists
    playlist = Playlist(playlist_path)
    playlists[playlist_path.stem] = playlist


# Set up flask app
app = Flask(__name__, static_folder='./react-frontend/build', static_url_path='/')
app.debug = True
app.config['PLAYLIST_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Playlists"
app.config['UPLOAD_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Animations"
app.config['SECRET_KEY'] = 'HappyChairAnimations'
Bootstrap(app)
CORS(app)  # Enable CORS for all routes

# Set up socketIO runner for flask app
sock = Sock(app)

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
                          global_framerate=player.framerate,
                          transport_playing=player.is_playing(),
                          playlist_transport_playing=False,
                          animation_mode=player.animation_mode(),
                          active_tab='#transport-tab')

# API Endpoints
@app.route('/api/animations', methods=['GET'])
def get_animations():
    return jsonify({
        'animations': list(available_animations.keys()),
        'global_framerate': player.framerate,
        'transport_playing': player.is_playing(),
        'animation_mode': player.animation_mode()
    })

@app.route('/api/playlists', methods=['GET'])
def get_playlists():
    return jsonify({
        'playlists': list(playlists.keys()),
        'playlist_transport_playing': False
    })

@app.route('/api/transport', methods=['POST'])
def api_set_transport():
    global player
    data = request.json
    transport_status = data.get('transport')
    
    if transport_status == "play":
        player.play()
    elif transport_status == "pause":
        player.pause()
    elif transport_status == "stop":
        player.stop()
    
    if 'global_framerate' in data:
        player.framerate = float(data['global_framerate'])
    
    return jsonify({
        'success': True,
        'transport_playing': player.is_playing(),
        'global_framerate': player.framerate
    })

@app.route('/api/animation/play', methods=['POST'])
def api_play_animation():
    global player, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    animation_weight = data.get('weight')
    interp_duration = data.get('interpolation_duration')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists, or create a new one
        layer = player.get_layer_by_name(animation_name)
        
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
        player.animate_layer_weight(layer, float(animation_weight), float(interp_duration))
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
    global player, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists
        layer = player.get_layer_by_name(animation_name)
        
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
    global player, available_animations
    data = request.json
    animation_name = data.get('animation_name')
    
    # Check if the animation exists in available animations
    if animation_name in available_animations:
        # Get the layer if it exists
        layer = player.get_layer_by_name(animation_name)
        
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
    global player
    data = request.json
    transport_status = data.get('transport')
    playlist_name = data.get('playlist_name')
    
    if playlist_name not in playlists:
        return jsonify({'success': False, 'error': 'Playlist not found'}), 404
    
    playlist = playlists[playlist_name]
    print(f'Playlist transport status changed to: {transport_status}. Does it match? {transport_status == "play"}')

    if transport_status == "play":
        player.set_playlist(playlist)
    elif transport_status == "pause":
        pass  # Currently not implemented in the backend
    elif transport_status == "stop":
        player.stop()
        player.reset_playlist()
    
    return jsonify({
        'success': True,
        'transport_status': transport_status,
        'playlist_name': playlist_name
    })


# WebSocket routes
@sock.route('/api/ws/status')
def animation_status(ws):
    global player
    try:
        # Check if the WebSocket is still connected
        while ws.connected:
            # Get animation mode from player
            anim_mode = player.animation_mode()
            print(f"Current animation mode: {anim_mode}")
            
            # Get active animations directly from the player
            active_animations = player.get_active_layers()
            
            # Debug print
            print(f"Active animations: {len(active_animations)}")
            for anim in active_animations:
                print(f"  {anim['name']}: playing={anim['is_playing']}, weight={anim['weight']}, frame={anim['current_frame']}/{anim['total_frames']}")
            
            status = {
                'is_playing': player.is_playing(),
                'animation_mode': player.animation_mode(),
                'global_framerate': player.framerate,
                'active_animations': active_animations
            }
            
            try:
                ws.send(json.dumps(status))
                time.sleep(0.1)  # Update every 100ms
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
    global player
    while True:
        message = ws.receive()
        command_start = message[0]
        if command_start == 0x3c:
            servo_id = int(message[1])
            angle = int.from_bytes(message[2:4], byteorder='big')
            command_end = message[4]
            # print("Raw message: " + str(message )+ ", Servo ID: " + str(servo_id) + ", value: " + str(angle))
            player.rotate_servo(servo_id, angle)


if __name__ == '__main__':
    #player = AnimationPlayer().start()
    player.add_servo(15, "shoulder.R", None,  (500, 2500))
    player.add_servo(14, "elbow.R", None,  (500, 2500))
    player.add_servo(13, "hand.R", None,  (500, 2500))
    player.add_servo(11, "shoulder.L", None,  (500, 2500))
    player.add_servo(10, "elbow.L", None,  (500, 2500))
    player.add_servo(12, "hand.L", None,  (500, 2500))
    
    #player.play()
    #server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    #server.serve_forever()
    app.run(host='0.0.0.0', port=5000)
