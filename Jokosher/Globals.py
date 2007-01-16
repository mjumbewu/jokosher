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

import gettext
_ = gettext.gettext

class Settings:
	"""
	Handles loading/saving settings from/to a file on disk.
	"""

	# the different settings in each config block
	general = 	{
				"mixdownformat": "value", 
				"recentprojects": "value", 
				"startupaction" : "value",
				"projectfolder" : ""
				}
	
	recording = {
				"fileformat": "vorbisenc ! oggmux",
				"samplerate": "44100"
				}
	
	playback = 	{
				"device": "default",
				"devicecardnum": "value",
				"audiosink":"autoaudiosink"
				}
	
	extensions = {
				 "extensions_blacklist": ""
				 }
	
	#_____________________________________________________________________
	
	def __init__(self, filename = None):
		"""
		Creates a new instance of Settings.
		
		Parameters:
			filename -- path to the settings file.
						If None, the default ~/.jokosher/config will be used.
		"""
		if not filename:
			self.filename = os.path.expanduser("~/.jokosher/config")
		else:
			self.filename = filename
		self.config = ConfigParser.ConfigParser()

		self.read()

	#_____________________________________________________________________

	def read(self):
		"""
		Reads configuration settings from the config file and loads
		then into the Settings dictionaries.
		"""
		self.config.read(self.filename)
	
		if not self.config.has_section("General"):
			self.config.add_section("General")
		if not self.config.has_section("Recording"):
			self.config.add_section("Recording")
		if not self.config.has_section("Playback"):
			self.config.add_section("Playback")
		if not self.config.has_section("Extensions"):
			self.config.add_section("Extensions")
	
		for key, value in self.config.items("General"):
			self.general[key] = value
		for key, value in self.config.items("Recording"):
			self.recording[key] = value
		for key, value in self.config.items("Playback"):
			self.playback[key] = value
		for key, value in self.config.items("Extensions"):
			self.extensions[key] = value
	
	#_____________________________________________________________________
		
	def write(self):
		"""
		Writes configuration settings to the Settings config file.
		"""		
		for key in self.general:
			self.config.set("General", key, self.general[key])
		for key in self.recording:
			self.config.set("Recording", key, self.recording[key])
		for key in self.playback:
			self.config.set("Playback", key, self.playback[key])
		for key in self.extensions:
			self.config.set("Extensions", key, self.extensions[key])
			
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
		
		#_____________________________________________________________________
		
def debug(*listToPrint):
	"""
	Global debug function to redirect all the debugging output from the other
	methods.
	
	Parameters:
		*listToPrint -- list of elements to append to the debugging output.
	"""
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
		
#_____________________________________________________________________
		
def PrintPipelineDebug(message, pipeline):
	"""
	Prints debugging information for the GStreamer pipeline.
	
	Parameters:
		message -- GStreamer message to be printed as debugging output.
		pipeline -- the currently active Project's main pipeline.
	"""
	try:
		if os.environ['JOKOSHER_DEBUG']:
			import JokDebug
			jokDebug = JokDebug.JokDebug()
			debug(message)
			jokDebug.ShowPipelineTree(pipeline)
	except:
		pass

#_____________________________________________________________________

#static list of all the Instrument files (to prevent having to reimport files).
instrumentPropertyList = []
_alreadyCached = False
_cacheGeneratorObject = None

def _cacheInstrumentsGenerator(alreadyLoadedTypes=[]):
	"""
	Yields a loaded Instrument everytime this method is called,
	so that the gui isn't blocked while loading many Instruments.
	If an Instrument's type is already in alreadyLoadedTypes,
	it is considered a duplicate and it's not loaded.
	
	Parameters:
		alreadyLoadedTypes -- array containing the already loaded Instrument types.
		
	Returns:
		the loaded Instrument. *CHECK*
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
			name = unicode(name, "UTF-8")
			pixbufPath = os.path.join(instr_path, "images", icon)
			pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
				
			yield (name, type, pixbuf)

#_____________________________________________________________________

def getCachedInstruments(checkForNew=False):
	"""
	Creates the Instrument cache if it hasn't been created already and
	return it.
	
	Parameters:
		checkForNew --	True = scan the Instrument folders for new_dir.
						False = don't scan for new Instruments.
						
	Returns:
		a list with the Instruments cached in memory.
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

