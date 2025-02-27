from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, send_from_directory
from flask_sock import Sock
from flask_bootstrap import Bootstrap
from flask_cors import CORS
from werkzeug.utils import secure_filename
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from Servo.Animation import Animation, AnimationPlayer, AnimationLayer, Playlist
from pathlib import Path

import os, subprocess

anim_layers = {}
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

def activate_animation(anim_path):
    global anim_layers, player
    animation = Animation(anim_path)
    layer = AnimationLayer(animation, False, 0.0 if len(anim_layers) else 1.0)
    anim_layers[anim_path.stem] = layer
    player.add_layer(layer)
    
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
for anim_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Animations"):
    activate_animation(anim_path)
    
for playlist_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Playlists"):
    activate_playlist(playlist_path)
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
    animation_names = list(anim_layers.keys())
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
        'animations': list(anim_layers.keys()),
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
    global current_layer, player
    data = request.json
    animation_name = data.get('animation_name')
    animation_weight = data.get('weight')
    interp_duration = data.get('interpolation_duration')
    
    if animation_name in anim_layers:
        print("Starting animation")
        player.animate_layer_weight(anim_layers[animation_name], float(animation_weight), float(interp_duration))
        anim_layers[animation_name].play()
        return jsonify({
            'success': True,
            'animation': animation_name,
            'weight': animation_weight,
            'duration': interp_duration
        })
    
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
        activate_animation(dest_filename)
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
        while not ws.closed:
            status = {
                'is_playing': player.is_playing(),
                'animation_mode': player.animation_mode(),
                'global_framerate': player.framerate,
                'active_animations': [
                    {'name': name, 'weight': layer.weight}
                    for name, layer in anim_layers.items()
                ]
            }
            ws.send(json.dumps(status))
            time.sleep(0.1)  # Update every 100ms
    except Exception as e:
        print(f"WebSocket error: {e}")

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
