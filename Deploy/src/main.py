"""
Main script, allows for some configuration
and sets the modules into motion.

Adin Ackerman
"""

import threading
from camera import Camera
import server
from server import Server

# Configurable constants
MODEL_NAME = '400x225'
MODEL_SIZE = 400, 225
PORT = 1234

s = Server(PORT)
c = Camera(s, MODEL_NAME, MODEL_SIZE)
threading.Thread(target=lambda: s.main(c), daemon=True).start()
c.main()
