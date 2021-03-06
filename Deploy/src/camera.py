"""
Camera related stuff.

Adapted from https://docs.luxonis.com/projects/api/en/latest/samples/08_rgb_mobilenet/
"""

import os
import re
from datetime import datetime
import threading
from pathlib import Path
import cv2
from PIL import Image
import depthai as dai
import numpy as np
import time
from simplejpeg import encode_jpeg
from networktables import NetworkTables as nt

"""
Camera object initializes the OAK-D camera,
then receives image data and NN inferences.
"""


class Camera:
    def __init__(self, server, modelName, modelSize, overlay=True):
        self.server = server
        self.modelSize = modelSize
        self.overlay = overlay
        self.imgCount = 0
        self.lock = threading.Lock()

        nt.initialize(server='roborio-2102-frc.local')
        self.sd = nt.getTable('SmartDashboard')

        mobilenet_path = str(
            (
                Path(__file__).parent
                / Path(f"../models/{modelName}/frozen_inference_graph.blob")
            )
            .resolve()
            .absolute()
        )

        # Start defining a pipeline
        self.pipeline = dai.Pipeline()

        # Define a source - color camera
        cam_rgb = self.pipeline.createColorCamera()
        cam_rgb.setPreviewSize(*modelSize)
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
        controlIn = self.pipeline.createXLinkIn()
        controlIn.setStreamName("control")
        detection_nn.passthrough.link(xout_rgb.input)

        xout_nn = self.pipeline.createXLinkOut()
        xout_nn.setStreamName("nn")
        detection_nn.out.link(xout_nn.input)

        controlIn.out.link(cam_rgb.inputControl)

        # MobilenetSSD label texts
        self.texts = ["", "ball"]

        self.objects = []

    def updateNetworkTable(self, data):
        values = [j for i in data for j in i]
        # print("ballcoords=", values)
        self.sd.putNumberArray('ballcoords', values)
        self.sd.putNumber('ballcount', len(values)//4)

    def setData(self, objects, frame):
        with self.lock:
            self.objects = objects
            self.frame = frame
            self.updateNetworkTable(objects)

        for client in self.server.clients.values():
            client.frameReady.release()

    def getObjects(self):
        with self.lock:
            return self.objects

    def getFrame(self):
        with self.lock:
            return self.frame

    @property
    def exposure(self):
        return None

    @exposure.setter
    def exposure(self, val):
        if val == None:
            self.ctrl.setAutoExposureEnable()
        else:
            self.ctrl = dai.CameraControl()
            self.ctrl.setManualExposure(*val)

        self.controlQueue.send(self.ctrl)

    @property
    def focus(self):
        return None

    @focus.setter
    def focus(self, val):
        if val == None:
            self.ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO)
        else:
            self.ctrl.setManualFocus(val)
        self.controlQueue.send(self.ctrl)

    def saveFrame(self):
        with self.lock:
            cv2.imwrite(f"../images/{datetime.now().isoformat()}.png", self.frameRGB)

    def main(self):
        # Pipeline defined, now the device is connected to
        with dai.Device(self.pipeline) as device:
            # Start pipeline
            device.startPipeline()
            self.controlQueue = device.getInputQueue("control")
            self.ctrl = dai.CameraControl()

            # Output queues will be used to get the rgb frames and nn data from the outputs defined above
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_nn = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

            start_time = time.monotonic()
            counter = 0
            detections = []
            frame = None

            # nn data (bounding box locations) are in <0..1> range - they need to be normalized with frame width/height
            def frame_norm(frame, bbox):
                norm_vals = np.full(len(bbox), frame.shape[0])
                norm_vals[::2] = frame.shape[1]
                return (np.clip(np.array(bbox), 0, 1) * norm_vals).astype(int)

            while True:
                if counter > 50:
                    start_time = time.monotonic()
                    counter = 0

                # use blocking get() call to catch frame and inference result synced
                in_rgb = q_rgb.get()
                in_nn = q_nn.get()

                if in_rgb is not None:
                    frame = in_rgb.getCvFrame()
                    if self.overlay:
                        cv2.putText(
                            frame,
                            "NN fps: {:.2f}".format(
                                counter / (time.monotonic() - start_time)
                            ),
                            (2, frame.shape[0] - 4),
                            cv2.FONT_HERSHEY_TRIPLEX,
                            0.4,
                            color=(255, 255, 255),
                        )

                if in_nn is not None:
                    detections = in_nn.detections
                    counter += 1

                # if the frame is available, draw bounding boxes on it and show the frame
                if frame is not None:
                    objectBuf = []
                    for detection in detections:
                        bbox = frame_norm(
                            frame,
                            (
                                detection.xmin,
                                detection.ymin,
                                detection.xmax,
                                detection.ymax,
                            ),
                        )
                        if self.overlay:
                            cv2.rectangle(
                                frame,
                                (bbox[0], bbox[1]),
                                (bbox[2], bbox[3]),
                                (255, 0, 0),
                                2,
                            )
                            cv2.putText(
                                frame,
                                self.texts[detection.label],
                                (bbox[0] + 10, bbox[1] + 20),
                                cv2.FONT_HERSHEY_TRIPLEX,
                                0.5,
                                255,
                            )
                            cv2.putText(
                                frame,
                                f"{int(detection.confidence*100)}%",
                                (bbox[0] + 10, bbox[1] + 40),
                                cv2.FONT_HERSHEY_TRIPLEX,
                                0.5,
                                255,
                            )

                        objectBuf.append(
                            [
                                int(i)
                                for i in [
                                    detection.xmin * self.modelSize[0],
                                    detection.ymin * self.modelSize[1],
                                    detection.xmax * self.modelSize[0],
                                    detection.ymax * self.modelSize[1],
                                ]
                            ]
                        )

                    self.frameRGB = frame
                    # cv2.imshow("rgb", self.frame)
                    framejpeg = memoryview(
                        encode_jpeg(frame, 50)
                    )  # Casting the encoded JPEG as a memoryview
                    # allows for cheap byte management
                    self.setData(
                        objectBuf, framejpeg
                    )  # Inform the server that the next frame is ready

                if cv2.waitKey(1) == ord("q"):
                    break
