import json
from adafruit_servokit import ServoKit
import math, time
from threading import Thread
from pathlib import Path


def map_range(value, start1, stop1, start2, stop2):
   return (value - start1) / (stop1 - start1) * (stop2 - start2) + start2


class AnimationPlayer(object):
    def __init__(self):
        self._is_playing = False
        self.looping = False
        self.stopped = False
        self.kit = ServoKit(channels=16)
        self.bone_direction_remap = {}
        self.servos = {}
        self.current_animation = None
        self.current_frame = 0
        
    def add_servo(self, servo_id, servo_name, remap_fn=None, pulse_width=None):
        self.servos[servo_id] = {
            "servo": self.kit.servo[servo_id],
            "remap": remap_fn if remap_fn else lambda angle: angle
        }
        if pulse_width:
            self.servos[servo_id]["servo"].set_pulse_width_range(pulse_width[0], pulse_width[1])
            
    def rotate_servo(self, servo_id, value):
        self.servos[servo_id]["servo"].angle = self.servos[servo_id]["remap"](value)
        
    def start(self):
        Thread(target=self.update,args=()).start()
        return self
    
    def play(self, animation, loop=False, from_frame=0):
        self._is_playing  = True
        self.current_frame = from_frame
        self.current_animation = animation
        self.looping = loop
        
    def pause(self):
        self._is_playing = False
        
    def resume(self):
        self._is_playing = True
    
    def stop(self):
        self._is_playing = False
        self.looping = False
        
    def join(self):
        self.stopped  = True
        
    def update(self):
        while True:
            # Animation update code here
            if not self.current_animation:
                time.sleep(0.1)
                continue
            
            if self._is_playing:
                for servo_id in self.current_animation.data["servos"]:
                    self.rotate_servo(int(servo_id), self.current_animation.servo_pos_at_frame(servo_id, self.current_frame))
            
                # Increment frame counter
                time.sleep(1 / self.current_animation.framerate())
                self.current_frame += 1
            
            # Stop or loop the animation
            if self.current_frame == self.current_animation.frames():
                self.current_frame = 0
                if not self.looping:
                    self.stop()
            
            # Quit thread
            if self.stopped:
                break
        
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
    
    anim = Animation(Path( __file__ ).absolute().parent / ".." / "Animations" / "wave_left.json")
    player.play(anim, True)