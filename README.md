# Computer Vision Pipeline Setup (`yolo_stream`)

This guide helps a new developer set up the Raspberry Pi 5 camera stream, run YOLO26 ONNX inference on a development machine, and publish detections to ROS 2 topic `/detections`.

## 1. System overview

- **Edge device:** Raspberry Pi 5 + Raspberry Pi Camera Module V2 (IMX219)
- **Development machine:** Ubuntu 24.04 / ROS 2 Jazzy, native Linux or Windows WSL2
- **Video:** GStreamer, H.264 over TCP or UDP, port `5600`
- **Inference:** YOLO26 ONNX using ONNX Runtime
- **ROS middleware:** `rmw_zenoh_cpp`
- **Output:** `vision_msgs/msg/Detection2DArray` on `/detections`

The Pi captures and sends video. The laptop receives and decodes it, runs inference, and publishes detection messages. Video and detections use separate channels.

## 2. Network preparation

Connect both devices to the same local network. Some campus/public Wi-Fi networks isolate clients; use a network that permits device-to-device communication.

On the Pi:

```bash
hostname -I
```

On the development machine:

```bash
ip -4 addr | grep -w inet
```

Record the LAN addresses as `<PI_ADDRESS>` and `<LAPTOP_ADDRESS>`. From the laptop, test the Pi:

```bash
ping -c 2 <PI_ADDRESS>
```

## 3. Clone the repository

```

Clone the project branch containing the setup and requirements file:

```bash
git clone -b requirements https://github.com/mututamumo/yolo_stream.git
cd yolo_stream
```

If the project has since been merged into `main`, use:

```bash
git clone https://github.com/mututamumo/yolo_stream.git
cd yolo_stream
```

Check the files:

```bash
git branch --show-current
ls
```

The project needs `gst_receiver.py`, `detector.py`, `main.py`, `yolo_node.py`, `requirements.txt`, and `model.onnx`. If `model.onnx` is not tracked in the repository, obtain the approved ONNX model separately and place it in `~/yolo_stream/model.onnx`.

## 4. Install laptop dependencies



### 4.2 GStreamer and system Python packages

```bash
sudo apt install -y \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  python3-gi \
  gir1.2-gst-plugins-base-1.0 \
  python3-venv \
  python3-opencv
```

Check the required GStreamer elements:

```bash
for e in x264enc avdec_h264 rtph264pay rtph264depay rtpstreampay rtpstreamdepay h264parse rtpjitterbuffer udpsrc udpsink tcpclientsrc tcpserversink videoconvert appsink; do
  gst-inspect-1.0 "$e" >/dev/null 2>&1 && echo "OK   $e" || echo "MISS $e"
done
```

Resolve any `MISS` entries before continuing. `x264enc` is provided by `gstreamer1.0-plugins-ugly`; `avdec_h264` is provided by `gstreamer1.0-libav`.

### 4.3 Python virtual environment

Create the environment with system packages enabled so Python can access the apt-installed GStreamer bindings and OpenCV:

```bash
cd ~/yolo_stream
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Do not `pip install opencv-python`; use Ubuntu's `python3-opencv` package to avoid conflicts with ROS 2's Python packages.

Verify imports:

```bash
python -c "import numpy, cv2, onnxruntime, gi; print(numpy.__version__, cv2.__version__, onnxruntime.__version__); gi.require_version('Gst','1.0'); from gi.repository import Gst; Gst.init(None); print(Gst.version_string())"
```

Verify the ONNX model:

```bash
python -c "import onnxruntime as ort; s=ort.InferenceSession('model.onnx'); print([(x.name, x.shape) for x in s.get_inputs()]); print([(x.name, x.shape) for x in s.get_outputs()])"
```

## 5. Prepare the Raspberry Pi

On the Pi, check the camera:

```bash
rpicam-hello --list-cameras
```

For the Camera Module V2, the sensor is commonly identified as IMX219. If a libcamera symbol error occurs, try:

```bash
LD_LIBRARY_PATH=/lib/aarch64-linux-gnu rpicam-hello --list-cameras
```

Install GStreamer:

```bash
sudo apt update
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly
```

Check sender elements:

```bash
for e in fdsrc rawvideoparse x264enc h264parse rtph264pay rtpstreampay tcpserversink udpsink; do
  gst-inspect-1.0 "$e" >/dev/null 2>&1 && echo "OK   $e" || echo "MISS $e"
done
```

## 6. Choose a transport

| Transport | Behaviour | Notes |
|---|---|---|
| TCP | Laptop connects to the Pi; lost data is retransmitted. | Easiest first setup; works with default WSL2 networking. |
| UDP | Pi sends packets to the laptop; lost packets are not retransmitted. | Can provide steadier low latency on busy Wi-Fi, but requires inbound UDP access. |

Start with TCP to validate the camera and model. Set up UDP after TCP works.

## 7. TCP video stream

### 7.1 Start the sender on the Pi

The repository may include `sender_pi.sh`. If not, create it on the Pi:

```bash
cat > ~/sender_pi.sh << 'EOF'
#!/usr/bin/env bash
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
```

Run and leave it running:

```bash
~/sender_pi.sh
```

### 7.2 Receive a test frame on the laptop

```bash
cd ~/yolo_stream
source .venv/bin/activate
export PI_HOST=<PI_ADDRESS>
nc -vz "$PI_HOST" 5600
```

Then:

