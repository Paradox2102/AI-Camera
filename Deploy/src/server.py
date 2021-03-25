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
                else:
                    raise Client.InvalidCommandError()

        except ConnectionResetError: # Socket closed
            print(f'[INFO] Client at address {self.addr} disconnected.')

        except BrokenPipeError: # Super bad socket error, means client is somehow still active but the socket is refusing packets.
            print(f'[ERR] A fatal error occurred on client at address {self.addr}, reduce number of simultaneous connections.')

        except Client.InvalidCommandError: # Undefined command received
            print(f'[Err] Invalid command received in client at address {self.addr}, could be due to bad packets.')

        except socket.timeout: # Watchdog catch
            print(f'[WATCHDOG] Client at address {self.addr} timed out, disconnecting.')

        except Exception as e: # Any other error
            print(f'[ERR] An error occured while handling client at address {self.addr}:\n{type(e)}: {e}')

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
                threading.Thread(target=self.clients[address].main, daemon=True).start()
            else:
                print(f'[WARN] Denied client {address} from connecting.\
                    Increase "max_connections" at risk of instability.')
