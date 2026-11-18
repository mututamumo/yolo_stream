# COMPUTER VISION SETUP

the project involves streaming video captured by the Pi camera to my
development machine running ubuntu jazzy 24.04 the payload captured is
used for detection by YOLO26 model where the output is published by
topic /detections

## TOOLS USED:

Raspberry Pi 5 Pi camera V2 linux development machine

## find PI and laptop ip

hostname -I

## run sender script (pi)

\~/sender_pi.sh

## Set up the environment and the Pi's address

cd \~/yolo_stream && source .venv/bin/activate export
PI_HOST=192.168.x.x

## Check the Pi is reachable and listening:

nc -vz \$PI_HOST 5600

## (test)Pull one frame (on laptop)

python -c " from gst_receiver import GstReceiver import time rx =
GstReceiver(5600, host='\$PI_HOST'); time.sleep(3) f =
rx.get_frame(3000) print('frame:', None if f is None else f.shape)
rx.close()"

Expected: frame: (480, 640, 3)

## Laptop (run the model with a window)

Every ROS terminal starts with these three lines (ROS before the venv)

source /opt/ros/jazzy/setup.bash export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd \~/yolo_stream && source .venv/bin/activate && export
PI_HOST=192.168.x.x

## run terminals on the laptop

1 ros2 run rmw_zenoh_cpp rmw_zenohd

2 python yolo_node.py --ros-args -p host:=\$PI_HOST -p show:=true -p
conf:=0.3

3 ros2 topic echo /detections --no-daemon
