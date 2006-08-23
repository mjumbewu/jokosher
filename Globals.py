#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Globals.py
#	
#	This module contains variable definitions that can be used across the code
#	base and also includes methods for reading and writing these settings to
#	the Jokosher configuration in ~/.jokosher/config.
#
#-------------------------------------------------------------------------------

import ConfigParser
import os

class Settings:

	# the different settings in each config block
	general = {"mixdownformat": "value", "recentprojects": "value", "samplerate": "value", "sampleformat": "value", "startupaction" : "value"}
	recording = {"device": "value", "fileformat": "value", "devicecardnum": "value"}
	playback = {"device": "value", "devicecardnum": "value"}
	
	def __init__(self, filename = None):
		if not filename:
			self.filename = os.path.expanduser("~/.jokosher/config")
		else:
			self.filename = filename
		self.config = ConfigParser.ConfigParser()

		self.read()

	def read(self):
		"""Read in configuration settings from the config file"""
		
		self.config.read(self.filename)
	
		if not self.config.has_section("General"):
			self.config.add_section("General")
		if not self.config.has_section("Recording"):
			self.config.add_section("Recording")
		if not self.config.has_section("Playback"):
			self.config.add_section("Playback")
	
		for key, value in self.config.items("General"):
			self.general[key] = value
		for key, value in self.config.items("Recording"):
			self.recording[key] = value
		for key, value in self.config.items("Playback"):
			self.playback[key] = value
		
	def write(self):
		"""Write config settings to the config file"""
		
		for key in self.general:
			self.config.set("General", key, self.general[key])
		for key in self.recording:
			self.config.set("Recording", key, self.recording[key])
		for key in self.playback:
			self.config.set("Playback", key, self.playback[key])
			
		# delete a .jokosher file if it exists, because that's old-fashioned
		old_jokosher_file = os.path.expanduser("~/.jokosher")
		if os.path.isfile(old_jokosher_file):
		  os.unlink(old_jokosher_file)
		  
		# make sure that the directory that the config file is in exists
		new_jokosher_file_dir = os.path.split(self.filename)[0]
		if not os.path.isdir(new_jokosher_file_dir): 
			os.makedirs(new_jokosher_file_dir)
		file = open(self.filename, 'w')
		self.config.write(file)
		file.close()
				
		# make some other directories that we're going to need later
		for d in ['extensions', 'instruments', 'presets']:
			new_dir = os.path.join(new_jokosher_file_dir, d)
			if not os.path.isdir(new_dir): 
				try:
					os.makedirs(new_dir)
				except:
					raise "Failed to create user config directory %s" % new_dir
		for d in ['effects', 'mixdown']:
			new_dir = os.path.join(new_jokosher_file_dir, 'presets', d)
			if not os.path.isdir(new_dir): 
				try:
					os.makedirs(new_dir)
				except:
					raise "Failed to create user config directory %s" % new_dir

def SetAbsPaths():
	"""Set a bunch of paths for use across the project. This is particularly
	useful for that 'orrible packaging lot"""
	global JOKOSHER_PATH, IMAGE_PATH, GLADE_PATH, LOCALE_DIR, LOCALE_APP, EFFECT_PRESETS_PATH
	
	JOKOSHER_PATH = os.path.dirname(os.path.abspath(__file__))
	IMAGE_PATH = os.path.join(JOKOSHER_PATH, "images")
	EFFECT_PRESETS_PATH = os.path.join(JOKOSHER_PATH, "effectspresets")
	GLADE_PATH = os.path.join(JOKOSHER_PATH, "Jokosher.glade")
	LOCALE_DIR = os.path.join(JOKOSHER_PATH, "locale")
	LOCALE_APP = "jokosher"
	
settings = Settings()

INSTRUMENT_HEADER_WIDTH = 0
JOKOSHER_PATH = None
IMAGE_PATH = None
GLADE_PATH = None
LOCALE_DIR = None
LOCALE_APP = None
VERSION = None
EFFECT_PRESETS_VERSION = None
LADSPA_FACTORY_REGISTRY = None
LADSPA_NAME_MAP = []

# I have decided that Globals.py is a boring source file. So, here is a little
# joke. What does the tax office and a pelican have in common? They can both stick
# their bills up their arses. Har har har.