import gi, numpy as np
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp  # noqa: F401 (GstApp adds appsink methods)
Gst.init(None)


class GstReceiver:
    def __init__(self, port=5600, host=None):
        if host:    # TCP client: connect out to the Pi
            src = (f'tcpclientsrc host={host} port={port} '
                   '! application/x-rtp-stream,media=video,encoding-name=H264,payload=96 '
                   '! rtpstreamdepay ')
        else:       # UDP listener (loopback tests)
            src = (f'udpsrc port={port} caps="application/x-rtp,media=video,'
                   'encoding-name=H264,payload=96" '
                   '! rtpjitterbuffer latency=50 drop-on-latency=true ')
        self.pipe = Gst.parse_launch(
            src + '! rtph264depay ! h264parse ! avdec_h264 ! videoconvert '
            '! video/x-raw,format=BGR '
            '! appsink name=sink drop=true max-buffers=1 sync=false')
        self.sink = self.pipe.get_by_name("sink")
        self.pipe.set_state(Gst.State.PLAYING)

    def get_frame(self, timeout_ms=100):
        s = self.sink.try_pull_sample(timeout_ms * Gst.MSECOND)
        if s is None:
            return None
        st = s.get_caps().get_structure(0)
        w, h = st.get_value("width"), st.get_value("height")
        buf = s.get_buffer()
        ok, m = buf.map(Gst.MapFlags.READ)
        frame = np.frombuffer(m.data, np.uint8).reshape(h, w, 3).copy()
        buf.unmap(m)
        return frame

    def close(self):
        self.pipe.set_state(Gst.State.NULL)
