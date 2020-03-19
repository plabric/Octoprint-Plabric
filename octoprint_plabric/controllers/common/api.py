
import requests

from octoprint_plabric.controllers.common import logger as _logger


class APIProtocol:

	def on_succeed(self, data):
		raise NotImplementedError

	def on_error(self, error):
		raise NotImplementedError


class API(object):

	def __init__(self, domain, name):
		self._domain = domain
		self._name = name
		_logger.log('%s: Initializing' % name)

	def _get_url(self, path):
		return "%s%s" % (self._domain, path)

	def get(self, path, params=None, headers=None, callback=None):
		_logger.log('%s: Get - %s' % (self._name, self._get_url(path)))
		self._execute(requests.get(self._get_url(path), params=params, headers=headers), callback)

	def post(self, path, params=None, headers=None, callback=None):
		_logger.log('%s: Post - %s' % (self._name, self._get_url(path)))
		self._execute(requests.post(self._get_url(path), json=params, headers=headers), callback)

	def put(self, path, params=None, headers=None, callback=None):
		_logger.log('%s: Put - %s' % (self._name, self._get_url(path)))
		self._execute(requests.put(self._get_url(path), json=params, headers=headers), callback)

	def patch(self, path, params=None, headers=None, callback=None):
		_logger.log('%s: Patch - %s' % (self._name, self._get_url(path)))
		self._execute(requests.patch(self._get_url(path), json=params, headers=headers), callback)

	def delete(self, path, params=None, headers=None, callback=None):
		_logger.log('%s: Delete - %s' % (self._name, self._get_url(path)))
		self._execute(requests.delete(self._get_url(path), json=params, headers=headers), callback)

	def _execute(self, resp, callback=None):
		try:
			status = resp.status_code
			if 200 <= status < 300:
				_logger.log('%s: Succeed - %d' % (self._name, status))
				if callback:
					try:
						callback.on_succeed(resp.json())
					except Exception as e:
						pass
			else:
				_logger.log('%s: Error - %d' % (self._name, status))
				if callback:
					callback.on_error(status)
		except Exception as e:
			_logger.log('%s: Error - %s' % (self._name, e))
			if callback:
				callback.on_error(404)
