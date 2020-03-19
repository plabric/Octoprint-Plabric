import logging
from octoprint_plabric import config

_logger = logging.getLogger('octoprint.plugins.Plabric')


def log(msg):
	if _logger and config.DEBUG:
		_logger.info(msg)


def warn(msg):
	if _logger and config.DEBUG:
		_logger.warning(msg)
