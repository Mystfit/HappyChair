import json
from adafruit_servokit import ServoKit
from Servo.DRV8825 import DRV8825
import math, time, os
import numpy as np
from threading import Thread, Lock
from pathlib import Path
from datetime import datetime, timedelta


DEFAULT_SERVO_ANGLE = 90


def map_range(value, start1, stop1, start2, stop2):
   return (value - start1) / (stop1 - start1) * (stop2 - start2) + start2


class Playlist(object):
    def __init__(self, path):
        self.name = os.path.basename(path)
        f = open(path)
        self.data = json.load(f)
        f.close()
    
    def get_animation_name(self, index):
        if not len(self.data):
            return ""
        return str(self.data[index]["name"])
    
    def __len__(self):
        return len(self.data)
    
    def get_animation_post_delay(self, index):
        if not len(self.data):
            return 0
        return int(self.data[index]["post_delay"])
    
    def get_pause_status(self, index):
        if not len(self.data):
            return False
        return bool(self.data[index]["pause_when_finished"]) 
        


class AnimationPlayer(object):
    PLAYLIST_MODE = "playlist"
    TRANSPORT_MODE = "transport"
    LIVE_MODE = "live"

    def __init__(self):
        self.stack = []
        self.servos = {}
        self.steppers = {}
        self.kit = ServoKit(channels=16)
        self.anim_lock = Lock()
        self.animation_thread = None
        
        self.framerate = 60
        self.stopped = False
        self._animation_mode = AnimationPlayer.TRANSPORT_MODE
        self._is_playing = False
        self._next_frame_time = datetime.now()
        
        # Interpolation
        self._interpolating = False
        self._interpolation_layer = None
        self._interpolation_start_weight = 0.0
        self._interpolation_end_weight = 1.0
        self._interpolation_start_time = 0.0
        self._interpolation_end_time = 0.0
        
        # Live servo values from external sources
        self._live_ws = False
        
        # Playlists
        self._active_playlist = None
        self._playlist_active_idx = 0
        self._playlist_next_idx = 0
        self._playlist_looping = True
        
    def animation_mode(self):
        return self._animation_mode
    
    def set_animation_mode(self, mode):
        self.set_live_mode(self.animation_mode() == AnimationPlayer.LIVE_MODE)
        self._animation_mode = mode
        
    def set_live_mode(self, active):
        if active:
            self.stop()
        else:
            self.start()
            
        self._live_ws = active
        
    def set_playlist(self, playlist: Playlist):
        self._active_playlist = playlist
        self._playlist_active_idx = 0
       
        # Hook start animation
        playlist_anim_name = self._active_playlist.get_animation_name(self._playlist_active_idx) if self._active_playlist else ""
        print(f"Playlist first animation: {playlist_anim_name}")
        if playlist_anim_name:
            playlist_layer = self.get_layer_by_name(playlist_anim_name)

        if playlist_layer: 
            print(f"Hooking onComplete function to {playlist_anim_name}")
            playlist_layer.on_complete = lambda: self.increment_playlist_animation()
            playlist_layer.set_post_delay_frames(self._active_playlist.get_animation_post_delay(self._playlist_active_idx))
            self.animate_layer_weight(playlist_layer, 1.0, 1.0)
            playlist_layer.play()

    def reset_playlist(self):
        self._playlist_active_idx = 0
        self._active_playlist = None

    def increment_playlist_animation(self):
        # Reset current animation hook since it has finished playing
        playlist_anim_name = self._active_playlist.get_animation_name(self._playlist_active_idx) if self._active_playlist else ""
        if playlist_anim_name:
            playlist_layer = self.get_layer_by_name(playlist_anim_name)
        playlist_layer.on_complete = None

        # Set up next animation. By default, the playlist will loop
        next_playlist_anim_idx = (self._playlist_active_idx + 1) % len(self._active_playlist)
        next_playlist_anim_name = self._active_playlist.get_animation_name(next_playlist_anim_idx)
        if next_playlist_anim_name:
            next_playlist_layer = self.get_layer_by_name(next_playlist_anim_name)

        print(f"Playlist transitioning from {playlist_anim_name} to {next_playlist_anim_name}")
        
        if next_playlist_layer:
            # Hook playlist increment when current animation finishes playing
            next_playlist_layer.on_complete = lambda: self.increment_playlist_animation()
            next_playlist_layer.set_post_delay_frames(self._active_playlist.get_animation_post_delay(next_playlist_anim_idx))

            # Interpolate next animation to avoid rapid servo movements
            self.animate_layer_weight(next_playlist_layer, 1.0, 1.5)
            next_playlist_layer.play()
        
        # Increment playlist index 
        self._playlist_active_idx = next_playlist_anim_idx
                
    def add_layer(self, layer):
        self.stack.append(layer)
        
    def remove_layer(self, layer):
        self.stack.remove(layer)
        
    def get_layer_by_name(self, layer_name):
        layers = [layer for layer in self.stack if layer.current_animation.name.split('.json')[0] == layer_name]
        return layers[0] if len(layers) else None
        
    def animate_layer_weight(self, layer, weight, duration):
        self._interpolating = True
        self._interpolation_start_time = datetime.now()
        self._interpolation_end_time = self._interpolation_start_time + timedelta(seconds=duration)
        self._interpolation_start_weight = layer.weight
        self._interpolation_end_weight = weight
        self._interpolation_layer = layer
        
    def set_layer_weight(self, layer, weight):
        # Weights can only be in the range 0.0-1.0
        weight = max(min(weight, 1.0), 0.0)
        weights = np.array([anim.weight for anim in self.stack])
        anim_idx = self.stack.index(layer)
        
        # Calculate the sum of the weights without the modified item
        sum_without_modified_item = np.sum(weights) - weights[anim_idx] + weight        
        weights[anim_idx] = weight
        
        # Calculate the scaling factor required to adjust the sum to 1.0
        scaling_factor = 1.0 / (sum_without_modified_item + weight)#(sum_without_modified_item + weight)
        if scaling_factor >= 0:
            for i in range(len(weights)):
                if i != anim_idx:
                    weights[i] *= scaling_factor
        else:
            print("Scaling factor is negative")
            weights[anim_idx] = 1.0
            
            # Recalculate the scaling factor and distribute proportionally
            scaling_factor = 1.0 / (sum_without_modified_item - weights[anim_idx])
            for i in range(len(arr)):
                if i != anim_idx:
                    weights[i] *= scaling_factor
        
        # Aquire anim lock so we don't end up with broken weights whilst the anim thread reads from the layer stack
        with self.anim_lock:
            # Set normalized weights
            for anim, norm_weight in zip(self.stack, weights):
                clamped_weight = round(max(min(norm_weight, 1.0), 0.0),3)
                #print(f"Setting weight of layer {anim.current_animation.name} to {clamped_weight}")
                anim.weight = clamped_weight
        
    def update(self):
        while True:
            # Animation update code here
            if not len(self.stack):
                time.sleep(0.1)
                continue
            
            current_frame_time = datetime.now()
            
            if self._is_playing:
                #print(f"Current frame time: {current_frame_time}, Next frame time: {self._next_frame_time}")
                if current_frame_time >= self._next_frame_time:
                    self._next_frame_time = current_frame_time + timedelta(seconds=(1.0 / self.framerate))
                    
                    # Interpolate weights
                    if self._interpolating:
                        current_time = datetime.now()
                        if current_time >= self._interpolation_end_time:
                            # Stop interpolating 
                            self.set_layer_weight(self._interpolation_layer, self._interpolation_end_weight)
                            self._interpolation_layer = None
                            self._interpolating = False
                        else:
                            duration = self._interpolation_end_time - self._interpolation_start_time
                            
                            lerp_amt = float((current_time - self._interpolation_start_time) / duration)
                            interpolated_weight = map_range(lerp_amt, 0.0, 1.0, self._interpolation_start_weight, self._interpolation_end_weight)
                            self.set_layer_weight(self._interpolation_layer, interpolated_weight)
                    
                    # Update all animation counters
                    for anim in self.stack:
                        anim.update()
                    
                    # Aquire animation lock to guarantee normalized weights
                    with self.anim_lock:
                        weighted_layer_sum = np.zeros(len(self.servos))
                        for anim in self.stack:
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
                        
            # Quit thread
            if self.stopped:
                print("Stopping animation player thread")
                break
    
    def start(self):
        self.stopped = False
        self.animation_thread = Thread(target=self.update,args=()).start()
        return self
    
    def stop(self):
        self.pause()
        
        # Remove power from servos
        for servo_id in self.servos:
           self.rotate_servo(servo_id, None)
           
        for anim in self.stack:
            anim.current_frame = 0
            
        self.stopped = True
            
        #self.looping = False
        
    def pause(self):
        self._is_playing = False
        self._next_frame_time = datetime.now()
        
    def play(self):
        self._is_playing  = True
        
    def is_playing(self):
        return  self._is_playing
        
    def add_servo(self, servo_id, servo_name, remap_fn=None, pulse_width=None):
        self.servos[servo_id] = {
            "servo": self.kit.servo[servo_id],
            "remap": remap_fn if remap_fn else lambda angle: angle
        }
        if pulse_width:
            self.servos[servo_id]["servo"].set_pulse_width_range(pulse_width[0], pulse_width[1])
            
    def rotate_servo(self, servo_id, value):
        try:
            angle = self.servos[servo_id]["remap"](value) if value is not None else None
            self.servos[servo_id]["servo"].angle = angle
        except ValueError as e:
            print(f"Angle {angle} out of range for servo {servo_id}. Ignoring")


