#	GNOMEAudioProfiles.py
#	--------------------
#	This extension is for adding the GNOME Audio Profiles into Jokosher

import Jokosher.Extension
import gconf
import traceback

EXTENSION_NAME = "GNOME Audio Profiles"
EXTENSION_DESCRIPTION = "Imports GNOME Audio Profiles into jokosher"
EXTENSION_VERSION = "0.0.2"
_GCONF_PROFILE_PATH = "/system/gstreamer/0.10/audio/profiles/"
_GCONF_PROFILE_LIST_PATH = "/system/gstreamer/0.10/audio/global/profile_list"
audio_profiles_list = []
API = None

def startup(api):
	global API, audio_profiles_list
	API = api
	_GCONF = gconf.client_get_default()
	profiles = _GCONF.get_list(_GCONF_PROFILE_LIST_PATH, 1)
	for name in profiles:
		if (_GCONF.get_bool(_GCONF_PROFILE_PATH + name + "/active")):
			description = _GCONF.get_string(_GCONF_PROFILE_PATH + name + "/name")
			extension = _GCONF.get_string(_GCONF_PROFILE_PATH + name + "/extension")
			encodeBin = "audioresample ! audioconvert ! " + _GCONF.get_string(_GCONF_PROFILE_PATH + name + "/pipeline")
			
			#last parameter is False to tell Jokosher to assume the strings are correct, and not check them.
			error = API.add_export_format(description, extension, encodeBin, False, False, False)
			if error == 0:
				#it has been succesfully added, so keep track of what we added
				audio_profiles_list.append((description, extension, encodeBin))

def shutdown():
	for format in audio_profiles_list:
		API.remove_export_format(*format)
