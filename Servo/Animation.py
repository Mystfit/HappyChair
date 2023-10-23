import json
from adafruit_servokit import ServoKit
from DRV8825 import DRV8825
import math, time
import numpy as np
from threading import Thread
from pathlib import Path


DEFAULT_SERVO_ANGLE = 90


def map_range(value, start1, stop1, start2, stop2):
   return (value - start1) / (stop1 - start1) * (stop2 - start2) + start2


class AnimationPlayer(object):
    def __init__(self):
        #self.base_layer = AnimationLayer
        self.stack = []
        self.framerate = 12
        self.kit = ServoKit(channels=16)
        self.stopped = False
        self._is_playing = False
        #self.looping = False
        self.servos = {}
        self.steppers = {}
        
    def add_layer(self, layer):
        self.stack.append(layer)
        
    def remove_layer(self, layer):
        self.stack.remove(layer)
        
    def set_layer_weight(self, layer, weight):
        layer.weight = weight
        anim_idx = self.stack.index(layer)
        weights = np.array([anim.weight for anim in self.stack])
        
        # Calculate the sum of the weights without the modified item
        sum_without_modified_item = np.sum(weights) - weight
        
        # Calculate the scaling factor required to adjust the sum to 1.0
        scaling_factor = 1.0 / sum_without_modified_item
        
        # Apply the scaling factor to the remaining items in the array
        weights = (weights - weight) * scaling_factor
        weights[anim_idx] = weight
                
        for anim, norm_weight in zip(self.stack, weights):
            print(f"Setting weight of layer {anim} to {norm_weight}")
            anim.weight = norm_weight
        
    def update(self):
        while True:
            # Animation update code here
            if not len(self.stack):
                time.sleep(0.1)
                continue
            
            if self._is_playing:
                weighted_layer_sum = np.zeros(len(self.servos)) 
                for anim in self.stack:
                    anim.update()
                    
                    # Read and sum angles together
                    anim_angles = np.zeros(len(self.servos))
                    servo_idx = 0
                    for servo_id, servo in self.servos.items():
                        anim_angles[servo_idx] = anim.servo_angle(servo_id)
                        servo_idx += 1
                    weighted_layer_sum += anim_angles * anim.weight
                                
                # Rotate servos
                for servo_id, angle in zip(self.servos, weighted_layer_sum):
                    self.rotate_servo(servo_id, angle)           
            
            time.sleep(1 / self.framerate)
            
            # Quit thread
            if self.stopped:
                break
    
    def start(self):
        Thread(target=self.update,args=()).start()
        return self
    
    def stop(self):
        self._is_playing = False
        #self.looping = False
        
    def play(self):
        self._is_playing  = True
        
    def add_servo(self, servo_id, servo_name, remap_fn=None, pulse_width=None):
        self.servos[servo_id] = {
            "servo": self.kit.servo[servo_id],
            "remap": remap_fn if remap_fn else lambda angle: angle
        }
        if pulse_width:
            self.servos[servo_id]["servo"].set_pulse_width_range(pulse_width[0], pulse_width[1])
            
    def rotate_servo(self, servo_id, value):
        self.servos[servo_id]["servo"].angle = self.servos[servo_id]["remap"](value)


class AnimationLayer(object):
    def __init__(self, animation, loop = False, weight = 1.0, on_completed_fn = lambda: None):
        self.looping = loop
        self.current_animation = animation
        self.bone_direction_remap = {}
        self.current_frame = 0
        self.weight = weight
        self._is_playing = True
        self.on_complete = on_completed_fn
        
    def start(self):
       pass
    
    def play(self, loop=False, from_frame=0):
        self.current_frame = from_frame
        self._is_playing = True
        self.looping = loop
        
    def pause(self):
        self._is_playing = False
        
    def resume(self):
        self._is_playing = True
    
    def stop(self):
        self._is_playing = False
        
    def join(self):
        self.stopped  = True
        
    def servo_angle(self, servo_id):
        if self.current_animation:
            return self.current_animation.servo_pos_at_frame(servo_id, self.current_frame)
        return DEFAULT_SERVO_ANGLE
        
    def update(self):
        #for servo_id in self.current_animation.data["servos"]:
        #    self.rotate_servo(int(servo_id), self.current_animation.servo_pos_at_frame(servo_id, self.current_frame))
        
        # Increment frame counter
        self.current_frame += 1
            
        # Stop or loop the animation
        if self.current_animation:
            if self.current_frame == self.current_animation.frames():
                self.current_frame = 0
                self.on_complete()
                if not self.looping:
                    self.stop()  
        
    def is_playing(self):
        return self._is_playing


class Animation(object):
    def __init__(self, path):        
        f = open(path)
        self.data = json.load(f)
        f.close()
        
    def framerate(self):
        return int(self.data["fps"])
    
    def frames(self):
        return int(self.data["frames"])
    
    def servo_pos_at_frame(self, servo_id, frame):
        return int(self.data["servos"][str(servo_id)]["positions"][frame])
     

if __name__ == "__main__":
    player = AnimationPlayer().start()
    player.add_servo(15, "shoulder.R", None,  (500, 2500))
    player.add_servo(14, "elbow.R", None,  (500, 2500))
    player.add_servo(13, "hand.R", None,  (500, 2500))
    player.add_servo(11, "shoulder.L", None,  (500, 2500))
    player.add_servo(10, "elbow.L", None,  (500, 2500))
    player.add_servo(12, "hand.L", None,  (500, 2500))
    
    Motor1 = DRV8825(dir_pin=24, step_pin=18, enable_pin=4, mode_pins=(21, 22, 27))
    Motor1.SetMicroStep('softward','fullstep')
    Motor1.Stop()
    def stepper_wiggle():
        sleepdelay = 0.52
        steps = 175
        stepdelay = 0.0035
        Motor1.TurnStep(Dir='forward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='backward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='forward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='backward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='forward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='backward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='forward', steps=steps, stepdelay=stepdelay)
        time.sleep(sleepdelay)
        Motor1.TurnStep(Dir='backward', steps=steps, stepdelay=stepdelay)
        Motor1.Stop()
        
    
    #anim1 = Animation(Path( __file__ ).absolute().parent / ".." / "Animations" / "ServoArm_LeftWave.json")
    #anim2 = Animation(Path( __file__ ).absolute().parent / ".." / "Animations" / "ServoArm_RightBeckon.json")
    #anim_layer1 = AnimationLayer(anim1, True, 1.0)
    #anim_layer2 = AnimationLayer(anim2, True, 0.0)
    #player.add_layer(anim_layer1)
    #player.add_layer(anim_layer2)
    anim1 = Animation(Path( __file__ ).absolute().parent / ".." / "Animations" / "demoloop.json")
    anim_layer1 = AnimationLayer(anim1, True, 1.0)#, stepper_wiggle)
    player.add_layer(anim_layer1)
    player.play()