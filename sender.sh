#!/usr/bin/env bash
# usage: ./sender.sh test|webcam|file [path]
HOST=${HOST:-127.0.0.1}; PORT=5600
case "$1" in
  webcam) SRC="v4l2src device=/dev/video0 ! videoconvert ! videoscale" ;;
  file)   SRC="filesrc location=$2 ! decodebin ! videoconvert ! videoscale ! videorate" ;;
  images) SRC="multifilesrc location=seq/%d.jpg loop=true caps=image/jpeg,framerate=2/1 ! jpegdec ! videoconvert ! videoscale ! videorate" ;;
  *)      SRC="videotestsrc is-live=true" ;;
esac
gst-launch-1.0 $SRC ! video/x-raw,width=${W:-640},height=${H:-480},framerate=30/1 ! \
  videoconvert ! video/x-raw,format=I420 ! \
  x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=30 ! \
  h264parse config-interval=1 ! rtph264pay pt=96 config-interval=1 ! \
  udpsink host=$HOST port=$PORT
