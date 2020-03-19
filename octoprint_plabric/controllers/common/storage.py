import os
import yaml
from octoprint_plabric.controllers.common import logger as _logger


class Storage:

	def __init__(self, plugin):
		self._plugin = plugin

	def get_saved_settings(self):
		config_path = self._plugin.get_plugin_data_folder() + "/.config.yaml"
		s = None
		if os.path.isfile(config_path):
			with open(config_path, 'r') as stream:
				config_str = stream.read()
				s = yaml.load(config_str)
		if not s:
			return None
		return s

	def get_saved_setting(self, key):
		if key is not None:
			settings = self.get_saved_settings()
			if settings is not None and key in settings and settings[key] is not None:
				return settings[key]
		return None

	def save_setting(self, key, value):
		s = self.get_saved_settings()
		_logger.log('Saved key: %s - %s' %(key, value))
		if s is None:
			s = {}
		s[key] = value
		config_path = self._plugin.get_plugin_data_folder() + "/.config.yaml"
		with open(config_path, 'w+') as outfile:
			yaml.dump(s, outfile, default_flow_style=False)

	def clear_setting(self, key):
		s = self.get_saved_settings()
		_logger.log('Clear key: %s' % key)
		if s is None:
			return
		if key in s:
			s.pop(key)
		config_path = self._plugin.get_plugin_data_folder() + "/.config.yaml"
		with open(config_path, 'w+') as outfile:
			yaml.dump(s, outfile, default_flow_style=False)

	def get_file_temporal_path(self, file_name=None):
		directory = self._plugin.get_plugin_data_folder() + "/.tmp/files"
		if not os.path.exists(directory):
			os.makedirs(directory)
		if not file_name:
			file_name = 'tmp.gcode'
		return "%s/%s" % (directory, file_name)

	def delete_file_temporal(self, path):
		if os.path.exists(path):
			os.remove(path)