#_____________________________________________________________________

def idleCacheInstruments():
	"""
	Loads the Instruments 'lazily' to avoid blocking the GUI.
	
	Returns:
		True -- keep calling itself to load more Instruments.
		False -- stop calling itself and sort Instruments alphabetically.
	"""
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

#_____________________________________________________________________
	
def PopulateEncoders():
	"""
	Check if the hardcoded list of encoders is available on the system.
	"""
	#HACK: we can't import gst at the top of Globals.py because
	#if we do, gstreamer will get to the sys.args and print it's own
	#message instead of ours. This will be fixed once we can use
	#GOption when we depend on pygobject 2.12.
	import gst
	
	for type in _export_formats:
		for element in type[2].split("!"):
			exists = gst.default_registry_check_feature_version(element.strip(), 0, 10, 0)
			if not exists:
				debug('Cannot find "%s" plugin, disabling encoder: "%s"' % (element.strip(), type[2]))
				# we know at least one of the elements doesnt exist, so skip this encode format.
				continue
				
		#create a dictionary using _export_template as the keys
		#and the current item from _export_formats as the values.
		d = dict(zip(_export_template, type))
		EXPORT_FORMATS.append(d)

#_____________________________________________________________________

"""
Used for launching the correct help file:
	True -- Jokosher's running locally by the user. Use the help file from
			the help subdirectory.
	False -- Jokosher has been installed system-wide. Use yelp's automatic
			help file selection.
"""
USE_LOCAL_HELP = False

