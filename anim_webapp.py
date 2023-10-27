from flask import Flask, render_template, request
from Servo.Animation import Animation, AnimationPlayer, AnimationLayer
from pathlib import Path

app = Flask(__name__)
player = AnimationPlayer().start()
current_layer = None

# Define your animations
animations = {
    'Excited': Animation(Path( __file__ ).absolute().parent /  "Animations" / "excited.json"),
    'Wave': Animation(Path( __file__ ).absolute().parent /  "Animations" / "wave_only.json"),
    'Beckon': Animation(Path( __file__ ).absolute().parent / "Animations" / "ServoArm_RightBeckon.json")
    # Add more animations here
}
anim_layers = {}

# Set initial weights and add layers
for anim_name, animation in animations.items():
    layer = AnimationLayer(animation, True, 0.0 if len(anim_layers) else 1.0)
    anim_layers[anim_name] = layer
    player.add_layer(layer)
    

    
@app.route('/')
def index():
    return render_template('index.html', animation_names=animations.keys())

@app.route('/play_animation', methods=['POST'])
def play_animation():
    global current_layer, player
    animation_name = request.form['animation_name']
    animation_weight = request.form['weight']
    interp_duration = request.form['interpolation_duration']
    
    if animation_name in animations:
        print("Starting animation")
         player.animate_layer_weight(anim_layers[animation_name], float(animation_weight), float(interp_duration))
        return index()


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
