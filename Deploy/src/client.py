"""
Simple client for testing the server.

Adin Ackerman
"""

import socket
import numpy as np
from simplejpeg import decode_jpeg
import cv2

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 1234))

# Configurable constants
BUF_SIZE = 2048
COMMAND = 'image'

commandDict = {
    'coords': 0x10,
    'image': 0x20,
    'no-op': 0xFFFF
}

while True:
    # Transmit
    s.send(bytearray([0x00, commandDict[COMMAND]]))

    # Receive
    command = int.from_bytes(s.recv(2), 'big')
    if command == 0x10: # Coordinates
        numObjects = int.from_bytes(s.recv(2), 'big')
        if numObjects > 0:
            buf = s.recv(numObjects*8)
            print([int.from_bytes(b0+b1, 'big') for b0, b1 in zip(buf[::2], buf[1::2])])
        else:
            print("No balls.")
    elif command == 0x20: # Image stream
        imgSize = int.from_bytes(s.recv(2), 'big')
        buf = bytearray()
        while len(buf) < imgSize: # Accumulate bytes until buffer is full
            l = len(buf)
            buf += s.recv(BUF_SIZE if l < imgSize-BUF_SIZE else imgSize-l)
        try:
            cv2.imshow('image', decode_jpeg(buf))
        except ValueError:
            print('[ERR] Packet loss.')
        cv2.waitKey(1)