"""
Global paths, so all methods can access them.
If JOKOSHER_DATA_PATH is not set, that is, Jokosher is running locally,
use paths relative to the current running directory instead of /usr ones.
"""
data_path = os.getenv("JOKOSHER_DATA_PATH")
if data_path:
	INSTR_PATHS = (os.path.join(data_path, "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
	EXTENSION_PATHS = (os.path.join(data_path, "extensions"), os.path.expanduser("~/.jokosher/extensions/"))
	GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
else:
	data_path = os.path.dirname(os.path.abspath(__file__))
	INSTR_PATHS = (os.path.join(data_path, "..", "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
	EXTENSION_PATHS = (os.path.join(data_path, "..", "extensions"), os.path.expanduser("~/.jokosher/extensions/"))
	GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
	LOCALE_PATH = os.path.join(data_path, "..", "locale")

# create a couple dirs to avoid having problems creating a non-existing
# directory inside another non-existing directory
for directory in ['extensions', 'instruments', 'instruments/images', 
		'presets', 'presets/effects', 'presets/mixdown']:
	new_dir = os.path.join(os.path.expanduser("~/.jokosher/"), directory)
	if not os.path.isdir(new_dir): 
		try:
			os.makedirs(new_dir)
		except:
			raise "Failed to create user config directory %s" % new_dir

#TODO: make this a list with the system path and home directory path
EFFECT_PRESETS_PATH = os.path.expanduser("~/.jokosher/presets/effects")

IMAGE_PATH = os.getenv("JOKOSHER_IMAGE_PATH")
if not IMAGE_PATH:
	IMAGE_PATH = os.path.join(data_path, "..", "images")

LOCALE_PATH = os.getenv("JOKOSHER_LOCALE_PATH")
if not LOCALE_PATH:
	LOCALE_PATH = os.path.join(data_path, "..", "locale")

HELP_PATH = os.getenv("JOKOSHER_HELP_PATH")
if not HELP_PATH:
	USE_LOCAL_HELP = True
	#TODO: replace C with the correct locale
	current_locale = "C"
	HELP_PATH = os.path.join(data_path, "..", "help/jokosher",
							current_locale, "jokosher.xml")

# add your own extension dirs with envar JOKOSHER_EXTENSION_DIRS, colon-separated
__extra_ext_dirs = os.environ.get('JOKOSHER_EXTENSION_DIRS','')
if __extra_ext_dirs:
	EXTENSION_PATHS = __extra_ext_dirs.split(':') + list(EXTENSION_PATHS)

""" ExtensionManager data """
AVAILABLE_EXTENSIONS = []
INSTRUMENT_HEADER_WIDTH = 0

""" Locale constant """
LOCALE_APP = "jokosher"

""" Set in Project.py """
VERSION = None
EFFECT_PRESETS_VERSION = None
LADSPA_FACTORY_REGISTRY = None
LADSPA_NAME_MAP = []
							#TODO: FIX THE ICONS
LADPSA_CATEGORIES_LIST = [
						("Broken", "effect_unclassified.png"),		#0 - this image is never used
						(_("Unclassified"), "effect_unclassified.png"),	#1
						(_("Delays"), "effect_delays.png"),				#2
						(_("Equalizers"), "effect_equalizers.png"),		#3
						(_("Modulators"), "effect_modulators.png"),		#4
						(_("Filters"), "effect_filters.png"),				#5
						(_("Distortion"), "effect_distortion.png"),		#6
						(_("Simulators"), "effect_simulators.png"),		#7
						(_("Miscellaneous"), "effect_miscellaneous.png"),	#8
						(_("Chorus"), "effect_chorus.png"),				#9
						(_("Phasers"), "effect_phasers.png"),				#10
						(_("Flangers"), "effect_flangers.png"),			#11
						(_("Oscillators"), "effect_oscillators.png"),		#12
						(_("Compressors"), "effect_compressors.png"),		#13
						(_("Amplifiers"), "effect_amplifiers.png")			#14
						]
LADSPA_CATEGORIES_DICT = {
						"ladspa-SweepVFII" : 4,
						"ladspa-SweepVFI" : 4,
						"ladspa-PhaserII" : 10,
						"ladspa-PhaserI" : 10,
						"ladspa-ChorusII" : 9,
						"ladspa-ChorusI" : 9,
						"ladspa-Clip" : 14,
						"ladspa-CabinetII" : 7,
						"ladspa-CabinetI" : 7,
						"ladspa-AmpV" : 7,
						"ladspa-AmpIV" : 7,
						"ladspa-AmpIII" : 7,
						"ladspa-PreampIV" : 7,
						"ladspa-PreampIII" : 7,
						"ladspa-Compress" : 13,
						"ladspa-Eq" : 3,
						"ladspa-ssm-masher" : 0, #no sound
						"ladspa-slew-limiter-rc" : 0, #no sound
						"ladspa-slide-tc" : 0, #chirps then dies
						"ladspa-signal-abs-cr" : 4,
						"ladspa-vcf-hshelf" : 0, #erratic behavior.
						"ladspa-vcf-lshelf" : 0, #erratic behavior
						"ladspa-vcf-peakeq" : 5,
						"ladspa-vcf-notch" : 5,
						"ladspa-vcf-bp2" : 5,
						"ladspa-vcf-bp1" : 0, #no sound
						"ladspa-vcf-hp" : 5,
						"ladspa-vcf-lp" : 5,
						"ladspa-vcf-reslp" : 5,
						"ladspa-range-trans-cr" : 14, #works, but the settings are impossible to use properly
						"ladspa-hz-voct-ar" : 0, #no sound
						"ladspa-Phaser1+LFO" : 10,
						"ladspa-Chorus2" : 9, #so so
						"ladspa-Chorus1" : 9, # so so
						"ladspa-tap-vibrato" : 4,
						"ladspa-tap-tubewarmth" : 5,
						"ladspa-tap-tremolo" : 4,
						"ladspa-tap-sigmoid" : 14,
						"ladspa-tap-reflector" : 4,
						"ladspa-tap-pitch" : 4,
						"ladspa-tap-pinknoise" : 8,
						"ladspa-tap-limiter" : 14,
						"ladspa-tap-equalizer-bw" : 3,
						"ladspa-tap-equalizer" : 3,
						"ladspa-formant-vc" : 4,
						"ladspa-tap-deesser" : 5,
						"ladspa-tap-dynamics-m" : 5, #could be in another category
						"ladspa-imp" : 5,
						"ladspa-pitchScaleHQ" : 4, #crap
						"ladspa-mbeq" : 3,
						"ladspa-sc4m" : 5, #could be in another category
						"ladspa-artificialLatency" : 8,
						"ladspa-pitchScale" : 4, #crap
						"ladspa-pointerCastDistortion" : 6, #crap
						"ladspa-const" : 6, #could be in another category
						"ladspa-lsFilter" : 5,
						"ladspa-revdelay" : 2,
						"ladspa-delay-c" : 0, #erratic behavior
						"ladspa-delay-l" : 0, #no change in sound?
						"ladspa-delay-n" : 0, #no change in sound?
						"ladspa-decay" : 6, #controls make it unusable
						"ladspa-comb-c" : 0, #erratic behavior
						"ladspa-comb-l" : 0, #no change in sound?
						"ladspa-comb-n" : 0, #no change in sound and static
						"ladspa-allpass-c" : 0, #no change in sound?
						"ladspa-allpass-l" : 0, #no change in sound?
						"ladspa-allpass-n" : 0, #no change in sound?
						"ladspa-butthigh-iir" : 5,
						"ladspa-buttlow-iir" : 5,
						"ladspa-dj-eq-mono" : 3,
						"ladspa-notch-iir" : 5,
						"ladspa-lowpass-iir" : 5,
						"ladspa-highpass-iir" : 5,
						"ladspa-bandpass-iir" : 5,
						"ladspa-bandpass-a-iir" : 5,
						"ladspa-gongBeater" : 4, #crap
						"ladspa-djFlanger" : 11,
						"ladspa-giantFlange" : 11,
						"ladspa-amPitchshift" : 4,
						"ladspa-chebstortion" : 6, #weak
						"ladspa-inv" : 0, #no change in sound, no options either
						"ladspa-zm1" : 0, #no change in sound, no options either
						"ladspa-sc1" : 13, #could be in another category
						"ladspa-gong" : 5,
						"ladspa-freqTracker" : 0, #no sound
						"ladspa-rateShifter" : 5,
						"ladspa-fmOsc" : 0, #erratic behavior
						"ladspa-smoothDecimate" : 5,
						"ladspa-hardLimiter" : 14,
						"ladspa-gate" : 5, #could be in another category
						"ladspa-satanMaximiser" : 6,
						"ladspa-alias" : 5, #could be in another category
						"ladspa-valveRect" : 5,
						"ladspa-crossoverDist" : 6, #crap
						"ladspa-dysonCompress" : 13,
						"ladspa-delayorama" : 2,
						"ladspa-autoPhaser" : 10,
						"ladspa-fourByFourPole" : 5,
						"ladspa-lfoPhaser" : 10,
						"ladspa-gsm" : 4,
						"ladspa-svf" : 5,
						"ladspa-foldover" : 6,
						"ladspa-harmonicGen" : 4, #crap
						"ladspa-sifter" : 4, #sounds like Distortion
						"ladspa-valve" : 6, #weak
						"ladspa-tapeDelay" : 2,
						"ladspa-dcRemove" : 0, #no change in sound, no options either
						"ladspa-fadDelay" : 2, #psychedelic stuff
						"ladspa-transient" : 4,
						"ladspa-triplePara" : 5,
						"ladspa-singlePara" : 5,
						"ladspa-retroFlange" : 11,
						"ladspa-flanger" : 11,
						"ladspa-decimator" : 5,
						"ladspa-hermesFilter" : 5, #control needs to have 2 columns, doesn't fit screen
						"ladspa-multivoiceChorus" : 9,
						"ladspa-foverdrive" : 6,
						"ladspa-declip" : 5, #couldn't properly test it since I had to clipping audio
						"ladspa-comb" : 5,
						"ladspa-ringmod-1i1o1l" : 4,
						"ladspa-shaper" : 5,
						"ladspa-divider" : 5,
						"ladspa-diode" : 6,
						"ladspa-amp" : 14,
						"ladspa-Parametric1" : 5,
						"ladspa-wshape-sine" : 0, #controls make it unusable
						"ladspa-vcf303" : 5,
						"ladspa-limit-rms" : 0, #controls make it unusable
						"ladspa-limit-peak" : 0, #controls make it unusable
						"ladspa-expand-rms" : 0, #controls make it unusable
						"ladspa-expand-peak" : 0, #controls make it unusable
						"ladspa-compress-rms" : 0, #controls make it unusable
						"ladspa-compress-peak" : 0, #controls make it unusable
						"ladspa-identity-audio" : 0, #no change in sound?
						"ladspa-hard-gate" : 5,
						"ladspa-grain-scatter" : 0, #no sound
						"ladspa-fbdelay-60s" : 2,
						"ladspa-fbdelay-5s" : 2,
						"ladspa-fbdelay-1s" : 2,
						"ladspa-fbdelay-0-1s" : 2,
						"ladspa-fbdelay-0-01s" : 2,
						"ladspa-delay-60s" : 2,
						"ladspa-delay-1s" : 2,
						"ladspa-delay-0-1s" : 2,
						"ladspa-delay-0-01s" : 2,
						"ladspa-disintegrator" : 5, #crap
						"ladspa-triangle-fcsa-oa" : 12,
						"ladspa-triangle-fasc-oa" : 0, #no sound
						"ladspa-syncsquare-fcga-oa" : 12,
						"ladspa-syncpulse-fcpcga-oa" : 12,
						"ladspa-sum-iaic-oa" : 0, #controls make it unusable
						"ladspa-square-fa-oa" : 12,
						"ladspa-sinusWavewrapper" : 5,
						"ladspa-ratio-ncda-oa" : 6,
						"ladspa-ratio-nadc-oa" : 0, #no sound
						"ladspa-random-fcsa-oa" : 12, #we GOTTA call this Atari or Arcade. It's the same sound!
						"ladspa-random-fasc-oa" : 0, #no sound
						"ladspa-sawtooth-fa-oa" : 12,
						"ladspa-pulse-fcpa-oa" : 12,
						"ladspa-pulse-fapc-oa" : 12,
						"ladspa-product-iaic-oa" : 12,
						"ladspa-lp4pole-fcrcia-oa" : 12, #controls suck
						"ladspa-fmod-fcma-oa" : 5,
						"ladspa-fmod-famc-oa" : 0, #controls make it unusable
						"ladspa-amp-gcia-oa" : 0, #controls make it unusable
						"ladspa-difference-icma-oa" : 14,
						"ladspa-difference-iamc-oa" : 0, #no sound
						"ladspa-sine-fcaa" : 12,
						"ladspa-sine-faac" : 0, #no sound
						"ladspa-hpf" : 5,
						"ladspa-lpf" : 5,
						"ladspa-adsr" : 0, #controls make it unusable, no sound
						"ladspa-amp-mono" : 0, #controls make it unusable
						"ladspa-delay-5s" : 2
						}
DEBUG_STDOUT, DEBUG_GST = (False, False)

_export_template = ("description", "extension", "pipeline") 
_export_formats = 	[
					("Ogg Vorbis", "ogg", "vorbisenc ! oggmux"),
					("MP3", "mp3", "lame"),
					("Flac", "flac", "flacenc"),
					("WAV", "wav", "wavenc"),
					]

EXPORT_FORMATS = []

SAMPLE_RATES = [8000, 11025, 22050, 32000, 44100, 48000, 96000, 192000]
	
""" init Settings """
settings = Settings()

""" Cache Instruments """
gobject.idle_add(idleCacheInstruments)

# I have decided that Globals.py is a boring source file. So, here is a little
# joke. What does the tax office and a pelican have in common? They can both stick
# their bills up their arses. Har har har.
