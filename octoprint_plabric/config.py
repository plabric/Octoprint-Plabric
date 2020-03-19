import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = False
HOST_PLABRIC_API = 'https://api.plabric.com'
PLABRIC_SOCKET_NAMESPACE = "/octoprint/plugin/socket"

JANUS_DIR = os.path.join(BASE_DIR, 'bin', 'janus')
JANUS_RUN_LOCAL = True
JANUS_HOST = 'localhost'
JANUS_API_PORT = 9010
JANUS_WS_PORT = 9011
JANUS_VIDEO_HOST = 'localhost'
JANUS_VIDEO_PORT = 9012
