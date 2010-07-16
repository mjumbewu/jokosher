

import os, os.path, urllib
import pwd


def getFullName():
	try:
		# Try to get the full name if it exists
		fullname = pwd.getpwuid(os.getuid())[4].split(",")[0]
		if fullname == "":
			fullname = pwd.getpwuid(os.getuid())[0]
		return fullname
	except:
		# If we can't get the fullname, then just use the login
		return pwd.getpwuid(os.getuid())[0]

def samefile(path1, path2):
	return os.path.samefile(path1, path2)


def url2pathname(url):
	return urllib.url2pathname(url)

def pathname2url(path):
	# urllib.pathname2url uses urllib.quote(), which cannot handle unicode.
	# See http://bugs.python.org/issue1712522 for details.
	# Basically its fixed in Python 3.0+ because all strings are utf8
	# and a safe assumption can be made. But here in Python 2.x urllib.quote()
	# expects *bytes* so we have to convert it explicitly.
	path = path.encode('utf8')
	
	return "file://%s" % urllib.pathname2url(path)

def GetRecordingDefaults():
	return dict()

def GetPlaybackDefaults():
	return dict()

