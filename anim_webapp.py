from flask import Flask, render_template, request, flash, redirect, url_for
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename

from Servo.Animation import Animation, AnimationPlayer, AnimationLayer
from pathlib import Path

import os

anim_layers = {}
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
    layer = AnimationLayer(animation, True, 0.0 if len(anim_layers) else 1.0)
    anim_layers[anim_path.stem] = layer
    player.add_layer(layer)


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Path(os.path.dirname(os.path.abspath(__file__))) / "Animations"
app.config['SECRET_KEY'] = 'HappyChairAnimations'

Bootstrap(app)
current_layer = None

for anim_path in get_animation_paths(Path( __file__ ).absolute().parent /  "Animations"):
    activate_animation(anim_path)
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
    return render_template('index.html', animation_names=anim_layers.keys())

@app.route('/animation/play', methods=['POST'])
def play_animation():
    global current_layer, player
    animation_name = request.form['animation_name']
    animation_weight = request.form['weight']
    interp_duration = request.form['interpolation_duration']
    
    if animation_name in anim_layers:
        print("Starting animation")
        player.animate_layer_weight(anim_layers[animation_name], float(animation_weight), float(interp_duration))
        return index()
    
@app.route('/animation/add', methods=['GET', 'POST'])
def add_animation():
    if request.method == 'POST':
        print(request.files)
        # check if the post request has the file part
        if 'file' not in request.files:
            print("No file part")
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect('index')
        if file and os.path.splitext(file.filename)[-1] == ".json":
            print(f"Saving {file.filename}") 
            filename = secure_filename(file.filename)
            dest_filename = Path(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(dest_filename)
            activate_animation(dest_filename)
            flash(f'Uploaded {dest_filename.stem}')
            return redirect(url_for('index'))
        else:
            flash('Invalid animation file extension. Accepts .json')
    return redirect(url_for('index'))


if __name__ == '__main__':
    #player = AnimationPlayer().start()
    player.add_servo(15, "shoulder.R", None,  (500, 2500))
    player.add_servo(14, "elbow.R", None,  (500, 2500))
    player.add_servo(13, "hand.R", None,  (500, 2500))
    player.add_servo(11, "shoulder.L", None,  (500, 2500))
    player.add_servo(10, "elbow.L", None,  (500, 2500))
    player.add_servo(12, "hand.L", None,  (500, 2500))
    
    player.play()
    
    app.run(host='0.0.0.0')
