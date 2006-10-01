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
import locale, gettext
import pygtk
pygtk.require("2.0")
import gobject, gtk

class Settings:

	# the different settings in each config block
	general = {"mixdownformat": "value", 
			   "recentprojects": "value", 
			   "samplerate": "value", 
			   "sampleformat": "value", 
			   "startupaction" : "value",
			   "projectfolder" : "" }
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
		for d in ['extensions', 'instruments', 'instruments/images', 
				'presets', 'presets/effects', 'presets/mixdown']:
			new_dir = os.path.join(new_jokosher_file_dir, d)
			if not os.path.isdir(new_dir): 
				try:
					os.makedirs(new_dir)
				except:
					raise "Failed to create user config directory %s" % new_dir

#a global debug function so we can easily redirect all that output
def debug(*listToPrint):
	#HACK: we can't import gst at the top of Globals.py because
	#if we do, gstreamer will get to the sys.args and print it's own
	#message instead of ours. This will be fixed once we can use
	#GOption when we depend on pygobject 2.12.
	import gst
	
	message = " ".join( [ str(x) for x in listToPrint ] )
	
	if DEBUG_STDOUT:
		print message
	if DEBUG_GST:
		gst.debug(message)	


#static list of all the instrument files (to prevent having to reimport files)
instrumentPropertyList = []
_alreadyCached = False
_cacheGeneratorObject = None

def _cacheInstrumentsGenerator(alreadyLoadedTypes=[]):
	"""
	   Yields a loaded instrument everytime this method is called
	   so that the gui isn't blocked while loading many instrument.
	   If an instrument's type is already in alreadyLoadedTypes,
	   it is considered a duplicate and not loaded.
	"""	
	try:
		#getlocale() will usually return  a tuple like: ('en_GB', 'UTF-8')
		lang = locale.getlocale()[0]
	except:
		lang = None
	for instr_path in INSTR_PATHS:
		if not os.path.exists(instr_path):
			continue
		instrFiles = [x for x in os.listdir(instr_path) if x.endswith(".instr")]
		for f in instrFiles:
			config = ConfigParser.SafeConfigParser()
			try:
				config.read(os.path.join(instr_path, f))
			except ConfigParser.MissingSectionHeaderError,e:
				debug("Instrument file %s in %s is corrupt or invalid, not loading"%(f,instr_path))
				continue	

			if config.has_option('core', 'type') and config.has_option('core', 'icon'):
				icon = config.get('core', 'icon')
				type = config.get('core', 'type')
			else:
				continue
			#don't load duplicate instruments
			if type in alreadyLoadedTypes:
				continue
		
			if lang and config.has_option('i18n', lang):
				name = config.get('i18n', lang)
			elif lang and config.has_option('i18n', lang.split("_")[0]):
				#in case lang was 'de_DE', use only 'de'
				name = config.get('i18n', lang.split("_")[0])
			elif config.has_option('i18n', 'en'):
				#fall back on english (or a PO translation, if there is any)
				name = gettext.gettext(config.get( 'i18n', 'en'))
			else:
				continue
		
			pixbufPath = os.path.join(instr_path, "images", icon)
			pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
				
			yield (name, type, pixbuf)
	
def getCachedInstruments(checkForNew=False):
	"""
	   Create the instrument cache if it hasn't been 
	   created already and return the list.
	   The instrument folders will be scanned for new_dir
	   instruments if checkForNew is True.
	"""
	global instrumentPropertyList, _alreadyCached
	if _alreadyCached and not checkForNew:
		return instrumentPropertyList
	else:
		_alreadyCached = True
	
	listOfTypes = [x[1] for x in instrumentPropertyList]
	try:
		newlyCached = list(_cacheInstrumentsGenerator(listOfTypes))
		#extend the list so we don't overwrite the already cached instruments
		instrumentPropertyList.extend(newlyCached)
	except StopIteration:
		pass

	#sort the instruments alphabetically
	#using the lowercase of the name (at index 0)
	instrumentPropertyList.sort(key=lambda x: x[0].lower())
	return instrumentPropertyList
	
def idleCacheInstruments():
	global instrumentPropertyList, _alreadyCached, _cacheGeneratorObject
	if _alreadyCached:
		#Stop idle_add from calling us again
		return False
	#create the generator if it hasnt been already
	if not _cacheGeneratorObject:
		_cacheGeneratorObject = _cacheInstrumentsGenerator()
	
	try:
		instrumentPropertyList.append(_cacheGeneratorObject.next())
		#Make sure idle add calls us again
		return True
	except StopIteration:
		_alreadyCached = True
	
	#sort the instruments alphabetically
	#using the lowercase of the name (at index 0)
	instrumentPropertyList.sort(key=lambda x: x[0].lower())
	#Stop idle_add from calling us again
	return False

#Global paths, so we can find everything
data_path = os.getenv("JOKOSHER_DATA_PATH")
if data_path:
	EFFECT_PRESETS_PATH = os.path.join(data_path, "effectspresets")
	INSTR_PATHS = (os.path.join(data_path, "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
	GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
else:
	data_path = os.path.dirname(os.path.abspath(__file__))
	EFFECT_PRESETS_PATH = os.path.join(data_path, "..", "effectspresets")
	INSTR_PATHS = (os.path.join(data_path, "..", "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
	GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
	LOCALE_PATH = os.path.join(data_path, "..", "locale")

IMAGE_PATH = os.getenv("JOKOSHER_IMAGE_PATH")
if not IMAGE_PATH:
	IMAGE_PATH = os.path.join(data_path, "..", "images")
LOCALE_PATH = os.getenv("JOKOSHER_LOCALE_PATH")
if not LOCALE_PATH:
	this_path = os.path.dirname(os.path.abspath(__file__))
	LOCALE_PATH = os.path.join(this_path, "..", "locale")
	

	
	
INSTRUMENT_HEADER_WIDTH = 0

LOCALE_APP = "jokosher"
#set in Project.py
VERSION = None
EFFECT_PRESETS_VERSION = None
LADSPA_FACTORY_REGISTRY = None
LADSPA_NAME_MAP = []
DEBUG_STDOUT, DEBUG_GST = (False, False)

_export_template = ("description", "extension", "encoder", "muxer", "requiresAudioconvert") 
_export_formats = [	("Ogg Vorbis (.ogg)", "ogg", "vorbisenc", "oggmux", True),
					("MP3 (.mp3)", "mp3", "lame", None, False),
					("Flac (.flac)", "flac", "flacenc", None, False),
					("WAV (.wav)", "wav", "wavenc", None, False),
				]
EXPORT_FORMATS = []
for type in _export_formats:
	#create a dictionary using _export_template as the keys
	#and the current item from _export_formats as the values.
	d = dict(zip(_export_template, type))
	EXPORT_FORMATS.append(d)
	
#init Settings
settings = Settings()
#cache instruments
gobject.idle_add(idleCacheInstruments)


# I have decided that Globals.py is a boring source file. So, here is a little
# joke. What does the tax office and a pelican have in common? They can both stick
# their bills up their arses. Har har har.
