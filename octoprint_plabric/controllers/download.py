import threading

import requests


class DownloadThread(threading.Thread):
	def __init__(self, url, dest, queue_main, queue_progress, log):
		threading.Thread.__init__(self)
		self.daemon = True
		self._url = url
		self._dest = dest
		self._queue_main = queue_main
		self._queue_progress = queue_progress
		self._log = log

	def run(self):
		try:
			self.download_url(self._url)
		except Exception as e:
			self._log(e)
			self._queue_main.put(False)

	def download_url(self, url):
		self._log("[%s] Downloading %s -> %s" % (self.ident, url, self._dest))

		r = requests.get(url, stream=True)
		if r.status_code == 200:
			last_percent = 0
			with open(self._dest, 'wb') as f:
				total_size = int(r.headers.get('content-length', 0))

				if total_size is None:
					f.write(r.content)
				else:
					dl = 0
					total_length = int(total_size)
					for data in r.iter_content(chunk_size=4096):
						dl += len(data)
						f.write(data)
						done = int(100 * dl / total_length)
						if done != last_percent:
							last_percent = done
							self._queue_progress.put_nowait(last_percent)
		else:
			self._log('Error downloading Docker image: %d' % r.status_code)
			self._queue_main.put_nowait(False)

		# Retrieve HTTP meta-data
		self._log(r.status_code)
		self._log(r.headers['content-type'])
		self._log(r.encoding)
		self._queue_main.put_nowait(r.status_code == 200)
