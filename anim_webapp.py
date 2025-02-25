from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sock import Sock
from flask_bootstrap import Bootstrap
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
app = Flask(__name__)
app.debug = True
app.config['PLAYLIST_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Playlists"
app.config['UPLOAD_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Animations"
app.config['SECRET_KEY'] = 'HappyChairAnimations'
Bootstrap(app)

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

    
@app.route('/')
def index():
    active_tab = request.args.get('active_tab', '#transport-tab')
    return render_template(
        'index.html',
        animation_names=anim_layers.keys(),
        global_framerate=player.framerate,
        transport_playing=player.is_playing(),
        playlist_names=playlists.keys(),
        playlist_transport_playing=False,
        animation_mode=player.animation_mode(),
        active_tab=active_tab
    )

@app.route('/transport', methods=['POST'])
def set_transport():
    global player
    transport_status = request.form['transport']
    active_tab = request.form.get('active_tab', '#transport-tab')
    if transport_status == "play":
        flash('Transport playing', "info")
        player.play()
    elif transport_status == "pause":
        flash('Transport paused', "light")
        player.pause()
    elif transport_status == "stop":
        flash('Transport stopped', "light")
        player.stop()
    else:
        print("No transport change")
    print(request.form['global_framerate'])    
    player.framerate = float(request.form['global_framerate'])
    return redirect(url_for('index', active_tab=active_tab))

@app.route('/animation/play', methods=['POST'])
def play_animation():
    global current_layer, player
    animation_name = request.form['animation_name']
    animation_weight = request.form['weight']
    interp_duration = request.form['interpolation_duration']
    active_tab = request.form.get('active_tab', '#transport-tab')
    
    if animation_name in anim_layers:
        print("Starting animation")
        player.animate_layer_weight(anim_layers[animation_name], float(animation_weight), float(interp_duration))
        anim_layers[animation_name].play()
        return redirect(url_for('index', active_tab=active_tab))
    
@app.route('/poweroff', methods=['POST'])
def power_off():
    active_tab = request.form.get('active_tab', '#transport-tab')
    subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
    flash(f"Power off in process", "success")
    return redirect(url_for('index', active_tab=active_tab))
    
@app.route('/animation/add', methods=['GET', 'POST'])
def add_animation():
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', '#transport-tab')
        print(request.files)
        # check if the post request has the file part
        if 'file' not in request.files:
            print("No file part")
            flash('No file part', "error")
            return redirect(url_for('index', active_tab=active_tab))
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file', "error")
            return redirect(url_for('index', active_tab=active_tab))
        if file and os.path.splitext(file.filename)[-1] == ".json":
            print(f"Saving {file.filename}") 
            filename = secure_filename(file.filename)
            dest_filename = Path(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(dest_filename)
            activate_animation(dest_filename)
            flash(f'Uploaded {dest_filename.stem}', "success")
            return redirect(url_for('index', active_tab=active_tab))
        else:
            flash('Invalid animation file extension. Accepts .json')
    return redirect(url_for('index'))


@app.route('/playlist/add', methods=['GET', 'POST'])
def add_playlist():
    if request.method == 'POST':
        active_tab = request.form.get('active_tab', '#transport-tab')
        print(request.files)
        # check if the post request has the file part
        if 'file' not in request.files:
            print("No file part")
            flash('No file part', "error")
            return redirect(url_for('index', active_tab=active_tab))
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file', "error")
            return redirect(url_for('index', active_tab=active_tab))
        if file and os.path.splitext(file.filename)[-1] == ".json":
            print(f"Saving {file.filename}") 
            filename = secure_filename(file.filename)
            dest_filename = Path(os.path.join(app.config['PLAYLIST_FOLDER'], filename))
            file.save(dest_filename)
            
            activate_playlist(dest_filename)
            flash(f'Uploaded {dest_filename.stem}', "success")
            return redirect(url_for('index', active_tab=active_tab))
        else:
            flash('Invalid playlist file extension. Accepts .json')
    return redirect(url_for('index'))

@app.route('/playlist/transport', methods=['POST'])
def set_playlist_transport():
    global player
    transport_status = request.form['transport']
    playlist_name = str(request.form["playlistSelect"])
    active_tab = request.form.get('active_tab', '#transport-tab')
    playlist = playlists[playlist_name]
    print(f'Playlist transport status changed to: {transport_status}. Does it match? {transport_status == "play"}')

    if transport_status == "play":
        flash('Playlist transport playing', "info")
        player.set_playlist(playlist)
    elif transport_status == "pause":
        flash('Playlist transport paused', "light")
    elif transport_status == "stop":
        flash('Playlist transport stopped', "light")
        player.stop()
        player.reset_playlist()
    else:
        print("No playlist transport change")
    
    return redirect(url_for('index', active_tab=active_tab))


'''
Websocket routes for livestreamed animations
'''
# @socketio.on('connect')
# def handle_connect():
#     global player
#     print("Websocket client connected")
#     player.set_animation_mode(AnimationPlayer.LIVE_MODE)
#     
# @socketio.on('disconnnect')
# def handle_disconnect():
#     global player
#     print("Websocket client disconnected")
#     player.set_animation_mode(AnimationPlayer.TRANSPORT_MODE)

@sock.route('/')
def handle_blender_index(ws):
    while not ws.closed:
        message = ws.receive()
        if message:    
            print("Received connect message" + str(data))
    
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
