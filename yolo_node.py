import os, cv2, rclpy
from rclpy.node import Node
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from gst_receiver import GstReceiver
from detector import YoloOnnx

NAMES = ["metal", "organic", "plastic"]   # order from data.yaml


class YoloNode(Node):
    def __init__(self):
        super().__init__("yolo_detector")
        self.declare_parameter("port", 5600)
        self.declare_parameter("host", "")
        self.declare_parameter("model", "model.onnx")
        self.declare_parameter("conf", 0.4)
        self.declare_parameter("show", False)
        p = lambda n: self.get_parameter(n).value
        self.show = p("show")
        self.rx = GstReceiver(p("port"), p("host") or None)
        self.det = YoloOnnx(p("model"), conf=p("conf"))
        self.pub = self.create_publisher(Detection2DArray, "/detections", 10)
        self.create_timer(0.001, self.tick)

    def tick(self):
        frame = self.rx.get_frame(timeout_ms=5)
        if frame is None:
            return
        res = self.det(frame)
        msg = Detection2DArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera"
        for cls, conf, x1, y1, x2, y2 in res:
            d = Detection2D()
            d.header = msg.header
            d.bbox.center.position.x = (x1 + x2) / 2
            d.bbox.center.position.y = (y1 + y2) / 2
            d.bbox.size_x, d.bbox.size_y = x2 - x1, y2 - y1
            h = ObjectHypothesisWithPose()
            h.hypothesis.class_id = NAMES[cls]
            h.hypothesis.score = conf
            d.results.append(h)
            msg.detections.append(d)
            if self.show:
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        self.pub.publish(msg)          # publish even when empty
        if self.show:
            cv2.imshow("yolo", frame); cv2.waitKey(1)


def main():
    rclpy.init()
    node = YoloNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.rx.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
