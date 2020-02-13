import os
import threading
from enum import Enum

import docker
import requests
import queue

from octoprint_plabric import config
from octoprint_plabric.controllers import download as _download
from octoprint_plabric.controllers import utils as _utils


class DockerState(Enum):
	DOCKER_NOT_AVAILABLE = 'not_installed',
	READY = 'ready'
	DOWNLOADING = 'downloading',
	INSTALLING_IMAGE = 'installing_image',
	INSTALLED = 'installed'
	STARTING = 'starting'
	RUNNING = 'running',
	STOPPING = 'stopping'
	STOPPED = 'stopped'


DOCKER_IMAGE_FOLDER = '.docker_image'


def get_file_image(path):
	path = os.path.join(path, DOCKER_IMAGE_FOLDER)
	file_path = None
	if os.path.exists(path):
		for f in os.listdir(path):
			file_path = os.path.join(path, f)
	return file_path if file_path is not None and config.DOCKER_IMAGE_NAME in file_path else None


def get_last_image_name(path):
	path = os.path.join(path, DOCKER_IMAGE_FOLDER)
	file_path = os.path.join(path, "last.txt")
	if os.path.isfile(file_path):
		file = open(file_path, "r")
		data = file.read()
		return data
	return None


def store_last_image_name(path, name):
	path = os.path.join(path, DOCKER_IMAGE_FOLDER)
	file_path = os.path.join(path, "last.txt")
	file = open(file_path, "w")
	head, tail = os.path.split(name)
	file.write(tail)
	file.close()


def set_interval(interval):
	def decorator(function):
		def wrapper(*args, **kwargs):
			if hasattr(function, 'interval_enabled') and function.interval_enabled:
				return
			stopped = threading.Event()

			def loop():
				while not stopped.wait(interval):
					function(*args, **kwargs)

			t = threading.Thread(target=loop)
			t.daemon = True
			t.start()
			function.interval_enabled = True
			return stopped
		return wrapper
	return decorator


