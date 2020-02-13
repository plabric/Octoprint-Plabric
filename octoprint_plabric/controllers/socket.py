from enum import Enum

import socketio

from octoprint_plabric import config, DockerState


class ConfigState(Enum):
	NEEDED = 'needed'
	CANCELLED = 'cancelled'
	DONE = 'done'


class SocketState(Enum):
	DISCONNECTED = 'disconnected'
	CONNECTED = 'connected'

class Socket:

	def __init__(self, plugin):
		self._plugin = plugin
		self._logger = plugin.get_logger()
		self._namespace = config.NAMESPACE_DOCKER_IMAGE
		self._host = plugin.get_host_docker_image()

		self._sio = socketio.Client(reconnection=True, reconnection_delay=2)

		@self._sio.on('connect', namespace=self._namespace)
		def on_connect():
			self.log("Connected")
			self._plugin.refresh_socket_state(SocketState.CONNECTED)
			self.init()

		@self._sio.on('user_joined', namespace=self._namespace)
		def on_user_joined(nick):
			self.log("User joined")
			self._plugin.set_user_joined(True, nick)

		@self._sio.on('user_leave', namespace=self._namespace)
		def on_user_leave():
			self.log("User leave")
			self._plugin.set_user_joined(False, None)

		@self._sio.on('configuration_needed', namespace=self._namespace)
		def on_configuration_needed():
			self.log("Configuration needed")
			self._plugin.refresh_config_state(ConfigState.NEEDED)

		@self._sio.on('authorization_succeed', namespace=self._namespace)
		def on_authorization_succeed(token):
			self.log("Plabric token received")
			self._plugin.set_temp_token(token)

		@self._sio.on('authorization_error', namespace=self._namespace)
		def on_authorization_error(error):
			self.log("Plabric error on authorization")
			self._plugin.set_error(error)

		@self._sio.on('config_done', namespace=self._namespace)
		def on_configuration_done(api_key):
			self.log("Configuration done")
			self.log(api_key)
			self._plugin.save_setting('api_key', str(api_key))
			self._plugin.refresh_config_state(ConfigState.DONE)

		@self._sio.on('config_cancelled', namespace=self._namespace)
		def on_config_cancelled():
			self.log("Configuration cancelled")
			self._plugin.refresh_config_state(ConfigState.CANCELLED)

		@self._sio.on('video_stream_enabled', namespace=self._namespace)
		def on_video_stream_enabled(enabled):
			self.log("Video stream enabled" if enabled else "Video stream disabled")
			self._plugin.set_video_stream_enabled(enabled)

		@self._sio.on('disconnect', namespace=self._namespace)
		def on_disconnect():
			self._plugin.refresh_socket_state(SocketState.DISCONNECTED)
			self.log("Disconnected")

	def connect(self):
		try:
			self._sio.connect(self._host, namespaces=[self._namespace])
		except (socketio.exceptions.ConnectionError, ValueError) as e:
			self.log(e)
			self.log("Unable to connect with Plabric Docker")
			self._plugin.retry_connection()

	def disconnect(self):
		if self._sio is not None and self._sio.connected:
			self._sio.disconnect()

	def send_video_stream(self, data):
		if self._sio and self._sio.connected:
			self._sio.emit('video_stream', data, namespace=self._namespace)

	def disable_connection(self):
		if self._sio and self._sio.connected:
			self._sio.emit('disable', namespace=self._namespace)

	def init(self):
		self.log('Init docker connection')
		api_key = self._plugin.get_saved_setting('api_key')
		data = {'host': 'localhost'}
		if api_key:
			data['api_key'] = str(api_key)
		self.log(data)
		self._sio.emit('init', data, namespace=self._namespace)

	def is_connected(self):
		return self._sio and self._sio.connected

	def log(self, msg):
		if config.DEBUG and self._logger:
			self._logger.info(msg)
