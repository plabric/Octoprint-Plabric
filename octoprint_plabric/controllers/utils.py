from __future__ import absolute_import
import platform
import socket


def system():
	return platform.system()


def machine():
	return platform.machine()


def get_available_port():
	in_use = True
	port = 9001
	try:
		while in_use and port < 9100:
			port += 1
			in_use = _is_port_in_use(port)
	except Exception as e:
		return 9002
	return port


def _is_port_in_use(port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	return s.connect_ex(('localhost', port)) == 0
