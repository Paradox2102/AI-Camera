"""
Server module that allows the raspberrypi to handle clients
and transmit image/object detection data.

Adin Ackerman
"""

import threading
import socket
from PIL import Image

"""
Client object represents socket stream with specific client.
Handles send/recv with corresponding client socket.
"""
class Client:
    def __init__(self, server, sock, addr):
        self.server, self.sock, self.addr = server, sock, addr
        self.sock.settimeout(10)

    def main(self):
        while True:
            try:
                # Receive command
                command = int.from_bytes(self.sock.recv(2), 'big')

                # No operation (watchdog)
                if command == self.server.commandDict['no-op']:
                    continue

                # Send coords
                elif command == self.server.commandDict['coords']:
                    self.waiting = True
                    while self.waiting:
                        pass

                    objects = self.server.camera.objects
                    numObjects = len(objects)
                    assert 0 <= numObjects < 2**16, f"Number of objects detected must be less than {2**16}."
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
                    self.waiting = True
                    while self.waiting:
                        pass

                    self.sock.send(
                        int.to_bytes(self.server.commandDict['image'], 2, 'big')+
                        int.to_bytes(self.server.camera.framejpeg.nbytes, 2, 'big')
                    )
                    self.sock.send(self.server.camera.framejpeg)

            except ConnectionResetError:
                print(f'[INFO] Client at address {self.addr} disconnected.')
                del self.server.clients[self.addr]
                return

            except socket.timeout:
                print(f'[WATCHDOG] Client at address {self.addr} timed out, disconnecting.')
                del self.server.clients[self.addr]
                self.sock.close()
                return

            except Exception as e:
                print(f'[ERR] An error occured while handling client at address {self.addr}:\n{type(e)}: {e}')

"""
Server object accepts client connections as Client threads
and keeps track of active connections
"""
class Server:
    def __init__(self, port):
        print("Server starting...")
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(('', port))
        self.s.listen()
        print(f'Listening on port {port}.')

        self.commandDict = {
            'coords': 0x10,
            'image': 0x20,
            'no-op': 0xFFFF
        }

        self.clients = {}

    def main(self, camera):
        self.camera = camera

        while True:
            clientsocket, address = self.s.accept()
            print(f'[INFO] Connection from {address} has been established.')
            self.clients[address] = Client(self, clientsocket, address)
            threading.Thread(target=self.clients[address].main, daemon=True).start()

    def frameReady(self):
        for a, c in self.clients.items():
            c.waiting = False
