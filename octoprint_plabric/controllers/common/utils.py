from __future__ import absolute_import
import platform
import re
import sys
import socket


def system():
	return platform.system()


def machine():
	return platform.machine()


def is_raspberry():
	try:
		with open('/sys/firmware/devicetree/base/model', 'r') as firmware_model:
			if firmware_model.read().find('Raspberry Pi') > -1:
				return True
	except Exception:
		pass
	return False


def pi_version():
	try:
		with open('/sys/firmware/devicetree/base/model', 'r') as firmware_model:
			model = re.search('Raspberry Pi(.*)', firmware_model.read()).group(1)
			if model:
				return "0" if re.search('Zero', model, re.IGNORECASE) else "3"
			else:
				return None
	except:
		return None


def is_python3():
	if sys.version_info[0] < 3:
		return False
	return True


def check_video_stream_url(url):
	if url == '/webcam/?action=stream':
		return 'http://localhost:8080/?action=stream'
	if is_python3():
		from urllib.parse import urlparse
		result = urlparse(url)
	else:
		from urlparse import urlparse
		result = urlparse(url)
	if result:
		scheme = result.scheme if result.scheme else 'http'
		netloc = result.netloc if result.netloc else 'localhost:8080'
		url = "%s://%s%s?%s" % (scheme, netloc, result.path, result.query)
		if valid_url(url=url):
			return url
	return None


def valid_url(url):
	regex = re.compile(
		r'^(?:http|ftp)s?://'
		r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
		r'localhost|'
		r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
		r'(?::\d+)?'
		r'(?:/?|[/?]\S+)$', re.IGNORECASE)
	return re.match(regex, url) is not None


def get_free_ports(count=3, starting_port=9010):
	ports = []
	port = starting_port
	while len(ports) < count:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(2)  # 2 Second Timeout
		result = sock.connect_ex(('127.0.0.1', port))
		if result != 0:
			ports.append(port)
		port += 1
	return ports
