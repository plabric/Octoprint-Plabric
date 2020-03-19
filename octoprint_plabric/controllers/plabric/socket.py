import socketio

from octoprint_plabric import config
from octoprint_plabric.controllers.common import logger as _logger
import json as _json


class PlabricSocketProtocol:
	def on_connected(self):
		raise NotImplementedError

	def on_disconnected(self):
		raise NotImplementedError

	def on_user_leave(self):
		raise NotImplementedError

	def on_user_joined(self, user_nick, octoprint_api_key):
		raise NotImplementedError

	def on_config_done(self):
		raise NotImplementedError

	def on_connection_registered(self, plabric_api_key):
		raise NotImplementedError

	def on_api_command(self, data):
		raise NotImplementedError

	def on_video_command(self, data):
		raise NotImplementedError

	def on_signaling(self, data):
		raise NotImplementedError

	def on_connection_error(self):
		raise NotImplementedError


class PlabricSocket:

	def __init__(self, domain, callback):
		_logger.log('Plabric Socket: Initializing')
		self._domain = domain
		self._sio = socketio.Client(reconnection=True, reconnection_delay=5)
		self._add_event_handlers()
		self._callback = callback

	def connect(self):
		try:
			_logger.log('Plabric Socket: Connecting')
			self._sio.connect(self._domain, namespaces=[config.PLABRIC_SOCKET_NAMESPACE])
		except (socketio.exceptions.ConnectionError, ValueError) as e:
			_logger.warn(e)
			self._callback.on_connection_error()

	def disconnect(self):
		_logger.log('Plabric Socket: Disconnecting')
		if self._sio and self._sio.connected:
			self._sio.disconnect()

	def send_msg(self, key, data=None):
		if self._sio.connected:
			self._sio.emit(key, data, namespace=config.PLABRIC_SOCKET_NAMESPACE) if data else self._sio.emit(key, namespace=config.PLABRIC_SOCKET_NAMESPACE)

	def _add_event_handlers(self):
		@self._sio.on('connect', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def connect():
			_logger.log('Plabric Socket: Connected')
			if self._callback:
				self._callback.on_connected()

		@self._sio.on('disconnect', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def disconnect():
			_logger.log('Plabric Socket: Disconnected')
			if self._callback:
				self._callback.on_disconnected()

		@self._sio.on('user_joined', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def user_joined(data):
			_logger.log('Plabric Socket: User joined')
			if self._callback:
				user_nick = data['user_nick']
				octoprint_api_key = data['octoprint_api_key']
				self._callback.on_user_joined(user_nick, octoprint_api_key)

		@self._sio.on('user_leave', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def user_leave(data):
			_logger.log('Plabric Socket: User leave')
			if self._callback:
				self._callback.on_user_leave()

		@self._sio.on('config_done', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def config_done():
			_logger.log('Plabric Socket: Config done')
			if self._callback:
				self._callback.on_config_done()

		@self._sio.on('connection_registered', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def connection_registered(data):
			_logger.log('Plabric Socket: Connection registered')
			if self._callback:
				api_key = data['api_key']
				self._callback.on_connection_registered(api_key)

		@self._sio.on('api_command', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def api_command(data):
			_logger.log('Plabric Socket: Api command received')
			if self._callback:
				_logger.log(data)
				self._callback.on_api_command(_json.loads(data))

		@self._sio.on('video_command', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def video_command(data):
			_logger.log('Plabric Socket: Video command received')
			if self._callback:
				self._callback.on_video_command(_json.loads(data))

		@self._sio.on('signaling', namespace=config.PLABRIC_SOCKET_NAMESPACE)
		def signaling(data):
			_logger.log('Plabric Socket: Signaling received')
			if self._callback:
				self._callback.on_signaling(data)