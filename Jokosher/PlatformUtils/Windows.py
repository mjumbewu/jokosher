

import urllib


def getFullName():
	#TODO: Work out how to get the fullname in windows
	return ""

def samefile(path1, path2):
	return path1 == path2

def url2pathname(url):
	return urllib.url2pathname(url)

def pathname2url(path):
	#Windows pathname2url appends // to the front of the path
	return "file:%s" % urllib.pathname2url(path)

def GetRecordingDefaults():
	defaults = {
			"fileformat": "vorbisenc ! oggmux",
			"file_extension": "ogg",
			"audiosrc" : "dshowaudiosrc"
		}
	return defaults


def GetPlaybackDefaults():
	defaults = {
			"audiosink": "directsoundsink"
		}
	return defaults	
