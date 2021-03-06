# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import admin_permission
from octoprint.settings import settings

from octoprint_plabric import config
from octoprint_plabric.controllers.common import logger as _logger, utils as _utils, storage as _storage
from octoprint_plabric.controllers.main import Step, Main
import json as _json


class PlabricPlugin(octoprint.plugin.SettingsPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.BlueprintPlugin,
					octoprint.plugin.EventHandlerPlugin):

	def __init__(self):
		self._host = None
		self._port = None
		self._main = None

	def on_event(self, event, payload):
		if event == 'ClientOpened':
			self.update_ui_status()
		elif event == 'PrintDone':
			if self._main:
				self._main.send_printer_event('finish')

	def on_startup(self, host, port):
		_logger.log('On Plabric Startup')
		self._host = host
		self._port = port
		self._main = Main(self)

		if self._main.plabric_api_key:
			self._main.start()

	def on_shutdown(self):
		_logger.log('On Plabric Shutdown')
		if self._main:
			self._main.disconnect()

	def get_host(self):
		if self._host is None or len(self._host) == 0 or self._host =="::":
			self._host = 'localhost'
		return "http://%s:%d" % (self._host, self._port)

	def get_video_stream_url(self):
		try:
			url = settings().get(["webcam", "stream"])
			return _utils.check_video_stream_url(url=url)
		except Exception:
			pass
		return None

	def get_webcam_params(self):
		return settings().get(["webcam"])

	def update_ui_status(self):
		self._plugin_manager.send_plugin_message(self._identifier, self.get_template_vars())

	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True)
		]

	def get_navbar_enabled(self):
		enabled = _storage.Storage(plugin=self).get_saved_setting('navbar_enabled')
		if enabled is None:
			_storage.Storage(plugin=self).save_setting('navbar_enabled', True)
			return True
		return enabled

	def get_template_vars(self):
		if self._main:
			return dict(plabric_token=self._main.plabric_token, step=self._main.step.value, status=self._main.get_status(), error=self._main.error, loading=self._main.loading, navbar_enabled=self.get_navbar_enabled())
		else:
			return dict(plabric_token=None, step=Step.LOGIN_NEEDED.value, status='Login need', error='', loading=False, navbar_enabled=self.get_navbar_enabled())

	# ~~ AssetPlugin mixin
	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/Plabric.js", "js/Plabric_navbar.js", "js/PlabricStatus.js"],
			css=["css/Plabric.css"],
			less=[]
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

	@octoprint.plugin.BlueprintPlugin.route("/data", methods=["GET"])
	@admin_permission.require(403)
	def status_data(self):
		return _json.dumps(self.get_template_vars())

	@octoprint.plugin.BlueprintPlugin.route("/authorize", methods=["POST"])
	@admin_permission.require(403)
	def oauth_octoprint(self):
		self._main.start(from_oauth=True)
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/disable", methods=["POST"])
	@admin_permission.require(403)
	def disable_api(self):
		self._main.disable()
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/reconnect", methods=["POST"])
	@admin_permission.require(403)
	def reconnect(self):
		self._main.reconnect()
		return ''

	@octoprint.plugin.BlueprintPlugin.route("/navbar/switch", methods=["POST"])
	@admin_permission.require(403)
	def navbar_switch(self):
		enabled = self.get_navbar_enabled()
		_storage.Storage(plugin=self).save_setting('navbar_enabled', not enabled)
		self.update_ui_status()
		return ''

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
