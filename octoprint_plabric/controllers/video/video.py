import os
import threading
from collections import deque
import ffmpeg

from octoprint_plabric import config
from octoprint_plabric.controllers.common import logger as _logger, utils as _utils

if _utils.is_python3():
	from urllib.request import urlopen
else:
	from urllib2 import urlopen


class VideoStreamProtocol:
	def on_video_started(self):
		return NotImplementedError

	def on_video_stopped(self):
		return NotImplementedError


class VideoStreamer:
	def __init__(self, janus_url, port, machine, system, is_raspberry=False):
		self._url = "rtp://%s:%d?pkt_size=1300" % (janus_url, port)
		self._callback = None
		self._process = None
		self._vcodec = 'libx264' if not is_raspberry else 'h264_omx'
		self._shutting_down = False
		self._flip_horizontally = False
		self._flip_vertically = False
		self._rotate_90_clockwise = False
		self._enabled = False
		self._extra_arguments = {'s': '640x480', 'b:v': 500000}

		if system == 'Linux':
			if machine == 'armv7l':
				self._ffmpeg_dir = os.path.join(config.FFMPEG_DIR, 'linux', 'armv7l', 'ffmpeg')
			else:
				self._ffmpeg_dir = os.path.join(config.FFMPEG_DIR, 'linux', 'x86_64', 'ffmpeg')
				self._extra_arguments['preset'] = 'medium'
				self._extra_arguments['crf'] = 17
				self._extra_arguments['tune'] = 'zerolatency'
			self._enabled = True
			os.system("chmod -R 777 %s" % config.FFMPEG_DIR)
		else:
			self._ffmpeg_dir = None
			_logger.log('Unable to start ffmpeg on %s system' % system)

	def set_callback(self, callback):
		self._callback = callback

	def _stream_from_device(self):
		_logger.log('Video stream: Start from device')
		try:
			self._stream(ffmpeg.input('/dev/video0', input_format='mjpeg'))
		except Exception as e:
			_logger.warn(e)

	def _stream_from_url(self, url):
		_logger.log('Video stream: Start from url %s' % url)
		try:
			self._stream(ffmpeg.input(url))
		except Exception as e:
			_logger.warn(e)

	def _stream(self, base):
		arguments = self._extra_arguments
		r = self.get_rotation_params()
		if r:
			arguments['vf'] = r

		try:
			self._process = base\
				.output(self._url, format='rtp', vcodec=self._vcodec, pix_fmt='yuv420p', an=None, ** arguments)\
				.run_async(cmd=self._ffmpeg_dir, pipe_stdin=True, pipe_stderr=True, quiet=True)
		except Exception as e:
			_logger.warn(e)

	def start(self, url=None, flip_horizontally=False, flip_vertically=False, rotate_90_clockwise=False):
		if self._enabled:
			if not self._process:
				self._flip_horizontally = flip_horizontally
				self._flip_vertically = flip_vertically
				self._rotate_90_clockwise = rotate_90_clockwise

				self._shutting_down = False
				url = url if url else 'http://localhost:8080/?action=stream'
				try:
					_logger.log(url)
					code = urlopen(url).getcode()
				except Exception:
					code = 404

				if code == 200:
					self._stream_from_url(url=url)
				else:
					self._stream_from_device()

				self.monitor(self._process)

	def stop(self):
		if self._process:
			self._shutting_down = True
			try:
				self._process.communicate(input=str.encode("q"))
				self._process.terminate()
				self._process.kill()
			except Exception as e:
				_logger.warn(e)
			self._process = None
			self._callback.on_video_stopped()

	def monitor(self, process):

		def monitor_ffmpeg_process():
			while True:
				ring_buffer = deque(maxlen=200)
				err = process.stderr.readline()
				if not err:
					if self._shutting_down:
						return
					process.wait()
					_logger.warn('STDERR:\n{}\n'.format('\n'.join(ring_buffer)))
					self.stop()
					return
				else:
					ring_buffer.append(err)

		gst_thread = threading.Thread(target=monitor_ffmpeg_process)
		gst_thread.daemon = True
		gst_thread.start()

	def get_rotation_params(self):
		rotation = []
		if self._flip_vertically:
			rotation.append("vflip")
		if self._flip_horizontally:
			rotation.append("hflip")
		if self._rotate_90_clockwise:
			rotation.append("transpose=2")
		f = None
		for r in rotation:
			f = "%s,%s" % (f, r) if f else r
		return f
