######## Webcam Object Detection Using Tensorflow-trained Classifier #########
#
# Author: Evan Juras
# Date: 10/27/19
# Description: 
# This program uses a TensorFlow Lite model to perform object detection on a live webcam
# feed. It draws boxes and scores around the objects of interest in each frame from the
# webcam. To improve FPS, the webcam object runs in a separate thread from the main program.
# This script will work with either a Picamera or regular USB webcam.
#
# This code is based off the TensorFlow Lite image classification example at:
# https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/examples/python/label_image.py
#
# I added my own method of drawing boxes and labels using OpenCV.

# Import packages
import os
import argparse
import cv2
import math
import numpy as np
import sys
import time
from threading import Thread
from Stepper.steppercontrol import StepperControl
import importlib.util

def get_screen_center():
    return (math.floor(imW * 0.5), math.floor(imH * 0.5))


# Define VideoStream class to handle streaming of video from webcam in separate processing thread
# Source - Adrian Rosebrock, PyImageSearch: https://www.pyimagesearch.com/2015/12/28/increasing-raspberry-pi-fps-with-python-and-opencv/
class VideoStream:
    """Camera object that controls video streaming from the Picamera"""
    def __init__(self,resolution=(640,480),framerate=30,flip=False):
        # Initialize the PiCamera and the camera image stream
        self.stream = cv2.VideoCapture(0)
        ret = self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret = self.stream.set(3,resolution[0])
        ret = self.stream.set(4,resolution[1])
        self.flip = flip
            
        # Read first frame from the stream
        (self.grabbed, self.frame) = self.stream.read()
                    

	# Variable to control when the camera is stopped
        self.stopped = False

    def start(self):
	# Start the thread that reads frames from the video stream
        Thread(target=self.update,args=()).start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        while True:
            # If the camera is stopped, stop the thread
            if self.stopped:
                # Close camera resources
                self.stream.release()
                return

            # Otherwise, grab the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
	# Return the most recent frame
        return self.frame
        #return cv2.flip(self.frame, 0) if self.flip else self.frame

    def stop(self):
	# Indicate that the camera and thread should be stopped
        self.stopped = True
        

class Recogniser(object):
    def __init__(self, videostream):
        self.videostream = videostream
        self.stopped = False
        self.__people_bb = []
        self.__closest_person_bb = None
        self.__found_person = False
    
    def start(self):
        Thread(target=self.update,args=()).start()
        return self
    
    def stop(self):
        self.stopped = True
        
    def get_all_people_bb(self):
        return self.__people_bb
    
    def get_closest_person_bb(self):
        return self.__closest_person_bb
    
    def get_bb_dist_to_center(self, bbox):
        screen_center = get_screen_center()
        
        ymin = int(max(1,(bbox[0] * imH)))
        xmin = int(max(1,(bbox[1] * imW)))
        ymax = int(min(imH,(bbox[2] * imH)))
        xmax = int(min(imW,(bbox[3] * imW)))  
    
        x_center = int((xmax + xmin) * 0.5)
        return screen_center[0] - x_center
    
    def get_abs_person_dist_to_center(self, bbox):
        return abs(self.get_bb_dist_to_center(bbox))
    
    def found_person(self):
        return self.__found_person
    
    def update(self):
        # Initialize frame rate calculation
        frame_rate_calc = 1
        freq = cv2.getTickFrequency()

        while True:
            if self.stopped:
                return
            
            # Start timer (for calculating frame rate)
            t1 = cv2.getTickCount()

            # Grab frame from video stream
            frame1 = videostream.read()

            # Acquire frame and resize to expected shape [1xHxWx3]
            frame = frame1.copy()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_resized = cv2.resize(frame_rgb, (width, height))
            input_data = np.expand_dims(frame_resized, axis=0)

            # Normalize pixel values if using a floating model (i.e. if model is non-quantized)
            if floating_model:
                input_data = (np.float32(input_data) - input_mean) / input_std

            # Perform the actual detection by running the model with the image as input
            interpreter.set_tensor(input_details[0]['index'],input_data)
            interpreter.invoke()

            # Retrieve detection results
            boxes = interpreter.get_tensor(output_details[boxes_idx]['index'])[0] # Bounding box coordinates of detected objects
            classes = interpreter.get_tensor(output_details[classes_idx]['index'])[0] # Class index of detected objects
            scores = interpreter.get_tensor(output_details[scores_idx]['index'])[0] # Confidence of detected objects
            
            found_person = False
            #person_center_x = imW
            screen_center = (math.floor(imW * 0.5), math.floor(imH * 0.5))
            
            closest_person_bb = None
            self.__people_bb = []
            prev_closest_center = imW
            # Loop over all detections and draw detection box if confidence is above minimum threshold
            for i in range(len(scores)):
                object_name = labels[int(classes[i])] # Look up object name from "labels" array using class index
                
                if ((scores[i] > min_conf_threshold) and (scores[i] <= 1.0) and object_name == "person"):
                    found_person = True
                    self.__people_bb.append(boxes[i])
                    #people_bb.append(boxes[i])
                    ymin = int(max(1,(boxes[i][0] * imH)))
                    xmin = int(max(1,(boxes[i][1] * imW)))
                    ymax = int(min(imH,(boxes[i][2] * imH)))
                    xmax = int(min(imW,(boxes[i][3] * imW)))
                    
                    x_center = int((xmin + xmax) * 0.5)
                    try:
                        if not hasattr(closest_person_bb, "any"):
                            closest_person_bb = boxes[i]
                    except TypeError:
                        closest_person_bb = boxes[i]
                        
                    prev_xmin = int(max(1,(closest_person_bb[1] * imW)))
                    prev_xmax = int(min(imW,(closest_person_bb[3] * imW)))
                    prev_closest_center = int((prev_xmin + prev_xmax) * 0.5)
                        
                    new_dist_center = abs(screen_center[0] - x_center)
                    prev_dist_center =  abs(screen_center[0] - prev_closest_center)
                    if new_dist_center < prev_dist_center:
                        #person_center_x = x_center
                        closest_person_bb = boxes[i]
            
            
            if found_person:
                self.__found_person = True
                self.__closest_person_bb = closest_person_bb
            else:
                self.__found_person = False

            # Draw label
        #     label = '%s: %d%%' % (object_name, int(scores[i]*100)) # Example: 'person: 72%'
        #     labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
        #     label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
        #     cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
        #     cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text

            # Draw framerate in corner of frame
            #cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)

            # All the results have been drawn on the frame, so it's time to display it.
            #cv2.imshow('Object detector', frame)

            # Calculate framerate
            #t2 = cv2.getTickCount()
            #time1 = (t2-t1)/freq
            #frame_rate_calc= 1/time1
        