class DockerController:

	def __init__(self, plugin):
		self._plugin = plugin
		self._logger = self._plugin.get_logger()
		self._client = docker.from_env()
		self._install_progress = 0
		self._download_progress = 0
		self._state = None
		self.set_new_state(DockerState.DOCKER_NOT_AVAILABLE if self._client is None else DockerState.READY)
		self.check_still_running()
		self.check_new_version()

	def get_image(self):
		try:
			image = self._client.images.get(config.DOCKER_IMAGE_NAME)
		except docker.errors.NotFound as e:
			return None
		except requests.exceptions.ConnectionError:
			self.set_new_state(DockerState.DOCKER_NOT_AVAILABLE)
			return None
		return image

	def get_container(self):
		try:
			container = self._client.containers.get(config.DOCKER_CONTAINER_NAME)
		except docker.errors.NotFound as e:
			return None
		except requests.exceptions.ConnectionError:
			self.set_new_state(DockerState.DOCKER_NOT_AVAILABLE)
			return None
		return container

	@set_interval(60 * 60 * 24 * 1)
	def check_new_version(self):
		if self._state != DockerState.DOCKER_NOT_AVAILABLE:
			url, version = self.get_download_url()
			self.log(url)
			if url is not None and version is not None:
				last_version = get_last_image_name(self._plugin.get_plugin_data_folder())
				self.log(last_version)
				if last_version is None or last_version != version:
					self.download_image()

	@set_interval(300)
	def check_still_running(self):
		self.log('Check still running')
		if self._state != DockerState.RUNNING:
			self.run()

	def run(self, allow_install=False):
		if self._state != DockerState.DOCKER_NOT_AVAILABLE:
			if self.get_image() is None:
				# Ask user for download/install image
				if allow_install:
					self.download_image()
				return

			self.set_new_state(DockerState.STARTING)
			self.log(self._plugin.available_port)
			container = self.get_container()
			if container:
				container.remove(force=True)
			self._client.containers.run(
				config.DOCKER_IMAGE_NAME,
				detach=True,
				privileged=True,
				name=config.DOCKER_CONTAINER_NAME,
				auto_remove=True,
				network_mode="host",
				environment=["PLUGIN_PORT=%d" % self._plugin.available_port])
			self.set_new_state(DockerState.RUNNING)

	def stop(self):
		if self._state == DockerState.RUNNING and self._state != DockerState.STOPPING:
			container = self.get_container()
			if container is not None:
				self.set_new_state(DockerState.STOPPING)
				container.stop()
				self.set_new_state(DockerState.STOPPED)

	def install_image(self):
		if self._state != DockerState.INSTALLING_IMAGE:
			if self.get_image() is not None:
				self.uninstall_image()
			path = get_file_image(self._plugin.get_plugin_data_folder())
			if path is not None:
				self.set_new_state(DockerState.INSTALLING_IMAGE)
				try:
					with open(path, 'rb') as f:
						self._client.images.load(f)
				except Exception as e:
					self.notify_error(self._state)

				self.clean_downloads_folder()
				self.set_new_state(DockerState.INSTALLED)
				store_last_image_name(self._plugin.get_plugin_data_folder(), path)
				self.run()

	def uninstall_image(self):
		if self.get_image() is not None:
			self.stop()
			self.remove_container()
			self._client.images.remove(image=config.DOCKER_IMAGE_NAME, force=True)

	def remove_container(self):
		container = self.get_container()
		if container:
			container.remove(force=True)

	def download_image(self):
		if self._state != DockerState.DOWNLOADING:
			self.log('Download image')
			self.set_new_state(DockerState.DOWNLOADING)
			self.clean_downloads_folder()
			url, version = self.get_download_url()
			if url is None or version is None:
				self.notify_error(self._state)
				return

			folder = os.path.join(self._plugin.get_plugin_data_folder(), DOCKER_IMAGE_FOLDER)
			if not os.path.isdir(folder):
				os.makedirs(folder)
			dest = os.path.join(folder, version)
			queue_main = queue.Queue()
			queue_progress = queue.Queue()
			t = _download.DownloadThread(url, dest, queue_main, queue_progress, self.log)
			t.start()

			while t.isAlive():
				if not queue_progress.empty():
					progress = queue_progress.get_nowait()
					if progress is not None:
						self.download_progress(progress)
				if not queue_main.empty():
					succeed = queue_main.get_nowait()
					if succeed is not None:
						self.download_callback(succeed)

	def download_callback(self, succeed):
		if succeed:
			self.log('Download Docker image done')
			self.install_image()
		else:
			self.notify_error(self._state)
			self.log('Unable to download Docker image')

	def download_progress(self, progress):
		self.log('Download progress: ' + str(progress))
		self._download_progress = progress
		self._plugin.update_ui_status()

	def get_download_progress(self):
		return self._download_progress

	def install_progress(self, progress):
		self.log('Install progress: ' + str(progress))
		self._install_progress = progress
		self._plugin.update_ui_status()

	def get_install_progress(self):
		return self._install_progress

	def clean_downloads_folder(self):
		path = os.path.join(self._plugin.get_plugin_data_folder(), DOCKER_IMAGE_FOLDER)
		if os.path.exists(path):
			for f in os.listdir(path):
				file_path = os.path.join(path, f)
				try:
					if os.path.isfile(file_path):
						os.unlink(file_path)
				except Exception as e:
					self.log(e)

	def get_download_url(self):
		r = requests.get('%s/octoprint/plugin/docker/image?s=%s&m=%s&p=%s' % (config.HOST_PLABRIC_API, _utils.system(), _utils.machine(), self._plugin.get_version()))
		if r.status_code == 200:
			json = r.json()
			if 'url' in json and 'version' in json:
				return json['url'], json['version']
		elif r.status_code == 409:
			self.log('OS not supported')
		else:
			self.log('Error retrieving Docker image url code: %d' % r.status_code)
		return None, None

	def notify_error(self, state):
		self.set_new_state(DockerState.DOCKER_NOT_AVAILABLE if self._client is None else DockerState.READY)

	def set_new_state(self, state):
		self._state = state
		self._plugin.refresh_docker_state(state)

	def log(self, msg):
		if config.DEBUG and self._logger:
			self._logger.info(msg)
