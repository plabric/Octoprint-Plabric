import threading
import time
from enum import Enum

from octoprint_plabric import config
from octoprint_plabric.controllers.common import logger as _logger, utils as _utils
from octoprint_plabric.controllers.common.api import APIProtocol
from octoprint_plabric.controllers.common.storage import Storage
from octoprint_plabric.controllers.octoprint.api import OctoprintAPI, OctoprintAPIProtocol
from octoprint_plabric.controllers.octoprint.socket import OctoprintSocket, OctoprintSocketProtocol
from octoprint_plabric.controllers.plabric.api import PlabricAPI
from octoprint_plabric.controllers.plabric.janus import Janus, JanusProtocol
from octoprint_plabric.controllers.plabric.socket import PlabricSocket, PlabricSocketProtocol
from octoprint_plabric.controllers.video.video import VideoStreamer, VideoStreamProtocol


class Step(Enum):
	ERROR_CONNECTION = 'error_connection'
	LOGIN_NEEDED = 'login_needed'
	OCTOPRINT_OAUTH = 'octoprint_oauth'
	QR_READ = 'qr_read'
	READY = 'ready'
	CONNECTED = 'connected'
	STOPPING = 'stopping'


class Main:

	def __init__(self, plugin):
		self.plugin = plugin
		self.error = ''
		self.loading = False
		self.user_nick = None
		self.step = None
		self.set_step(Step.LOGIN_NEEDED)

		self.plabric_api = None
		self.plabric_socket = None
		self.plabric_webrtc = None
		self.octoprint_api = None
		self.octoprint_socket = None
		self.video_streamer = None

		self.plabric_api_key = Storage(self.plugin).get_saved_setting('plabric_api_key')
		self.plabric_token = None
		self.octoprint_api_key = None

		self.init()

	def init(self):
		self._init_plabric_api()
		self._init_plabric_socket()
		self._init_plabric_webrtc()
		self._init_octoprint_api()
		self._init_octoprint_socket()
		self._init_video_stream()

	def start(self, from_oauth=False):
		_logger.log('Starting')
		self.set_error('')
		if from_oauth and not self.plabric_api_key:
			f = self.probe_plugin_appkeys
		else:
			f = self.connect

		thread = threading.Thread(target=f)
		thread.daemon = True
		thread.start()

	def connect(self):
		self.plabric_socket.connect()

	def set_step(self, step):
		self.step = step
		self.plugin.update_ui_status()

	def set_error(self, error):
		self.error = error
		self.set_loading(False)
		self.plugin.update_ui_status()

	def set_loading(self, loading):
		self.loading = loading
		self.plugin.update_ui_status()

	def _init_plabric_api(self):
		self.plabric_api = PlabricAPI(domain=config.HOST_PLABRIC_API)

	def download_temporal_file(self, data):
		class Response(APIProtocol):
			def __init__(self, p, file_path):
				self._p = p
				self._file_path = file_path

			def on_succeed(self, response):
				self._p.upload_file(data=data, file_path=self._file_path)

			def on_error(self, error):
				self._p.set_error(error)

		destination = Storage(self.plugin).get_file_temporal_path("tmp.gcode")
		self.plabric_api.download_temporal_file(file_id=data['params']['file_id'], destination=destination, plabric_api_key=self.plabric_api_key, callback=Response(self, file_path=destination))

	def upload_file(self, data, file_path):
		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, response):
				Storage(self._p.plugin).delete_file_temporal(path=file_path)
				self._p.call_octoprint_api_succeed(data=data, response=response)

			def on_error(self, error):
				self._p.call_octoprint_api_error(data=data, error=error)

		self.octoprint_api.upload_file(data=data, file_path=file_path, callback=Response(self))

	def _init_plabric_socket(self):

		class Response(PlabricSocketProtocol):

			def __init__(self, p):
				self._p = p

			def on_connected(self):
				self._p.plabric_socket.send_msg(key='jr_slave', data={'api_key': self._p.plabric_api_key} if self._p.plabric_api_key else {'token': self._p.plabric_token})
				if self._p.plabric_api_key:
					self._p.set_step(Step.READY)
					self._p.send_metadata()
				else:
					if self._p.step == Step.OCTOPRINT_OAUTH:
						self._p.set_step(Step.QR_READ)

			def on_connection_error(self):
				if self._p.plabric_api_key:
					self._p.set_step(Step.ERROR_CONNECTION)
				else:
					self._p.set_error('Unable to connect with Plabric server')
					self._p.set_step(Step.LOGIN_NEEDED)

			def on_disconnected(self):
				self._p.set_step(Step.ERROR_CONNECTION) if self._p.plabric_api_key else self._p.set_step(Step.LOGIN_NEEDED)
				self._p.octoprint_socket.disconnect()
				self._p.plabric_webrtc.disconnect()

			def on_user_leave(self):
				self._p.set_step(Step.READY)
				self._p.octoprint_socket.disconnect()
				self._p.plabric_webrtc.disconnect()

			def on_user_joined(self, user_nick, octoprint_api_key):
				self._p.plabric_socket.send_msg('ready')
				self._p.octoprint_api_key = octoprint_api_key
				self._p.user_nick = user_nick

				self._p.login_octoprint_api(octoprint_api_key)
				if self._p.plabric_api_key and self._p.step != Step.QR_READ:
					self._p.load_webrtc_servers()

				self._p.set_step(Step.CONNECTED)
				self._p.send_metadata()

			def on_config_done(self):
				self._p.set_step(Step.READY)

			def on_connection_registered(self, plabric_api_key):
				self._p.plabric_socket.send_msg(key='lr')
				self._p.plabric_socket.send_msg(key='close')
				self._p.plabric_socket.send_msg(key='jr_slave', data={'api_key': plabric_api_key})
				self._p.plabric_api_key = plabric_api_key
				storage = Storage(self._p.plugin)
				storage.save_setting('plabric_api_key', plabric_api_key)

			def on_api_command(self, data):
				self._p.call_octoprint_api(data)

			def on_video_command(self, data):
				if data['enable']:
					self._p.plabric_webrtc.start_video_stream()
				else:
					self._p.plabric_webrtc.stop_video_stream()

			def on_signaling(self, data):
				self._p.plabric_webrtc.on_signaling(data)

		self.plabric_socket = PlabricSocket(domain=config.HOST_PLABRIC_API, callback=Response(self))

	def send_metadata(self):
		plugin_version = self.plugin.get_version()
		machine = _utils.machine()
		system = _utils.system()
		camera_type = _utils.camera_type()
		pi_version = _utils.pi_version()
		self.plabric_api.send_metadata(plabric_api_key=self.plabric_api_key, plugin_version=plugin_version,
									   machine=machine,
									   system=system, camera_type=camera_type, pi_version=pi_version, callback=None)

	def load_webrtc_servers(self):
		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, data):
				self._p.plabric_webrtc.run(json_servers=data)

			def on_error(self, error):
				self._p.set_error(error)

		self.plabric_api.get_webrtc_servers(self.plabric_api_key, callback=Response(self))

	def _init_plabric_webrtc(self):

		class Response(JanusProtocol):
			def __init__(self, p):
				self._p = p

			def send_msg(self, key, data=None):
				self._p.plabric_socket.send_msg(key=key, data=data)

			def connected(self):
				pass

			def disconnected(self):
				pass

			def wrtc_disconnected(self):
				self._p.video_streamer.stop()

			def wrtc_connected(self):
				pass

			def video_stream_started(self):
				self._p.video_streamer.start(url=self._p.plugin.get_video_stream_url(),
												flip_horizontally='flipH' in self._p.plugin.get_webcam_params(),
												flip_vertically='flipV' in self._p.plugin.get_webcam_params(),
												rotate_90_clockwise='rotate90' in self._p.plugin.get_webcam_params())

			def video_stream_paused(self):
				self._p.video_streamer.stop()

			def janus_running(self):
				self._p.plabric_socket.send_msg(key='webrtc_ready')

		self.plabric_webrtc = Janus(system=_utils.system(), machine=_utils.machine(), callback=Response(self))

	def _init_video_stream(self):
		class VideoResponse(VideoStreamProtocol):
			def __init__(self, p):
				self._p = p

			def on_video_started(self):
				pass

			def on_video_stopped(self):
				self._p.plabric_webrtc.stop_video_stream()

		self.video_streamer = VideoStreamer(janus_url=config.JANUS_VIDEO_HOST, port=config.JANUS_VIDEO_PORT, system=_utils.system(), machine=_utils.machine(), is_raspberry=_utils.is_raspberry())
		self.video_streamer.set_callback(VideoResponse(self))

	def _init_octoprint_api(self):
		host = self.plugin.get_host()
		self.octoprint_api = OctoprintAPI(domain=host)

	def login_octoprint_api(self, octoprint_api_key):
		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, data):
				self._p.octoprint_socket.connect(username=data['name'], session=data['session'])

			def on_error(self, error):
				self._p.set_step(Step.LOGIN_NEEDED)

		self.octoprint_api.login(octoprint_api_key=octoprint_api_key, callback=Response(self))

	def call_octoprint_api_succeed(self, data, response):
		if response:
			data['response'] = response
		data['status_code'] = 200
		self.plabric_socket.send_msg(key='api_command_response', data=data)

	def call_octoprint_api_error(self, data, error):
		data['status_code'] = error
		self.plabric_socket.send_msg(key='api_command_response', data=data)

	def call_octoprint_api(self, data):

		class APIResponse(OctoprintAPIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, response):
				self._p.call_octoprint_api_succeed(data=data, response=response)

			def on_error(self, error):
				self._p.call_octoprint_api_error(data=data, error=error)

			def on_download_first(self, data):
				thread = threading.Thread(target=self._p.download_temporal_file, args=(data,))
				thread.daemon = True
				thread.start()

		self.octoprint_api.call_method(data=data, callback=APIResponse(self))

	def _init_octoprint_socket(self):

		class Response(OctoprintSocketProtocol):
			def __init__(self, p):
				self._p = p

			def on_event(self, event):
				self._p.plabric_socket.send_msg(key='socket_event', data=event)

			def connected(self):
				pass

			def disconnected(self):
				pass

		host = self.plugin.get_host()
		self.octoprint_socket = OctoprintSocket(domain=host, callback=Response(self))

	def probe_plugin_appkeys(self):
		_logger.log('Octoprint API: Probe plugin appkeys')
		self.set_loading(True)

		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, data):
				self._p.request_app_token()

			def on_error(self, error):
				self._p.set_error('You have to install Application Keys Plugin for grant access to Plabric or update your Octoprint version to version >= 1.3.10')
				self._p.disconnect()

		self.set_step(Step.OCTOPRINT_OAUTH)
		self.octoprint_api.probe_plugin_appkeys(callback=Response(self))

	def request_app_token(self):
		_logger.log('Octoprint API: Request app token')
		self.set_loading(True)

		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, data):
				self._p.polling_for_api_key(token=data['app_token'])

			def on_error(self, error):
				self._p.set_error(error)
				self._p.disconnect()

		self.set_step(Step.OCTOPRINT_OAUTH)
		self.octoprint_api.request_app_token(callback=Response(self))

	def polling_for_api_key(self, token, count=0):
		class Response(APIProtocol):
			def __init__(self, p, token, count):
				self._p = p
				self._token = token
				self._count = count

			def on_succeed(self, data):
				if 'api_key' in data:
					self._p.octoprint_api_key = data['api_key']
					self._p.octoprint_api.login(octoprint_api_key=self._p.octoprint_api_key, callback=None)
					self._p.request_plabric_token()
				else:
					if count < 4:
						time.sleep(3)
						self._p.polling_for_api_key(token=token, count=count + 1)
					else:
						self._p.set_error('Unable to grant access to Octoprint')
						self._p.disconnect()

			def on_error(self, error):
				self._p.set_error('Unable to grant access to Octoprint')
				self._p.disconnect()

		self.octoprint_api.request_api_key(app_token=token, callback=Response(self, token=token, count=count))

	def request_plabric_token(self):

		class Response(APIProtocol):
			def __init__(self, p):
				self._p = p

			def on_succeed(self, data):
				self._p.plabric_token = data['token']
				self._p.set_step(Step.QR_READ)
				self._p.set_loading(False)
				self._p.plabric_socket.connect()

			def on_error(self, error):
				self._p.set_error('Unable to connect with Plabric Server')
				self._p.disconnect()

		self.plabric_api.get_temporal_token(octoprint_api_key=self.octoprint_api_key, callback=Response(self))

	def get_status(self):
		if self.step == Step.LOGIN_NEEDED:
			return 'Login need'
		elif self.step in [Step.QR_READ, Step.OCTOPRINT_OAUTH]:
			return 'Login'
		elif self.step == Step.READY:
			return 'Ready'
		elif self.step == Step.CONNECTED:
			return 'User connected' if self.user_nick is None else '%s connected' % self.user_nick
		elif self.step == Step.STOPPING:
			return 'Stopping'
		elif self.step == Step.ERROR_CONNECTION:
			return 'Unable to connect'

	def send_printer_event(self, event):
		if self.plabric_api_key:
			class Response(APIProtocol):
				def on_succeed(self, response):
					_logger.log('Plabric API: Event sent')

				def on_error(self, error):
					_logger.log('Plabric API: Error sending event')

			self.plabric_api.send_event(plabric_api_key=self.plabric_api_key, event=event, callback=Response())

	def disable(self):
		self.disconnect()
		self.plabric_api_key = None
		_logger.log('Disabling Plabric Plugin')
		Storage(self.plugin).clear_setting('plabric_api_key')

	def disconnect(self):
		self.set_loading(True)
		_logger.log('Disconnecting Plabric Plugin')
		self.video_streamer.stop()
		self.octoprint_socket.disconnect()
		self.plabric_socket.disconnect()
		self.plabric_webrtc.disconnect()
		self.set_step(Step.LOGIN_NEEDED)
		self.set_loading(False)

	def reconnect(self):
		_logger.log('Reconnecting')
		self.connect()