# Define and parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('--modeldir', help='Folder the .tflite file is located in',
                    required=True)
parser.add_argument('--graph', help='Name of the .tflite file, if different than detect.tflite',
                    default='detect.tflite')
parser.add_argument('--labels', help='Name of the labelmap file, if different than labelmap.txt',
                    default='labelmap.txt')
parser.add_argument('--threshold', help='Minimum confidence threshold for displaying detected objects',
                    default=0.5)
parser.add_argument('--resolution', help='Desired webcam resolution in WxH. If the webcam does not support the resolution entered, errors may occur.',
                    default='1280x720')
parser.add_argument('--edgetpu', help='Use Coral Edge TPU Accelerator to speed up detection',
                    action='store_true')
parser.add_argument('--flip', help='Flip the webcam input',
                    action='store_true')
parser.add_argument('--deadzone', help='Distance from the center of the camera to stop rotating',
                    default=150)
parser.add_argument('--disablespin', help='Disable stepper motor for rotating the chair to face a user',
                    action='store_true')

args = parser.parse_args()

MODEL_NAME = args.modeldir
GRAPH_NAME = args.graph
LABELMAP_NAME = args.labels
min_conf_threshold = float(args.threshold)
resW, resH = args.resolution.split('x')
imW, imH = int(resW), int(resH)
flip_webcam = hasattr(args, "flip")
stepper_enabled = not args.disablespin
use_TPU = args.edgetpu
rotate_deadzone = int(args.deadzone)

print(f"Stepper enabled? {stepper_enabled}")

# Import TensorFlow libraries
# If tflite_runtime is installed, import interpreter from tflite_runtime, else import from regular tensorflow
# If using Coral Edge TPU, import the load_delegate library
pkg = importlib.util.find_spec('tflite_runtime')
if pkg:
    from tflite_runtime.interpreter import Interpreter
    if use_TPU:
        from tflite_runtime.interpreter import load_delegate
else:
    from tensorflow.lite.python.interpreter import Interpreter
    if use_TPU:
        from tensorflow.lite.python.interpreter import load_delegate

# If using Edge TPU, assign filename for Edge TPU model
if use_TPU:
    # If user has specified the name of the .tflite file, use that name, otherwise use default 'edgetpu.tflite'
    if (GRAPH_NAME == 'detect.tflite'):
        GRAPH_NAME = 'edgetpu.tflite'       

# Get path to current working directory
CWD_PATH = os.getcwd()

# Path to .tflite file, which contains the model that is used for object detection
PATH_TO_CKPT = os.path.join(CWD_PATH,MODEL_NAME,GRAPH_NAME)

# Path to label map file
PATH_TO_LABELS = os.path.join(CWD_PATH,MODEL_NAME,LABELMAP_NAME)

# Load the label map
with open(PATH_TO_LABELS, 'r') as f:
    labels = [line.strip() for line in f.readlines()]

# Have to do a weird fix for label map if using the COCO "starter model" from
# https://www.tensorflow.org/lite/models/object_detection/overview
# First label is '???', which has to be removed.
if labels[0] == '???':
    del(labels[0])

