"""
Simple client for testing the server.

Adin Ackerman
"""

import threading
import socket
import numpy as np
from simplejpeg import decode_jpeg
import cv2
from tkinter import *
from tkinter.ttk import *
from time import sleep

class Client:
    def __init__(self):
        # Configurable constants
        self.BUF_SIZE = 2048
        self.lock = threading.Lock()

        self.commandDict = {
            'coords': 0x10,
            'image': 0x20,
            'take-picture': 0x30,
            'overlay': 0x40,
            'm_exposure': 0x50,
            'a_exposure': 0x51,
            'm_focus': 0x60,
            'a_focus': 0x61,
            'success': 0xF0,
            'failure': 0x0F,
            'no-op': 0xFFFF
        }

    def connect(self, ip, port=1234):
        connectStatus.set('Connecting...')
        for item in [hLabel, ipEntry, portEntry]:
            item['state'] = 'disabled'
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((ip, port))
        except TimeoutError as e:
            connectStatus.set('Connect')
            statusTextLabel['foreground'] = 'red'
            statusTextVar.set(str(e))
            del self
            for item in [hLabel, ipEntry, portEntry]:
                item['state'] = 'enabled'
            return

        connectStatus.set('Disconnect')
        connectButton['command'] = disconnect

        threading.Thread(
            target=self._keepalive
        ).start()

    def connectStream(self, ip, port=1234):
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((ip, port))
        except TimeoutError as e:
            statusTextLabel['foreground'] = 'red'
            statusTextVar.set(str(e))
            del self
            return

        self.imageStream()

    def imageStream(self):
        viewImageStatus.set('Close image stream')
        try:
            while True:
                # Transmit
                self.s.send(int.to_bytes(commandDict['image'], 2, 'big'))

                # Receive
                command = int.from_bytes(self.s.recv(2), 'big')
                if command == client.commandDict['coords']: # Coordinates
                    numObjects = int.from_bytes(self.s.recv(2), 'big')
                    if numObjects > 0:
                        buf = self.s.recv(numObjects*8)
                        print([int.from_bytes(b0+b1, 'big') for b0, b1 in zip(buf[::2], buf[1::2])])
                    else:
                        print("No balls.")
                elif command == client.commandDict['image']: # Image stream
                    imgSize = int.from_bytes(self.s.recv(2), 'big')
                    buf = bytearray()
                    while len(buf) < imgSize: # Accumulate bytes until buffer is full
                        l = len(buf)
                        buf += self.s.recv(self.BUF_SIZE if l < imgSize-self.BUF_SIZE else imgSize-l)
                    try:
                        cv2.imshow('image', decode_jpeg(buf))
                    except ValueError:
                        statusTextLabel['foreground'] = 'red'
                        statusTextVar.set("Packet loss.")
                    if cv2.waitKey(1) == ord('q'):
                        return
        except Exception as e:
            statusTextLabel['foreground'] = 'red'
            statusTextVar.set(str(e))

    def transact(self, word, data=None):
        try:
            with self.lock:
                # Transmit
                self.s.send(int.to_bytes(commandDict[word], 2, 'big'))

                if data != None:
                    self.s.send(len(data))
                    self.s.send(data)

                # Receive
                result = int.from_bytes(self.s.recv(2), 'big')

            return result
        except Exception as e:
            statusTextLabel['foreground'] = 'red'
            statusTextVar.set(str(e))

    def _keepalive(self):
        try:
            while True:
                sleep(3)
                with self.lock:
                    self.s.send(int.to_bytes(self.commandDict['no-op'], 2, 'big'))
        except Exception as e:
            statusTextLabel['foreground'] = 'red'
            statusTextVar.set(str(e))


def connect():
    global client
    client = Client()
    threading.Thread(
        target=lambda: client.connect(
            ipEntry.get(), int(portEntry.get())
        )
    ).start()

def disconnect():
    client.s.close()
    del client

    for item in [hLabel, ipEntry, portEntry]:
        item['state'] = 'enabled'

    connectButton['command'] = connect

def updateStates():
    if autoExposureState.get():
        exposureEntry['state'] = 'disabled'
        isoEntry['state'] = 'disabled'
    else:
        exposureEntry['state'] = 'enabled'
        isoEntry['state'] = 'enabled'

    if autoFocusState.get():
        focusEntry['state'] = 'disabled'
    else:
        focusEntry['state'] = 'enabled'

