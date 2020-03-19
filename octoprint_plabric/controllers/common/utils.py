from __future__ import absolute_import
import platform
import sys

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


def is_python3():
	if sys.version_info[0] < 3:
		return False
	return True
