# COMPUTER VISION SETUP

the project involves streaming video captured by the Pi camera to my
development machine running ubuntu jazzy 24.04 the payload captured is
used for detection by YOLO26 model where the output is published by
topic /detections

## TOOLS USED:

Raspberry Pi 5 Pi 
camera V2 
linux development machine

## find PI and laptop ip

hostname -I

## run sender script (pi)
### Create the sender script
cat > ~/sender_pi.sh << 'EOF'
#!/usr/bin/env bash
# rpicam-vid (system libcamera) -> x264 -> RTP over TCP. The laptop connects in.
unset GST_PLUGIN_PATH
PORT=${PORT:-5600}; W=${W:-640}; H=${H:-480}; FPS=${FPS:-15}
LD_LIBRARY_PATH=/lib/aarch64-linux-gnu rpicam-vid -t 0 -n \
  --width $W --height $H --framerate $FPS --codec yuv420 --flush -o - | \
gst-launch-1.0 -e fdsrc fd=0 ! \
  rawvideoparse format=i420 width=$W height=$H framerate=$FPS/1 ! \
  x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=$FPS ! \
  h264parse config-interval=1 ! rtph264pay pt=96 config-interval=1 ! \
  rtpstreampay ! tcpserversink host=0.0.0.0 port=$PORT sync=false
EOF
chmod +x ~/sender_pi.sh

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

# UDP SETUP
## clone repo
git clone https://github.com/mututamumo/yolo_stream.git
cd ~/yolo_stream


# Run on both the Raspberry Pi and the Laptop
hostname -I

# Or on Linux/WSL to list IPv4 addresses clearly:
ip -4 addr | grep -w inet

### Open PowerShell as Administrator, add the firewall rules for UDP port 5600, and restart WSL:powershell
New-NetFirewallHyperVRule -Name "yolo-udp" -DisplayName "yolo udp 5600" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol UDP -LocalPorts 5600

New-NetFirewallRule -DisplayName "yolo-udp-5600" -Direction Inbound -Protocol UDP -LocalPort 5600 -Action Allow

wsl --shutdown


## Verify UDP Connectivity

Test that UDP packets reach your laptop from the Pi:
• On Laptop: nc -u -l 5600
• On Pi: echo hello | nc -u -w1 <LAPTOP_IP> 5600

## Create & Run the UDP Sender (Raspberry Pi)

cat > ~/sender_pi_udp.sh << 'EOF'
#!/usr/bin/env bash
# rpicam-vid (system libcamera) -> x264 -> RTP over UDP to the laptop.
unset GST_PLUGIN_PATH
LAPTOP=${LAPTOP:?set LAPTOP=<laptop LAN address>}
PORT=${PORT:-5600}; W=${W:-640}; H=${H:-480}; FPS=${FPS:-15}
LD_LIBRARY_PATH=/lib/aarch64-linux-gnu rpicam-vid -t 0 -n \
  --width $W --height $H --framerate $FPS --codec yuv420 --flush -o - | \
gst-launch-1.0 -e fdsrc fd=0 ! \
  rawvideoparse format=i420 width=$W height=$H framerate=$FPS/1 ! \
  x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=$FPS ! \
  h264parse config-interval=1 ! rtph264pay pt=96 config-interval=1 ! \
  udpsink host=$LAPTOP port=$PORT sync=false
EOF
chmod +x ~/sender_pi_udp.sh

## Start streaming to your laptop's IP address:

LAPTOP=<LAPTOP_IP> ~/sender_pi_udp.

##  Run the ROS 2 Detection Pipeline (Laptop)

### Run the three-terminal pipeline on your laptop with ROS 2 Jazzy and 

rmw_zenoh_cpp configured: start the Zenoh router :

 ros2 run rmw_zenoh_cpp rmw_zenohd

launch yolo_node.py in UDP mode (leaving PI_HOST unset for local port 5600) with:
 
 python yolo_node.py --ros-args -p show:=true -p conf:=0.3

 and verify output using 
 
 ros2 topic echo /detections --once --no-daemon.

