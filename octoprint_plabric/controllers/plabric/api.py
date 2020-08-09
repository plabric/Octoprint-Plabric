import requests
from octoprint_plabric.controllers.common.api import API, APIProtocol
from octoprint_plabric.controllers.common import logger as _logger


class PlabricAPI(API):

	def __init__(self, domain):
		super(PlabricAPI, self).__init__(domain=domain, name='Plabric API')

	def get_temporal_token(self, octoprint_api_key, callback):
		self.post(path='/octoprint/plugin/token', params={'octoprint_api_key': octoprint_api_key}, callback=callback)

	def get_webrtc_servers(self, plabric_api_key, callback):
		self.post(path='/octoprint/plugin/servers', params={'api_key': plabric_api_key}, callback=callback)

	def get_file_url(self, plabric_api_key, file_id, callback):
		self.post(path='/octoprint/plugin/file/url', params={'api_key': plabric_api_key, 'id': file_id}, callback=callback)

	def send_event(self, plabric_api_key, event, callback):
		self.post(path='/octoprint/plugin/printer/event', params={'api_key': plabric_api_key, 'event': event}, callback=callback)

	def send_metadata(self, plabric_api_key, plugin_version, machine, system, pi_version, callback):
		self.post(path='/octoprint/plugin/metadata', params={'api_key': plabric_api_key, 'p': plugin_version, 'm': machine, 's': system, 'r': pi_version}, callback=callback)

	def download_temporal_file(self, plabric_api_key, file_id, destination, callback):
		class Response(APIProtocol):
			def __init__(self, p, destination, callback):
				self._p = p
				self._callback = callback
				self._destination = destination

			def on_succeed(self, data):
				url = data['url']
				self._p.execute_dowload(url=url, destination=self._destination, callback=callback)

			def on_error(self, error):
				self._callback.on_error(error)

		self.get_file_url(plabric_api_key=plabric_api_key, file_id=file_id, callback=Response(p=self, destination=destination, callback=callback))

	def execute_dowload(self, url, destination, callback):
		_logger.log('Plabric API: Downloading file')
		r = requests.get(url, stream=True)
		if r.status_code == 200:
			with open(destination, 'wb') as f:
				total_size = int(r.headers.get('content-length', 0))
				if total_size is None:
					f.write(r.content)
				else:
					dl = 0
					for data in r.iter_content(chunk_size=4096):
						dl += len(data)
						f.write(data)
			callback.on_succeed(None)
		else:
			callback.on_error(r.status_code)