def sendAutoExposure():
    result = client.transact(
        client.commandDict['a_exposure'],
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Auto exposure enabled successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to enable auto exposure.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def sendManualExposure():
    result = client.transact(
        client.commandDict['m_exposure'],
        int.to_bytes(int(exposureEntry.get()), 2, 'big')+\
        int.to_bytes(int(isoEntry.get()), 2, 'big')
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Manual exposure configured successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to configure manual exposure.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def sendAutoFocus():
    result = client.transact(
        client.commandDict['a_focus'],
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Auto focus enabled successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to enable auto focus.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def sendManualFocus():
    result = client.transact(
        client.commandDict['m_focus'],
        int.to_bytes(int(focusEntry.get()), 2, 'big')
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Manual focus distance configured successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to configure manual focus distance.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def sendOverlay():
    result = client.transact(
        client.commandDict['overlay'],
        int.to_bytes(overlayState.get(), 2, 'big')
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Overlay toggled successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to toggle overlay.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def takePicture():
    result = client.transact(
        client.commandDict['take-picture']
    )

    if result == client.commandDict['success']:
        statusTextLabel['foreground'] = 'green'
        statusTextVar.set("Picture taken successfully.")
    elif result == client.commandDict['failure']:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Failed to take picture.")
    else:
        statusTextLabel['foreground'] = 'red'
        statusTextVar.set("Socket communication out of sync.")

def startImageStream():
    imageClient = Client()

    threading.Thread(
        target=lambda: imageClient.connectStream(
            ipEntry.get(), int(portEntry.get())
        )
    ).start()

# set up gui
root = Tk()
root.title("Control Center")
root.resizable(False, False)

header1 = Frame(root)
header1.pack(side=TOP, padx=5, pady=5)

header2 = Frame(root)
header2.pack(side=TOP, padx=5, pady=5)

body = Frame(root)
body.pack(side=TOP, padx=5, pady=5)

footer = Frame(root)
footer.pack(side=TOP, padx=5, pady=5)

exposureFrame = Frame(body)
exposureFrame.grid(row=1, column=0, sticky='WE')

isoFrame = Frame(body)
isoFrame.grid(row=2, column=0, sticky='WE')

focusFrame = Frame(body)
focusFrame.grid(row=1, column=1, sticky='WE')

hLabel = Label(
    header1,
    text="IP, Port",
    justify=LEFT
)
hLabel.pack(side=LEFT, padx=5)

ipEntry = Entry(header1, width=15)
ipEntry.pack(side=LEFT, padx=5)
ipEntry.insert(END, '10.21.2.50')

portEntry = Entry(header1, width=8)
portEntry.pack(side=LEFT, padx=5)
portEntry.insert(END, '1234')

connectStatus = StringVar()
connectStatus.set('Connect')

connectButton = Button(
    header2,
    textvariable=connectStatus,
    command=connect
)
connectButton.pack(side=BOTTOM, pady=5)

exposureLabel = Label(
    exposureFrame,
    text='Exposure',
    justify=LEFT,
    state='disable'
)
exposureLabel.pack(side=LEFT, padx=5)

exposureEntry = Entry(
    exposureFrame,
    width=15,
    state='disable'
)
exposureEntry.pack(side=RIGHT, padx=5)
exposureEntry.insert(END, '10000')

isoLabel = Label(
    isoFrame,
    text='ISO',
    justify=LEFT,
    state='disable'
)
isoLabel.pack(side=LEFT, padx=5)

isoEntry = Entry(
    isoFrame,
    width=15,
    state='disable'
)
isoEntry.pack(side=RIGHT, padx=5)
isoEntry.insert(END, '300')

autoExposureState = IntVar()
autoExposure = Checkbutton(
    body,
    text='Auto Exposure',
    state='disable',
    variable=autoExposureState,
    command=updateStates
)
autoExposure.grid(row=0, column=0, sticky='W')

focusLabel = Label(
    focusFrame,
    text='Focus distance',
    justify=LEFT,
    state='disable'
)
focusLabel.pack(side=LEFT, padx=5)

focusEntry = Entry(focusFrame, width=15, state='disable')
focusEntry.pack(side=RIGHT, padx=5)
focusEntry.insert(END, '10000')

autoFocusState = IntVar()
autoFocus = Checkbutton(
    body,
    text='Auto Focus',
    state='disable',
    variable=autoFocusState,
    command=updateStates
)
autoFocus.grid(row=0, column=1, sticky='W')

overlayState = IntVar()
overlay = Checkbutton(
    body,
    text='Overlay',
    state='disable',
    variable=overlayState,
    command=updateStates
)
overlay.grid(row=0, column=2, sticky='W')

takePicture = Button(
    body,
    text='Take Picture',
    state='disable',
    command=lambda: None
)
takePicture.grid(row=1, column=2, stick='W')

viewImageStatus = StringVar()
viewImageStatus.set('View Image Stream')

viewImage = Button(
    body,
    textvariable=viewImageStatus,
    state='disable',
    command=lambda: threading.Thread(
        target=client.imageStream
    ).start()
)
viewImage.grid(row=2, column=2, sticky='W')

statusTextVar = StringVar()

statusTextLabel = Label(
    footer,
    textvariable=statusTextVar,
    justify=LEFT,
    wraplength=450
)
statusTextLabel.pack(side=TOP, padx=5, pady=5)

mainloop()
