# coding=utf-8
from __future__ import absolute_import

import time
import requests
import yaml
import os

import octoprint.plugin
from octoprint.server import admin_permission

from octoprint_plabric.controllers.dock import DockerController as _docker, DockerState
from octoprint_plabric.controllers.socket import Socket as _socket, SocketState, ConfigState
from octoprint_plabric.controllers import utils as _utils
from octoprint_plabric import config
from octoprint_plabric.controllers import download as _download


class PlabricPlugin(octoprint.plugin.SettingsPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.BlueprintPlugin,
					octoprint.plugin.EventHandlerPlugin):

	def __init__(self):
		self._docker = None
		self._docker_state = DockerState.DOCKER_NOT_AVAILABLE

		self._socket = None
		self._socket_state = SocketState.DISCONNECTED

		self._os = _utils.system()
		self._machine = _utils.machine()
		self._temp_token = None
		self._config_state = ConfigState.NEEDED

		self._user_joined = False
		self._user_nick = None

		self.retries_count = 0
		self.available_port = _utils.get_available_port()
		self.tmp_p = None
		self.error = ''

	def on_event(self, event, payload):
		if event == 'ClientOpened':
			self.update_ui_status()

	def on_startup(self, host, port):
		self.init()

	def init(self):
		if not self._docker:
			self._docker = _docker(self)
		self._docker.run()

	def connect_socket(self):
		if not self._socket:
			self._socket = _socket(self)
		if not self._socket.is_connected():
			self._socket.connect()

	def disconnect_socket(self):
		if self._socket:
			if self._socket.is_connected():
				self._socket.disconnect()
				self._socket = None

	def retry_connection(self):
		if self._docker_state == DockerState.RUNNING:
			if self.retries_count < 2:
				self.retries_count += 1
				time.sleep(1)
				self.connect_socket()
			else:
				self.retries_count = 0
				if self._docker:
					self._docker.set_new_state(DockerState.STOPPED)

	def refresh_docker_state(self, state):
		self.log('Docker state: ' + state.name)
		self._docker_state = state
		self.update_ui_status()

		if state == DockerState.RUNNING:
			time.sleep(4)
			self.connect_socket()

	def refresh_socket_state(self, state):
		self.log('Socket state: ' + state.name)
		self._socket_state = state
		self.update_ui_status()

	def refresh_config_state(self, state):
		self.log('Config state: ' + state.name)
		self._config_state = state
		self.update_ui_status()
		if self._config_state == ConfigState.DONE:
			self._temp_token = None

	def set_user_joined(self, joined, nick=None):
		self._user_nick = nick
		self._user_joined = joined
		self.update_ui_status()

	def update_ui_status(self):
		self._plugin_manager.send_plugin_message(self._identifier, self.get_template_vars())

	def get_socket(self):
		return self._socket

	def set_video_stream_enabled(self, enabled):
		if enabled:
			self.log('Video stream started')
		else:
			self.log('Video stream stopped')

	def on_shutdown(self):
		if self._socket:
			self._socket.disconnect()
		if self._docker:
			self._docker.stop()

	def get_logger(self):
		return self._logger

	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True)
		]

	def get_template_vars(self):
		return dict(temp_token=self._temp_token,
					configurated=self._config_state == ConfigState.DONE,
					config_cancelled=self._config_state == ConfigState.CANCELLED,
					status=self.get_status(),
					docker_available=self._docker_state not in [DockerState.DOCKER_NOT_AVAILABLE],
					docker_running=self._docker_state == DockerState.RUNNING,
					error=self.error,
					os=self._os,
					machine=self._machine,
					installing=self._docker_state == DockerState.INSTALLING_IMAGE or self._docker_state == DockerState.DOWNLOADING,
					install_progress=self._docker.get_download_progress() if self._docker else 0,
					socket_connected=self._socket_state == SocketState.CONNECTED)

	def get_status(self):
		if self._docker_state == DockerState.DOCKER_NOT_AVAILABLE or self._docker_state == DockerState.READY:
			return 'Need install'

		if self._docker_state == DockerState.INSTALLING_IMAGE or self._docker_state == DockerState.DOWNLOADING:
			return 'Installing...'

		if self._docker_state == DockerState.INSTALLED:
			return 'Waiting...'

		if self._docker_state == DockerState.STARTING:
			return 'Starting...'

		if self._docker_state == DockerState.STOPPING:
			return 'Stopping...'

		if self._docker_state == DockerState.STOPPED:
			return 'Stopped'

		if self._docker_state == DockerState.RUNNING:
			if self._socket_state == SocketState.DISCONNECTED:
				return 'Disconnected'

			if self._socket_state == SocketState.CONNECTED:
				if self._config_state == ConfigState.NEEDED or self._config_state == ConfigState.CANCELLED:
					return 'Login needed'

				if self._user_joined:
					return 'User connected' if self._user_nick is None else '%s connected' % self._user_nick
				else:
					return 'Ready'

	def get_saved_settings(self):
		config_path = self.get_plugin_data_folder() + "/.config.yaml"
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
		self.log('Saved key: %s - %s' %(key, value))
		if s is None:
			s = {}
		s[key] = value
		config_path = self.get_plugin_data_folder() + "/.config.yaml"
		with open(config_path, 'w+') as outfile:
			yaml.dump(s, outfile, default_flow_style=False)

	def clear_setting(self, key):
		s = self.get_saved_settings()
		self.log('Clear key: %s' % key)
		if s is None:
			return
		if key in s:
			s.pop(key)
		config_path = self.get_plugin_data_folder() + "/.config.yaml"
		with open(config_path, 'w+') as outfile:
			yaml.dump(s, outfile, default_flow_style=False)


	# ~~ AssetPlugin mixin
	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/Plabric.js", "js/Plabric_navbar.js"],
			css=["css/Plabric.css"],
			less=["less/Plabric.less"]
		)

	def get_version(self):
		return self._plugin_version

	# ~~ Softwareupdate hook
	def get_update_information(self):
		return dict(
			Plabric=dict(
				displayName="Plabric",
				displayVersion=self._plugin_version,
				type="github_release",
				user="plabric",
				repo="OctoPrint-Plabric",
				current=self._plugin_version,
				pip="https://github.com/Plabric/OctoPrint-Plabric/archive/{target_version}.zip"
			)
		)

	def get_host_docker_image(self):
		self.log(self.available_port)
		return "%s:%d" % (config.HOST_DOCKER_IMAGE, self.available_port)

	def authorize(self):
		r = requests.get("%s/authorize" % self.get_host_docker_image())
		r.raise_for_status()

	def set_temp_token(self, token):
		if token:
			self._temp_token = token
			self.update_ui_status()

	def set_error(self, error):
		if error:
			if error == 'error_authorization':
				self.error = 'You have to allow access to Plabric for continue'
			self.update_ui_status()

	def set_error_install_docker(self, error):
		self.error = error
		self.update_ui_status()

	@octoprint.plugin.BlueprintPlugin.route("/authorize", methods=["GET"])
	@admin_permission.require(403)
	def authorize_access(self):
		self.error = ''
		self._temp_token = None
		if self._socket is None or self._socket_state == SocketState.DISCONNECTED:
			self.init()
		self.authorize()
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/disable", methods=["GET"])
	@admin_permission.require(403)
	def disable_api(self):
		self.clear_setting('api_key')
		if self._socket:
			self._socket.disable_connection()
		self.set_user_joined(False, None)
		self.refresh_config_state(ConfigState.NEEDED)
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/run_docker", methods=["GET"])
	@admin_permission.require(403)
	def run_docker(self):
		if self._docker:
			self._docker.run(allow_install=True)
		else:
			self.init()
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/reconnect", methods=["GET"])
	@admin_permission.require(403)
	def reconnect(self):
		if self._docker_state == DockerState.RUNNING:
			self.connect_socket()
		else:
			self.init()
		return ''

	def log(self, msg):
		if config.DEBUG and self._logger:
			self._logger.info(msg)

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Plabric"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = PlabricPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
