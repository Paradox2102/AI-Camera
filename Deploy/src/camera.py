"""
Camera related stuff.

Adapted from https://docs.luxonis.com/projects/api/en/latest/samples/08_rgb_mobilenet/
"""

import threading
from pathlib import Path
import cv2
import depthai as dai
import numpy as np
import time
from simplejpeg import encode_jpeg

"""
Camera object initializes the OAK-D camera,
then receives image data and NN inferences.
"""
class Camera:
    def __init__(self, server, modelName):
        self.server = server

        mobilenet_path = str((Path(__file__).parent / Path(f'../models/{modelName}/frozen_inference_graph.blob')).resolve().absolute())

        # Start defining a pipeline
        self.pipeline = dai.Pipeline()

        # Define a source - color camera
        cam_rgb = self.pipeline.createColorCamera()
        cam_rgb.setPreviewSize(400, 225)
        cam_rgb.setInterleaved(False)
        cam_rgb.setFps(90)

        # Define a neural network that will make predictions based on the source frames
        detection_nn = self.pipeline.createMobileNetDetectionNetwork()
        detection_nn.setConfidenceThreshold(0.5)
        detection_nn.setBlobPath(mobilenet_path)
        detection_nn.setNumInferenceThreads(2)
        detection_nn.input.setBlocking(False)
        cam_rgb.preview.link(detection_nn.input)

        # Create outputs
        xout_rgb = self.pipeline.createXLinkOut()
        xout_rgb.setStreamName("rgb")
        detection_nn.passthrough.link(xout_rgb.input)

        xout_nn = self.pipeline.createXLinkOut()
        xout_nn.setStreamName("nn")
        detection_nn.out.link(xout_nn.input)

        # MobilenetSSD label texts
        self.texts = ['', "ball"]

        self.objects = []

    def main(self):
        lock = threading.Lock()
        # Pipeline defined, now the device is connected to
        with dai.Device(self.pipeline) as device:
            # Start pipeline
            device.startPipeline()

            # Output queues will be used to get the rgb frames and nn data from the outputs defined above
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_nn = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

            start_time = time.monotonic()
            counter = 0
            detections = []
            self.frame = None

            # nn data (bounding box locations) are in <0..1> range - they need to be normalized with frame width/height
            def frame_norm(frame, bbox):
                norm_vals = np.full(len(bbox), self.frame.shape[0])
                norm_vals[::2] = self.frame.shape[1]
                return (np.clip(np.array(bbox), 0, 1) * norm_vals).astype(int)


            while True:
                # use blocking get() call to catch frame and inference result synced
                in_rgb = q_rgb.get()
                in_nn = q_nn.get()


                if in_rgb is not None:
                    self.frame = in_rgb.getCvFrame()
                    cv2.putText(self.frame, "NN fps: {:.2f}".format(counter / (time.monotonic() - start_time)),
                                (2, self.frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color=(255, 255, 255))

                if in_nn is not None:
                    detections = in_nn.detections
                    counter += 1

                # if the frame is available, draw bounding boxes on it and show the frame
                if self.frame is not None:
                    with lock:
                        self.objects = []
                        for detection in detections:
                            bbox = frame_norm(self.frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                            cv2.rectangle(self.frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)
                            cv2.putText(self.frame, self.texts[detection.label], (bbox[0] + 10, bbox[1] + 20),
                                        cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
                            cv2.putText(self.frame, f"{int(detection.confidence*100)}%", (bbox[0] + 10, bbox[1] + 40),
                                        cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)

                            self.objects.append([int(i*300) for i in [detection.xmin, detection.ymin, detection.xmax, detection.ymax]])

                        # cv2.imshow("rgb", self.frame)
                        self.framejpeg = memoryview(encode_jpeg(self.frame, 50)) # Casting the encoded JPEG as a memoryview
                                                                                 # allows for cheap byte management
                    self.server.frameReady() # Inform the server that the next frame is ready

                if cv2.waitKey(1) == ord('q'):
                    break
