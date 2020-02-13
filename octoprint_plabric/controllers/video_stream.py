import threading
from datetime import datetime

import sys
if sys.version_info >= (3, 0):
	from urllib.request import urlopen
	from io import StringIO
if (3, 0) > sys.version_info >= (2, 5):
	from urllib2 import urlopen
	from StringIO import StringIO

from contextlib import closing


class VideoStream:
	def __init__(self, plugin, stream_url):
		self._stream_url = stream_url
		self._plugin = plugin
		self._logger = plugin.get_logger()
		self._vst = None
		self._run = False

	def run(self):
		self._run = True
		self._vst = threading.Thread(target=self.send)
		self._vst.daemon = True
		self._vst.start()

	def stop(self):
		self._run = False

	def send(self):
		stream = UpStream(self._stream_url, self._logger)
		while self._run:
			if self._plugin.get_socket() and stream:
				frame = stream.next()
				if frame:
					self._plugin.get_socket().send_video_stream(data={'data': frame.encode('base64')})

	def log(self, msg):
		if self._logger:
			self._logger.info(msg)


class UpStream:
	def __init__(self, stream_url, logger):
		self._stream_url = stream_url
		self.last_reconnect_ts = datetime.now()
		self.last_frame_ts = datetime.min
		self._logger = logger

	def __iter__(self):
		return self

	def next(self):
		try:
			self.last_frame_ts = datetime.now()
			return self.capture_mjpeg()
		except:
			pass

	def capture_mjpeg(self):
		try:
			with closing(urlopen(self._stream_url)) as res:
				chunker = MjpegStreamChunker()
				while True:
					data = res.readline()
					mjpg = chunker.chunk(data)
					if mjpg:
						res.close()
						return mjpg
		except Exception as e:
			self.log(e.args)

	def log(self, msg):
		if self._logger:
			self._logger.info(msg)


class MjpegStreamChunker:

	def __init__(self):
		self.boundary = None
		self.current_chunk = StringIO()

	def chunk(self, line):
		if not self.boundary:
			self.boundary = line
			self.current_chunk.write(line)
			return None

		if len(line) == len(self.boundary) and line == self.boundary:
			return self.current_chunk.getvalue()

		self.current_chunk.write(line)
		return None
