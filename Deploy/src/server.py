"""
Server module that allows the raspberrypi to handle clients
and transmit image/object detection data.

Adin Ackerman
"""

import sys
import threading
import socket
import time

"""
Client object represents socket stream with specific client.
Handles send/recv with corresponding client socket.
"""
class Client:
    class InvalidCommandError(Exception):
        pass

    def __init__(self, server, sock, addr):
        self.server, self.sock, self.addr = server, sock, addr
        self.sock.settimeout(10)

        self.frameReady = threading.Semaphore(0)

    def main(self):
        try:
            while True:
                # Receive command
                command = int.from_bytes(self.sock.recv(2), 'big')

                # No operation (watchdog)
                if command == self.server.commandDict['no-op']:
                    continue

                # Send coords
                elif command == self.server.commandDict['coords']:
                    self.frameReady.acquire(False)
                    self.frameReady.acquire()

                    objects = self.server.camera.getObjects()
                    numObjects = len(objects)
                    self.sock.send(
                        int.to_bytes(self.server.commandDict['coords'], 2, 'big')+
                        int.to_bytes(numObjects, 2, 'big')
                    )
                    msg = bytearray()
                    for o in objects:
                        for i in o:
                            msg += int.to_bytes(i, 2, 'big')
                        self.sock.send(msg)

                # Image stream
                elif command == self.server.commandDict['image']:
                    self.frameReady.acquire(False)
                    self.frameReady.acquire()

                    frame = self.server.camera.getFrame()

                    self.sock.send(
                        int.to_bytes(self.server.commandDict['image'], 2, 'big')+
                        int.to_bytes(frame.nbytes, 2, 'big')
                    )
                    self.sock.send(frame)

                elif command == self.server.commandDict['take-picture']:
                    try:
                        self.server.camera.saveFrame()
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                elif command == self.server.commandDict['overlay']:
                    try:
                        l = self.sock.recv(2)
                        self.server.camera.overlay = int.from_bytes(self.sock.recv(2), 'big')
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                elif command == self.server.commandDict['m_exposure']:
                    l = self.sock.recv(2)
                    buf = self.sock.recv(4)
                    try:
                        self.server.camera.exposure = int.from_bytes(buf[:2], 'big'), int.from_bytes(buf[2:], 'big')
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                elif command == self.server.commandDict['a_exposure']:
                    try:
                        self.server.camera.exposure = None
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                elif command == self.server.commandDict['m_focus']:
                    l = self.sock.recv(2)
                    try:
                        self.server.camera.focus = int.from_bytes(self.sock.recv(2), 'big')
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                elif command == self.server.commandDict['a_focus']:
                    try:
                        self.server.camera.focus = None
                    except Exception as e:
                        print(f'[ERR] {str(type(e))}: {str(e)}')
                        self.sock.send(int.to_bytes(self.server.commandDict['failure'], 2, 'big'))
                        continue

                    self.sock.send(int.to_bytes(self.server.commandDict['success'], 2, 'big'))

                else:
                    raise Client.InvalidCommandError()

        except ConnectionResetError: # Socket closed
            print(f'[INFO] Client at address {self.addr} disconnected.')

        except BrokenPipeError: # Super bad socket error, means client is somehow still active but the socket is refusing packets.
            print(f'[ERR] A fatal error occurred on client at address {self.addr}, reduce number of simultaneous connections.')

        except Client.InvalidCommandError: # Undefined command received
            print(f'[Err] Invalid command received in client at address {self.addr}, could be due to bad packets. {command}')

        except socket.timeout: # Watchdog catch
            print(f'[WATCHDOG] Client at address {self.addr} timed out, disconnecting.')

        finally:
            sys.stdout.flush()
            # Terminate client thread
            self.sock.close()
            del self.server.clients[self.addr]
            return

"""
Server object accepts client connections as Client threads
and keeps track of active connections
"""
class Server:
    def __init__(self, port, max_connections=3):
        print("Server starting...")
        self.max_connections = max_connections

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(('', port))
        self.s.listen()
        print(f'Listening on port {port}.')

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

        self.clients = {}

    def main(self, camera):
        self.camera = camera

        while True:
            clientsocket, address = self.s.accept()
            if len(self.clients) < self.max_connections:
                print(f'[INFO] Connection from {address} has been established.')
                self.clients[address] = Client(self, clientsocket, address)
                threading.Thread(target=self.clients[address].main, name=str(address[1]), daemon=True).start()
            else:
                print(f'[WARN] Denied client {address} from connecting.\
                    Increase "max_connections" at risk of instability.')
