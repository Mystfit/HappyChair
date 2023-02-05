from adafruit_servokit import ServoKit
import math, time

def map_range(value, start1, stop1, start2, stop2):
   return (value - start1) / (stop1 - start1) * (stop2 - start2) + start2


kit = ServoKit(channels=16)

bone_direction_remap = {}

shoulder_r= kit.servo[15]
elbow_r = kit.servo[14]
hand_r = kit.servo[13]
shoulder_l = kit.servo[11]
elbow_l = kit.servo[10]
hand_l = kit.servo[12]

shoulder_r.set_pulse_width_range(500, 2500)
elbow_r.set_pulse_width_range(500, 2500)
hand_r.set_pulse_width_range(500, 2500)
shoulder_l.set_pulse_width_range(500, 2500)
elbow_l.set_pulse_width_range(500, 2500)
hand_l.set_pulse_width_range(500, 2500)

bone_direction_remap[shoulder_l] = lambda angle: angle
bone_direction_remap[elbow_l] = lambda angle: angle
bone_direction_remap[hand_l] = lambda angle: map_range(angle, 0, 180, 180, 0)
bone_direction_remap[shoulder_r] = lambda angle: map_range(angle, 0, 180, 180, 0)
bone_direction_remap[elbow_r] = lambda angle: angle
bone_direction_remap[hand_r] = lambda angle: angle

def rotate_servo(servo, value):
    servo.angle = bone_direction_remap[servo](value)


shoulder_l.actuation_range = 180
elbow_l.actuation_range = 180
hand_l.actuation_range = 180

shoulder_r.actuation_range = 180
elbow_r.actuation_range = 180
hand_r.actuation_range = 180

for i in range (10):
    for i in range (100):
        rotate_servo(shoulder_r, 120-i)
        rotate_servo(hand_r, 120-i)
        time.sleep(0.05)
    for i in range (100):
        rotate_servo(shoulder_r, 20+i)
        rotate_servo(hand_r, 20+i)
        time.sleep(0.05)