class AnimationLayer(object):
    def __init__(self, animation, loop = False, weight = 1.0, on_completed_fn = lambda: None):
        self.looping = loop
        self.current_animation = animation
        self.bone_direction_remap = {}
        self.current_frame = 0
        self.weight = weight
        self._is_playing = True
        self._post_delay_frames = 0
        self._current_post_delay_frame_count = 0
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

    def set_post_delay_frames(self, delay_frames):
        print(f'Setting post-delay to {delay_frames} for animation {self.current_animation.name.split(".json")[0]}')
        self._post_delay_frames = delay_frames
        
    def servo_angle(self, servo_id):
        if self.current_animation:
            return self.current_animation.servo_pos_at_frame(servo_id, self.current_frame)
        return DEFAULT_SERVO_ANGLE
        
    def update(self):
        if not self._is_playing:
            return
        
        if self.current_animation:
            if self.current_frame + 1  < self.current_animation.frames():
                # Increment frame counter
                self.current_frame += 1
            else:
                if self.current_frame + 1 >= self.current_animation.frames():
                    # We're in the post delay part of the animation
                    print(f"Animation {self.current_animation.name.split('.json')[0]} finished but waiting for post-delay to expire. { self._post_delay_frames - self._current_post_delay_frame_count } frames remaining")
                    self._current_post_delay_frame_count += 1

                if self._current_post_delay_frame_count >= self._post_delay_frames:
                    # Reset counters
                    self._current_post_delay_frame_count = 0
                    self.current_frame = 0

                    # Trigger callbacks
                    print(f'End of animation {self.current_animation.name.split(".json")[0]}')
                    if self.on_complete:
                        self.on_complete()

                    # Handle looping
                    if not self.looping:
                        self.stop()
        
    def is_playing(self):
        return self._is_playing


class Animation(object):
    def __init__(self, path):
        self.name = os.path.basename(path)
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
    anim1 = Animation(Path( __file__ ).absolute().parent / ".." / "Animations" / "wave_only.json")
    anim_layer1 = AnimationLayer(anim1, True, 1.0)#, stepper_wiggle)
    player.add_layer(anim_layer1)
    player.play()