# Load the Tensorflow Lite model.
# If using Edge TPU, use special load_delegate argument
if use_TPU:
    interpreter = Interpreter(model_path=PATH_TO_CKPT,
                              experimental_delegates=[load_delegate('libedgetpu.so.1.0')])
    print(PATH_TO_CKPT)
else:
    interpreter = Interpreter(model_path=PATH_TO_CKPT)

interpreter.allocate_tensors()

# Get model details
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
height = input_details[0]['shape'][1]
width = input_details[0]['shape'][2]

floating_model = (input_details[0]['dtype'] == np.float32)

input_mean = 127.5
input_std = 127.5

# Check output layer name to determine if this model was created with TF2 or TF1,
# because outputs are ordered differently for TF2 and TF1 models
outname = output_details[0]['name']

if ('StatefulPartitionedCall' in outname): # This is a TF2 model
    boxes_idx, classes_idx, scores_idx = 1, 3, 0
else: # This is a TF1 model
    boxes_idx, classes_idx, scores_idx = 0, 1, 2

# Initialize video stream and recogniser
videostream = VideoStream(resolution=(imW,imH),framerate=1, flip=flip_webcam).start()
recogniser = Recogniser(videostream).start()

# Initialize stepper control
stepper = StepperControl(stepper_enabled)

time.sleep(1)

#for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):

while True:
    frame  = videostream.read()
    
    # Initialize blank mask image of same dimensions for drawing the shapes
    shapes = np.zeros_like(frame, np.uint8)
    
    boxes = recogniser.get_all_people_bb()
    screen_center = (math.floor(imW * 0.5), math.floor(imH * 0.5))
    
    for box in boxes:
        # Get bounding box coordinates and draw box
        # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
        ymin = int(max(1,(box[0] * imH)))
        xmin = int(max(1,(box[1] * imW)))
        ymax = int(min(imH,(box[2] * imH)))
        xmax = int(min(imW,(box[3] * imW)))  
        cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)
    
        x_center = int((xmax + xmin) * 0.5)
        #cv2.circle(frame, (int(x_center), int(screen_center[1])), 50, (0, 10, 255), 2)
        dist_center = recogniser.get_abs_person_dist_to_center(box)
        cv2.putText(frame, f"Dist: {dist_center}", (int(x_center), int(screen_center[1])-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
    if recogniser.found_person():
        person_center_x = 0
        found_person = recogniser.get_closest_person_bb()
        person_center_dist = 0
        try:
            #person_center_dist_abs = recogniser.get_abs_person_dist_to_center(found_person)
            person_center_dist = recogniser.get_bb_dist_to_center(found_person)
            person_xmin = int(max(1,(found_person[1] * imW)))
            person_xmax = int(min(imW,(found_person[3] * imW)))
            person_ymin = int(max(1,(found_person[0] * imH)))
            person_ymax = int(min(imH,(found_person[2] * imH)))
            person_center_x = int((person_xmin + person_xmax) * 0.5)
        except ValueError:
            pass
        #cv2.rectangle(frame, (int(person_center_x)-20,int(imH*0.5)-20), (int(person_center_x)+20,int(imH*0.5)+20), (0, 255, 255), 1)
        
        #  Draw thicker rectangle  to show which BB is active
        cv2.rectangle(frame, (person_xmin,person_ymin), (person_xmax,person_ymax), (10, 255, 80), 4)
        #cv2.rectangle(frame, (int(person_center_x)-20,int(imH*0.5)-20), (int(person_center_x)+20,int(imH*0.5)+20), (0, 255, 255), 1)
        #cv2.circle(frame, (int(person_center_x),int(imH*0.5)), 50, (255, 255, 255), cv2.FILLED)

        if person_center_dist < rotate_deadzone * -1:
            # Rotate left
            cv2.rectangle(shapes, (screen_center[0] + int((rotate_deadzone * 0.5)), 0), (imW, imH), (0, 255, 255), cv2.FILLED)
            stepper.rotate(-1, 200, 0.003)
            time.sleep(1)
            stepper.stop()

        elif person_center_dist > rotate_deadzone:
            # Rotate right
            cv2.rectangle(shapes, (0, 0), (screen_center[0] - int((rotate_deadzone * 0.5)), imH), (0, 255, 255), cv2.FILLED)
            stepper.rotate(1, 200, 0.003)
            time.sleep(1)
            stepper.stop()
        else:
            # Do nothing
            stepper.stop()
            
    out = frame.copy()
    alpha = 0.5
    mask = shapes.astype(bool)
    out[mask] = cv2.addWeighted(frame, alpha, shapes, 1 - alpha, 0)[mask]
    
    #cv2.imshow('Frame', frame)
    #cv2.imshow('Shapes', shapes)
    cv2.imshow('Object detector', out)

    # Press 'q' to quit
    if cv2.waitKey(1) == ord('q'):
        break

# Clean up
cv2.destroyAllWindows()
videostream.stop()
recogniser.stop()
