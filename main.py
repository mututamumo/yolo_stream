import os, time, cv2
from gst_receiver import GstReceiver
from detector import YoloOnnx

HOST = os.environ.get("PI_HOST")             # Pi address; unset = UDP loopback test
CONF = float(os.environ.get("CONF", "0.3"))  # confidence threshold
NAMES = ["metal", "organic", "plastic"]

rx = GstReceiver(5600, host=HOST)
det = YoloOnnx("model.onnx", conf=CONF)
t0, n = time.time(), 0
while True:
    frame = rx.get_frame()
    if frame is None:
        continue
    for cls, conf, x1, y1, x2, y2 in det(frame):
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        cv2.putText(frame, f"{NAMES[cls]} {conf:.2f}", (int(x1), int(y1) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    n += 1
    if n % 30 == 0:
        print(f"{n / (time.time() - t0):.1f} FPS")
        t0, n = time.time(), 0
    cv2.imshow("yolo", frame)
    if cv2.waitKey(1) == 27:      # Esc to quit
        break
rx.close()
