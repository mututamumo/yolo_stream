import cv2, numpy as np, onnxruntime as ort


class YoloOnnx:
    def __init__(self, path, conf=0.5, iou=0.45):
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        inp = self.sess.get_inputs()[0]
        self.name = inp.name
        self.h = inp.shape[2] if isinstance(inp.shape[2], int) else 640
        self.w = inp.shape[3] if isinstance(inp.shape[3], int) else 640
        self.conf, self.iou = conf, iou

    def _letterbox(self, img):
        h, w = img.shape[:2]
        r = min(self.w / w, self.h / h)
        nw, nh = round(w * r), round(h * r)
        canvas = np.full((self.h, self.w, 3), 114, np.uint8)
        px, py = (self.w - nw) // 2, (self.h - nh) // 2
        canvas[py:py + nh, px:px + nw] = cv2.resize(img, (nw, nh))
        return canvas, r, px, py

    def __call__(self, bgr):
        img, r, px, py = self._letterbox(bgr)
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, swapRB=True)
        out = self.sess.run(None, {self.name: blob})[0][0]

        if out.shape[-1] == 6:                      # end-to-end (NMS-free)
            d = out[out[:, 4] > self.conf]
            xyxy, scores, cls = d[:, :4], d[:, 4], d[:, 5].astype(int)
        else:                                       # raw head, needs NMS
            if out.shape[0] < out.shape[1]:
                out = out.T
            sc = out[:, 4:]
            cls, scores = sc.argmax(1), sc.max(1)
            m = scores > self.conf
            if not m.any():
                return []
            xywh, scores, cls = out[m, :4], scores[m], cls[m]
            xyxy = np.c_[xywh[:, :2] - xywh[:, 2:] / 2, xywh[:, :2] + xywh[:, 2:] / 2]
            keep = cv2.dnn.NMSBoxes(
                np.c_[xyxy[:, :2], xywh[:, 2:]].tolist(), scores.tolist(),
                self.conf, self.iou)
            keep = np.array(keep).flatten().astype(int)
            xyxy, scores, cls = xyxy[keep], scores[keep], cls[keep]

        xyxy = (xyxy - [px, py, px, py]) / r        # undo letterbox
        H, W = bgr.shape[:2]
        xyxy = np.clip(xyxy, 0, [W, H, W, H])
        return [(int(c), float(s), *map(float, b))
                for b, s, c in zip(xyxy, scores, cls)]
