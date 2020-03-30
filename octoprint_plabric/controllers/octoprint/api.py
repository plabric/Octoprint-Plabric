from enum import Enum
from octoprint_plabric.controllers.common.api import API, APIProtocol
from octoprint_plabric.controllers.common import logger as _logger
import requests


class OctoprintAPIProtocol(APIProtocol):
	def on_download_first(self, data):
		raise NotImplementedError


class OctoprintAPI(API):

	def __init__(self, domain):
		super(OctoprintAPI, self).__init__(domain=domain, name='Octoprint API')
		# super().__init__(domain=domain, name='Octoprint API')
		self._api_key = None

	def set_api_key(self, api_key):
		self._api_key = api_key

	def get_headers(self, data=None):
		h = {'Content-Type': 'application/json'}
		if self._api_key:
			h['X-Api-Key'] = self._api_key
		if data:
			h['Content-Length'] = str(len(data))
		return h

	def probe_plugin_appkeys(self, callback):
		self.get(path='/plugin/appkeys/probe', callback=callback)

	def request_app_token(self, callback):
		self.post(path='/plugin/appkeys/request', params={'app': 'Plabric'}, callback=callback)

	def request_api_key(self, app_token, callback):
		self.get(path='/plugin/appkeys/request/%s' % app_token, callback=callback)

	def login(self, octoprint_api_key, callback):
		self.set_api_key(octoprint_api_key)
		self.post(path='/api/login', params={'passive': True}, headers=self.get_headers(), callback=callback)

	def call_method(self, data, callback):
		action = DataAction(raw=data)
		if action.method == Method.GET:
			self.get(path=action.path, headers=self.get_headers(), callback=callback)

		elif action.method == Method.POST:
			if not action.download_first:
				self.post(path=action.path, params=action.params, headers=self.get_headers(), callback=callback)
			else:
				callback.on_download_first(data)
		elif action.method == Method.PUT:
			self.put(path=action.path, params=action.params, headers=self.get_headers(), callback=callback)
		elif action.method == Method.PATCH:
			self.patch(path=action.path, params=action.params, headers=self.get_headers(), callback=callback)
		elif action.method == Method.DELETE:
			self.delete(path=action.path, params=action.params, headers=self.get_headers(), callback=callback)

	def upload_file(self, data, file_path, callback):
		_logger.log('Octoprint API: Uploading file')
		action = DataAction(raw=data)
		file_name = data['params']['file_name']
		_logger.log('%s Post file on: %s' % (self._name, self._get_url(action.path)))

		files = {"file": ("%s.gcode" % file_name, open(file_path, "rb").read())}
		payload = {'path': 'plabric/tmp', 'select': 'true', 'print': 'false'}
		self._execute(requests.post(self._get_url(action.path), data=payload, files=files, headers={'X-Api-Key': self._api_key}), callback)


class Method(Enum):
	GET = 'get'
	POST = 'post'
	PUT = 'put'
	PATCH = 'patch'
	DELETE = 'delete'
	DOWNLOAD = 'download'


class DataAction:

	def __init__(self, raw):
		self.raw = raw
		self.method = None
		self.path = None
		self.params = None
		self.download_first = False
		self.parse()

	def parse(self):
		self.method = Method(self.raw['method'])
		self.path = self.raw['url']
		if 'params' in self.raw:
			self.params = self.raw['params']
		if self.method == Method.POST and self.raw['api'] == 'files':
			self.download_first = True
