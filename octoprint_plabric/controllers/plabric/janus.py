import os
import subprocess
import threading

from octoprint_plabric import config
from octoprint_plabric.controllers.common import logger as _logger
import websocket
import json as _json


class JanusProtocol:
	def send_msg(self, key, data=None):
		raise NotImplementedError

	def connected(self):
		raise NotImplementedError

	def disconnected(self):
		raise NotImplementedError

	def wrtc_disconnected(self):
		raise NotImplementedError

	def wrtc_connected(self):
		raise NotImplementedError

	def wrtc_paused(self):
		raise NotImplementedError

	def video_stream_started(self):
		raise NotImplementedError

	def video_stream_paused(self):
		raise NotImplementedError

	def janus_running(self):
		raise NotImplementedError


class Janus:

	def __init__(self, machine, system, ports, callback=None):
		_logger.log('Janus Socket: Initializing')

		# websocket.enableTrace(True)
		self._janus_ws_port = ports[0]
		self._janus_api_port = ports[1]
		self._janus_video_port = ports[2]
		self._url = 'ws://%s:%d/' % (config.JANUS_HOST, self._janus_ws_port)
		self._janus_thread = None
		self._janus_proc = None
		self._ws = None
		self._ws_thread = None
		self._transaction = None
		self._session_id = None
		self._handle_id = None
		self._paused = False
		self._streams = []
		self._callback = callback
		self._stream_on_start = False
		self._enabled = False

		if system == 'Linux':
			if machine == 'armv7l':
				self._janus_dir = os.path.join(config.JANUS_DIR, 'linux', 'armv7l')
				self._enabled = True
			else:
				self._janus_dir = os.path.join(config.JANUS_DIR, 'linux', 'x86_64')
				self._enabled = True
		else:
			self._janus_dir = None
			_logger.log('Unable to start janus on %s system' % system)

	def run(self, json_servers):
		if config.JANUS_RUN_LOCAL and self._enabled:
			_logger.log('Janus: Starting')

			def ll():
				janus_cmd = os.path.join(self._janus_dir, 'run_janus.sh')
				self._janus_proc = subprocess.Popen(janus_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

				# if config.DEBUG:
				# 	while self._janus_proc:
				# 		line = self._janus_proc.stdout.readline()
				# 		if line:
				# 			_logger.log('JANUS: ' + line)

			self._configure(json_servers=json_servers)
			janus_thread = threading.Thread(target=ll)
			janus_thread.daemon = True
			janus_thread.start()
		self._callback.janus_running()

	def get_video_port(self):
		return self._janus_video_port

	def _configure(self, json_servers):
		if not self._enabled:
			return
		_logger.log('Janus: Configuring')

		stun_server = None
		stun_port = None

		turn_server = None
		turn_port = None
		turn_username = None
		turn_credential = None

		for s in json_servers:
			if 'username' in s and 'credential' in s:
				if not turn_server:
					turn_server, turn_port = s['urls'][0].replace('turn:', '').split(":")
					turn_username = s['username']
					turn_credential = s['credential']
			else:
				if not stun_server:
					stun_server, stun_port = s['urls'][0].replace('stun:', '').split(":")

		self._process_config_file(name='janus', params={'JANUS_DIR': self._janus_dir,
														'TURN_SERVER': turn_server, 'TURN_PORT': turn_port,
														'TURN_USERNAME': turn_username, 'TURN_CREDENTIAL': turn_credential,
														'STUN_SERVER': stun_server, 'STUN_PORT': stun_port})
		self._process_config_file(name='janus.transport.http', params={'JANUS_API_PORT': self._janus_api_port})
		self._process_config_file(name='janus.transport.websockets', params={'JANUS_WS_PORT': self._janus_ws_port})
		self._process_config_file(name='janus.plugin.streaming', params={'JANUS_VIDEO_PORT': self._janus_video_port})

	def _process_config_file(self, name, params):
		janus_conf_template = os.path.join(self._janus_dir, 'etc/janus/%s.jcfg.template' % name)
		janus_conf_path = os.path.join(self._janus_dir, 'etc/janus/%s.jcfg' % name)
		if not os.path.isfile(janus_conf_template):
			_logger.log('Janus: Config file not found: %s' % janus_conf_template)
			return

		with open(janus_conf_template, "rt") as fin:
			with open(janus_conf_path, "wt") as fout:
				for line in fin:
					if len(line) > 0:
						for key, value in params.items():
							if key in line:
								if value is None:
									line = '	#%s' % line
								else:
									line = line.replace('{%s}' % key, str(value))
					fout.write(line)

	def connect(self):
		if self._ws_thread is None and self._enabled:
			_logger.log('Janus: Connecting')

			def _on_error(ws, error):
				_logger.log('Janus Error: %s' % error)

			def _on_message(ws, msg):
				self._process_msg(msg)

			def _on_close(ws):
				_logger.log('Janus: Ws Closed')
				self._callback.disconnected()

			def _on_open(ws):
				_logger.log('Janus: Ws Opened')
				self._create_session()

			try:
				self._ws = websocket.WebSocketApp(self._url, on_open=_on_open, on_message=_on_message, on_close=_on_close, on_error=_on_error, subprotocols=['janus-protocol'])
				self._ws_thread = threading.Thread(target=self._ws.run_forever)
				self._ws_thread.daemon = True
				self._ws_thread.start()
			except Exception as e:
				_logger.warn(e)

	def ws_connected(self):
		return self._ws and self._ws.sock and self._ws.sock.connected

	def disconnect(self):
		_logger.log('Janus: Disconnecting')

		if self.ws_connected():
			self._ws.close()
			self._ws.keep_running = False
			self._ws_thread = None
			self._paused = False
			self._stream_on_start = False

		if self._janus_proc:
			try:
				self._janus_proc.terminate()
			except Exception as e:
				_logger.warn(e)

		self._janus_thread = None

	def _create_session(self):
		_logger.log('Janus: Creating transaction')
		data = _json.dumps({'janus': 'create', 'transaction': 'create'})
		self._send_to_janus(data)

	def _attach_plugin(self):
		_logger.log('Janus: Attaching plugin')
		data = _json.dumps({'janus': 'attach', 'transaction': 'attach_plugin', 'session_id': self._session_id, 'plugin': 'janus.plugin.streaming', 'request': 'list'})
		self._send_to_janus(data)

	def on_signaling(self, data):
		if data['type'] == 'offer':
			self.on_offer_received(data)
		elif data['type'] == 'answer':
			self.on_answer_received(data)
		elif data['type'] == 'candidate':
			self.on_ice_candidate_received(data)

	def on_offer_received(self, json):
		_logger.log('Janus: Offer received')
		jsep = {
			'type': 'offer',
			'sdp': json['sdp']
		}
		data = _json.dumps({'janus': 'message', 'transaction': 'on_offer_received', 'session_id': self._session_id, 'handle_id': self._handle_id, 'body': {}, 'jsep': jsep})
		self._send_to_janus(data)

	def on_answer_received(self, json):
		_logger.log('Janus: Answer received')
		jsep = {
			'type': 'answer',
			'sdp': json['sdp']
		}
		data = _json.dumps({'janus': 'message', 'transaction': 'on_answer_received', 'session_id': self._session_id, 'handle_id': self._handle_id, 'body': {}, 'jsep': jsep})
		self._send_to_janus(data)

	def on_ice_candidate_received(self, json):
		_logger.log('Janus: Ice candidate received')
		candidate = {
			'sdpMid': json["id"],
			'sdpMlineIndex': json["label"],
			'candidate': json['candidate']
		}
		data = _json.dumps({'janus': 'trickle', 'transaction': 'on_ice_candidate_received', 'session_id': self._session_id, 'handle_id': self._handle_id, 'candidate': candidate})
		self._send_to_janus(data)

	def _send_session_description(self, _type, description):
		_logger.log('Janus: Session description sent')
		obj = {}
		obj["type"] = _type
		obj["sdp"] = description
		self._callback.send_msg(key='signaling', data=obj)

	def _update_streams_list(self):
		_logger.log('Janus: Update streams list')
		body = {'request': 'list'}
		self._send_msg(body=body, transaction='update_streams_list')

	def _start_streams(self, stream):
		body = {'request': 'watch' if not self._paused else 'start', 'id': stream['id']}
		self._send_msg(body=body, transaction='start_stream_%d' % stream['id'])
		self._paused = False

	def start_video_stream(self):
		_logger.log('Janus: Start video stream')
		if not self.ws_connected():
			self._stream_on_start = True
			self.connect()
		else:
			self._start_streams(self._streams[0])

	def stop_video_stream(self):
		_logger.log('Janus: Stop video stream')
		if self.ws_connected():
			self._paused = True
			body = {'request': 'pause', 'id': self._streams[0]['id']}
			self._send_msg(body=body, transaction='stop_stream_%d' % self._streams[0]['id'])
			self._callback.video_stream_paused()

	def _send_msg(self, body, transaction):
		data = _json.dumps({'janus': 'message', 'transaction': transaction, 'session_id': self._session_id, 'handle_id': self._handle_id, 'body': body})
		self._send_to_janus(data=data)

	def _send_to_janus(self, data):
		if self.ws_connected():
			self._ws.send(data)

	def _process_msg(self, msg):
		json = _json.loads(msg)
		if json['janus'] == 'ack':
			return

		_logger.log('Janus msg: %s' % json)

		if json['janus'] == 'success':
			if json['transaction'] == 'create':
				self._session_id = json['data']['id']
				self._attach_plugin()
			elif json['transaction'] == 'attach_plugin':
				self._handle_id = json['data']['id']
				self._send_to_janus(data=_json.dumps({'janus': 'keepalive', 'transaction': 'keepalive', 'session_id': self._session_id}))
				self._update_streams_list()

			elif json['transaction'] == 'update_streams_list':
				self._streams = json['plugindata']['data']['list']
				if self._stream_on_start:
					self.start_video_stream()

		if json['janus'] == 'event':
			if 'jsep' in json:
				self._send_session_description(json['jsep']['type'], json['jsep']['sdp'])

		if json['janus'] == 'hangup':
			_logger.log('Disconnected WebRTC')
			self._callback.wrtc_disconnected()

		if json['janus'] == 'webrtcup':
			_logger.log('Connected WebRTC')
			self._callback.wrtc_connected()

		if json['janus'] == 'event':
			if 'plugindata' in json and 'data' in json['plugindata'] and 'streaming' in json['plugindata']['data']:
				if json['plugindata']['data']['streaming'] == 'event':
					if 'result' in json['plugindata']['data']:
						if json['plugindata']['data']['result']['status'] == 'started':
							self._callback.video_stream_started()


