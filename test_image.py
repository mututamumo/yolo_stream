import sys, cv2
from detector import YoloOnnx

path = sys.argv[1] if len(sys.argv) > 1 else "test.jpg"
img = cv2.imread(path)
if img is None:
    sys.exit(f"Could not read image: {path}")

det = YoloOnnx("model.onnx", conf=0.25)
res = det(img)
print(len(res), "detections")
for cls, conf, x1, y1, x2, y2 in res[:10]:
    print(f"class={cls} conf={conf:.2f} box=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})")
    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
    cv2.putText(img, f"{cls} {conf:.2f}", (int(x1), int(y1) - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
cv2.imwrite("out.jpg", img)