```bash
python -c "
from gst_receiver import GstReceiver
import time
rx = GstReceiver(5600, host='$PI_HOST')
time.sleep(3)
f = rx.get_frame(3000)
print('frame:', None if f is None else f.shape)
rx.close()
"
```

Expected:

```text
frame: (480, 640, 3)
```

### 7.3 Run detection without ROS

```bash
python main.py
```

A window should show the camera feed with detection boxes and labels. Press `Esc` to exit.

## 8. UDP video stream (optional)

### 8.1 WSL2 networking configuration

Native Ubuntu users can skip this subsection.

On Windows 11, edit `%UserProfile%\\.wslconfig` and add:

```ini
[wsl2]
networkingMode=mirrored
```

Open PowerShell as Administrator and run:

```powershell
New-NetFirewallHyperVRule -Name "yolo-udp" -DisplayName "yolo udp 5600" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol UDP -LocalPorts 5600
New-NetFirewallRule -DisplayName "yolo-udp-5600" -Direction Inbound -Protocol UDP -LocalPort 5600 -Action Allow
wsl --shutdown
```

Reopen WSL and find the laptop LAN address:

```bash
ip -4 addr | grep -w inet
```

### 8.2 Test UDP connectivity

On the laptop:

```bash
nc -u -l 5600
```

On the Pi:

```bash
echo hello | nc -u -w1 <LAPTOP_ADDRESS> 5600
```

The laptop should display `hello`. Stop the listener with `Ctrl+C`. Do not continue until the test succeeds.

### 8.3 Create and run the UDP sender on the Pi

```bash
cat > ~/sender_pi_udp.sh << 'EOF'
#!/usr/bin/env bash
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
```

Start the sender using the laptop's LAN address:

```bash
LAPTOP=<LAPTOP_ADDRESS> ~/sender_pi_udp.sh
```

On the laptop, unset `PI_HOST` so the receiver listens for UDP:

```bash
cd ~/yolo_stream
source .venv/bin/activate
unset PI_HOST
python main.py
```

Only one process can receive on port `5600` at a time. Stop any other receiver first.

## 9. Publish detections with ROS 2

In every ROS terminal, source ROS **before** activating the virtual environment:

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd ~/yolo_stream
source .venv/bin/activate
```

Use three laptop terminals.

### Terminal 1 — Zenoh router

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd ~/yolo_stream && source .venv/bin/activate
ros2 run rmw_zenoh_cpp rmw_zenohd
```

Leave this terminal running.

### Terminal 2 — YOLO ROS node

For **TCP**:

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd ~/yolo_stream && source .venv/bin/activate
export PI_HOST=<PI_ADDRESS>
python yolo_node.py --ros-args -p host:=$PI_HOST -p show:=true -p conf:=0.3
```

For **UDP**:

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd ~/yolo_stream && source .venv/bin/activate
unset PI_HOST
python yolo_node.py --ros-args -p show:=true -p conf:=0.3
```

Make sure the matching Pi sender is running.

### Terminal 3 — Verify detections

```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
cd ~/yolo_stream && source .venv/bin/activate
ros2 topic echo /detections --once --no-daemon
```

Check the message type:

```bash
ros2 topic type /detections --no-daemon
```

Expected:

```text
vision_msgs/msg/Detection2DArray
```

An empty `detections` array means no objects passed the confidence threshold in that frame; it does not necessarily mean the node is stopped.

## 10. Session checklist

**TCP**
1. Pi: `~/sender_pi.sh`
2. Laptop: activate `.venv`, set `PI_HOST=<PI_ADDRESS>`.
3. Run `python main.py`, or start the ROS router and `yolo_node.py` with the TCP host parameter.

**UDP**
1. Confirm the laptop can receive UDP on port `5600`.
2. Laptop: activate `.venv`, run `unset PI_HOST`.
3. Pi: `LAPTOP=<LAPTOP_ADDRESS> ~/sender_pi_udp.sh`.
4. Run `python main.py`, or start the ROS router and `yolo_node.py` without a host parameter.

Stop the laptop receiver/detector and ROS processes first, then stop the Pi sender with `Ctrl+C`. Only one sender should own the Pi camera at a time.

## 11. Troubleshooting

| Symptom | Likely cause / action |
|---|---|
| TCP connection refused | Start the Pi TCP sender; check port `5600`. |
| Ping or connection timeout | Check that both devices share a network and client isolation is disabled. |
| UDP test packet does not arrive in WSL2 | Check mirrored networking, firewall rules, and run `wsl --shutdown`. |
| `frame: None` | Check the sender and wait for a keyframe; retry after a few seconds. |
| `Address already in use` | Stop the other receiver using port `5600`. |
| Camera busy | Stop other camera/sender processes. |
| `No module named rclpy` | Source ROS before activating `.venv`. |
| ROS topics are not visible | Set `RMW_IMPLEMENTATION=rmw_zenoh_cpp` in every ROS terminal. |
| No detections | Confirm video arrives; try a lower confidence threshold, e.g. `0.15`. |
| GStreamer element missing | Install the relevant plugin package and re-run `gst-inspect-1.0`. |

## 12. Notes

- The supplied sender settings default to 640 × 480 at 15 FPS. Keep `rpicam-vid` and `rawvideoparse` settings matched.
- TCP is the simplest initial setup. UDP requires inbound port access and may behave better on lossy Wi-Fi, but compare it under the actual network conditions.
- Keep `model.onnx` in the repository root.
- Do not commit access tokens, `.venv`, or machine-specific credentials.
- Re-check IP addresses whenever either device changes networks or receives a new DHCP address.
