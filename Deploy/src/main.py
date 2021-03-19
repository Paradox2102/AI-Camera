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
MODEL = '400x225'
PORT = 1234

s = Server(PORT)
c = Camera(s, MODEL)
threading.Thread(target=lambda: s.main(c), daemon=True).start()
c.main()
