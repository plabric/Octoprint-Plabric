import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = False
HOST_PLABRIC_API = 'https://apiv2.plabric.com/'
PLABRIC_SOCKET_NAMESPACE = "/octoprint/plugin/socket"

FFMPEG_DIR = os.path.join(BASE_DIR, 'bin', 'ffmpeg')
JANUS_DIR = os.path.join(BASE_DIR, 'bin', 'janus')
JANUS_RUN_LOCAL = True
JANUS_HOST = 'localhost'
JANUS_VIDEO_HOST = 'localhost'
