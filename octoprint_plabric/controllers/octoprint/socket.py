import json as _json
import threading

import websocket
from octoprint_plabric.controllers.common import logger as _logger


class OctoprintSocketProtocol:
	def on_event(self, event):
		raise NotImplementedError

	def connected(self):
		raise NotImplementedError

	def disconnected(self):
		raise NotImplementedError


class OctoprintSocket:

	def __init__(self, domain, callback):
		_logger.log('Octoprint Socket: Initializing')
		self._domain = domain
		self._ws = None
		self._callback = callback
		self._thread = None

	def connect(self, username, session):
		self._connect(username, session)

	def connected(self):
		return self._ws and self._ws.sock and self._ws.sock.connected

	def disconnect(self):
		_logger.log('Octoprint Socket: Disconnecting')
		if self._ws:
			self._ws.close()
			self._ws.keep_running = False
			self._thread = None

	def _connect(self, username, session):
		if self._thread is None:
			_logger.log('Octoprint Socket: Connecting')

			def _on_message(ws, message):
				# _logger.log('Octoprint socket message recieved: %s' % message)
				self._callback.on_event(event=message)

			def _on_error(ws, error):
				_logger.log('Octoprint Socket Error: %s' % error)

			def _on_close(ws):
				_logger.log('Octoprint Socket: Ws Closed')
				self._callback.disconnected()

			def _on_open(ws):
				_logger.log('Octoprint Socket: Ws Opened')
				self._ws.send(_json.dumps({'auth': '%s:%s' % (username, session)}))
				self._ws.send(_json.dumps({'throttle': 10}))
				self._callback.connected()

			try:
				self._ws = websocket.WebSocketApp("ws://localhost:5000/sockjs/websocket", on_message=_on_message, on_error=_on_error, on_close=_on_close, on_open=_on_open)

				self._thread = threading.Thread(target=self._ws.run_forever)
				self._thread.daemon = True
				self._thread.start()
			except Exception as e:
				_logger.warn(e)

