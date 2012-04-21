#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Globals.py
#	
#	This module contains variable definitions that can be used across the code
#	base and also includes methods for reading and writing these settings to
#	the Jokosher configuration in JOKOSHER_CONFIG_HOME/config.
#
#-------------------------------------------------------------------------------

import ConfigParser
import os, errno
import locale, gettext
import pygtk
pygtk.require("2.0")
import gobject, gtk
import xdg.BaseDirectory
import shutil
import PlatformUtils

import gettext
_ = gettext.gettext

class Settings:
	"""
	Handles loading/saving settings from/to a file on disk.
	"""

	# the different settings in each config block
	general = 	{
				# increment each time there is an incompatible change with the config file
				"version" : "1",
				"recentprojects": "", #deprecated
				"startupaction" : "value",
				"projectfolder" : "",
				"windowheight" : 550,
				"windowwidth" : 900,
				"addinstrumentwindowheight" : 350,
				"addinstrumentwindowwidth" : 300,
				"instrumenteffectwindowheight" : 450,				
				"instrumenteffectwindowwidth" : 650,
				
				}

	recording = {
				"fileformat": "vorbisenc bitrate=%(bitrate)d ! oggmux",
				"file_extension": "ogg",
				"samplerate": "0", # zero means, autodetect sample rate (ie use any available)
				"bitrate": "131072",
				"audiosrc" : "gconfaudiosrc",
				"device" : "default"
				}
	# Overwrite with platform specific settings
	recording.update( PlatformUtils.GetRecordingDefaults() )
	
	playback = 	{
				"devicename": "default",
				"device": "default",
				"audiosink":"autoaudiosink"
				}
	# Overwrite with platform specific settings
	playback.update( PlatformUtils.GetPlaybackDefaults() )

	extensions = {
				 "extensions_blacklist": ""
				 }
				 
	recentprojects = {
			#FIXME: replace with some kind of proper database since 
			# we now plan to store all the projects created ever 
			# (not just the last 8 used)
			"paths": "",
			"names": "",
			"create_times": "",
			"last_used_times": "",
	
			}
	
	sections = {
				"General" : general,
				"Recording" : recording,
				"Playback" : playback,
				"Extensions" : extensions,
				"RecentProjects" : recentprojects,
				}
				
	

	#_____________________________________________________________________
	
	def __init__(self):
		self.filename = os.path.join(JOKOSHER_CONFIG_HOME, "config")
		# Use RawConfigParser so that parameters in pipelines don't get processed
		self.config = ConfigParser.RawConfigParser()
		self.read()

	#_____________________________________________________________________

	def read(self):
		"""
		Reads configuration settings from the config file and loads
		then into the Settings dictionaries.
		"""
		self.config.read(self.filename)
	
		for section in self.sections:
			if not self.config.has_section(section):
				self.config.add_section(section)
	
		for section, section_dict in self.sections.iteritems():
			for key, value in self.config.items(section):
				if value == "None":
					value = None
				section_dict[key] = value
	
	#_____________________________________________________________________
		
	def write(self):
		"""
		Writes configuration settings to the Settings config file.
		"""

		for section, section_dict in self.sections.iteritems():
			for key, value in section_dict.iteritems():
				self.config.set(section, key, value)
		
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
		print(message)
	if DEBUG_GST:
		gst.debug(message)
		
#_____________________________________________________________________

def FAT32SafeFilename(filename):
	"""
	Returns a copy fo the given string that has all the
	characters that are not allowed in FAT32 path names
	taken out.
	
	Parameters:
		filename -- the filename string.
	"""
	
	allowedChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$%'`-@{}~!#()&_^ "
	return "".join([x for x in filename if x in allowedChars])

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
				name = _(config.get( 'i18n', 'en'))
			else:
				continue
			name = unicode(name, "UTF-8")
			pixbufPath = os.path.join(instr_path, "images", icon)
			pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
			
			# add instrument to defaults list if it's a defaults
			if instr_path == INSTR_PATHS[0]:
				DEFAULT_INSTRUMENTS.append(type)
				
			yield (name, type, pixbuf, pixbufPath)

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

def getCachedInstrumentPixbuf(get_type):
	for (name, type, pixbuf, pixbufPath) in getCachedInstruments():
		if type == get_type:
			return pixbuf
	return None

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
	for type in _export_formats:
		if VerifyAllElements(type[2]):
			#create a dictionary using _export_template as the keys
			#and the current item from _export_formats as the values.
			d = dict(zip(_export_template, type))
			EXPORT_FORMATS.append(d)

#_____________________________________________________________________

def VerifyAllElements(bin_desc):
	#HACK: we can't import gst at the top of Globals.py because
	#if we do, gstreamer will get to the sys.args and print it's own
	#message instead of ours. This will be fixed once we can use
	#GOption when we depend on pygobject 2.12.
	import gst
	
	all_elements_exist = True
	for element in bin_desc.split("!"):
		element = element.strip().split(" ")[0] # Disregard any options
		exists = gst.default_registry_check_feature_version(element.strip(), 0, 10, 0)
		if not exists:
			all_elements_exist = False
			debug('Cannot find "%s" plugin, disabling: "%s"' % (element.strip(), bin_desc))
			# we know at least one of the elements doesnt exist, so skip this encode format.
			break
	
	return all_elements_exist
	
#_____________________________________________________________________

def PopulateAudioBackends():
	CheckBackendList(PLAYBACK_BACKENDS)
	CheckBackendList(CAPTURE_BACKENDS)
	
#_____________________________________________________________________
	
def CheckBackendList(backend_list):
	remove_list = []
	for tuple_ in backend_list:
		bin_desc = tuple_[1]
		if not VerifyAllElements(bin_desc):
			remove_list.append(tuple_)
	
	for tuple_ in remove_list:
		backend_list.remove(tuple_)

#_____________________________________________________________________

def CopyAllFiles(src_dir, dest_dir, only_these_files=None):
	""" Copies all the files, but only the files from one directory to another."""
	for file in os.listdir(src_dir):
		if only_these_files is not None and file not in only_these_files:
			continue
		
		src_path = os.path.join(src_dir, file)
		dest_path = os.path.join(dest_dir, file)
		if os.path.isfile(src_path):
			try:
				shutil.copy2(src_path, dest_path)
			except IOError:
				print "Unable to copy from old ~/.jokosher directory:", src_path

#_____________________________________________________________________

def LoadGtkBuilderFilename(filename):
	builder = gtk.Builder()
	builder.add_from_file(os.path.join(GTK_BUILDER_PATH, filename))
	return builder

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

XDG_RESOURCE_NAME = "jokosher"
JOKOSHER_CONFIG_HOME = xdg.BaseDirectory.save_config_path(XDG_RESOURCE_NAME)
JOKOSHER_DATA_HOME =   xdg.BaseDirectory.save_data_path(XDG_RESOURCE_NAME)

data_path = os.getenv("JOKOSHER_DATA_PATH")
if data_path:
	INSTR_PATHS = (os.path.join(data_path, "Instruments"), os.path.join(JOKOSHER_DATA_HOME, "instruments"))
	EXTENSION_PATHS = (os.path.join(data_path, "extensions"), os.path.join(JOKOSHER_DATA_HOME, "extensions"))
	GTK_BUILDER_PATH = os.path.join(data_path, "gtk-builder-ui")
else:
	data_path = os.path.dirname(os.path.abspath(__file__))
	INSTR_PATHS = (os.path.join(data_path, "..", "Instruments"), os.path.join(JOKOSHER_DATA_HOME, "instruments"))
	EXTENSION_PATHS = (os.path.join(data_path, "..", "extensions"), os.path.join(JOKOSHER_DATA_HOME, "extensions"))
	GTK_BUILDER_PATH = os.path.join(data_path, "..", "gtk-builder-ui")
	LOCALE_PATH = os.path.join(data_path, "..", "locale")

# create a couple dirs to avoid having problems creating a non-existing
# directory inside another non-existing directory
create_dirs = [
	'extensions',
	'instruments',
	('instruments', 'images'),
	'presets',
	('presets', 'effects'),
	('presets', 'mixdown'),
	'mixdownprofiles',
	'projects',
]

# do a listing before we create the dirs so we know if it was empty (ie first run)
jokosher_dir_empty = (len(os.listdir(JOKOSHER_DATA_HOME)) == 0)
_HOME_DOT_JOKOSHER = os.path.expanduser("~/.jokosher")

if jokosher_dir_empty and os.path.isdir(_HOME_DOT_JOKOSHER):
	# Copying old config file from ~/.jokosher.
	CopyAllFiles(_HOME_DOT_JOKOSHER, JOKOSHER_CONFIG_HOME, ["config"])

for dirs in create_dirs:
	if isinstance(dirs, str):
		new_dir = os.path.join(JOKOSHER_DATA_HOME, dirs)
		old_dir = os.path.join(_HOME_DOT_JOKOSHER, dirs)
	else:
		new_dir = os.path.join(JOKOSHER_DATA_HOME, *dirs)
		old_dir = os.path.join(_HOME_DOT_JOKOSHER, *dirs)
		
	try:
		os.makedirs(new_dir)
	except OSError, e:
		if e.errno != errno.EEXIST:
			raise
	except:
		raise Exception("Failed to create user config directory %s" % new_dir)
	
	if jokosher_dir_empty and os.path.isdir(old_dir) and os.path.isdir(new_dir):
		CopyAllFiles(old_dir, new_dir)
			

#TODO: make this a list with the system path and home directory path
EFFECT_PRESETS_PATH = os.path.join(JOKOSHER_DATA_HOME, "presets", "effects")
MIXDOWN_PROFILES_PATH = os.path.join(JOKOSHER_DATA_HOME, "mixdownprofiles")
PROJECTS_PATH = os.path.join(JOKOSHER_DATA_HOME, "projects")

IMAGE_PATH = os.getenv("JOKOSHER_IMAGE_PATH")
if not IMAGE_PATH:
	IMAGE_PATH = os.path.join(data_path, "..", "images")

LOCALE_PATH = os.getenv("JOKOSHER_LOCALE_PATH")
if not LOCALE_PATH:
	LOCALE_PATH = os.path.join(data_path, "..", "locale")

HELP_PATH = os.getenv("JOKOSHER_HELP_PATH")
if not HELP_PATH:
	USE_LOCAL_HELP = True
	
	# change the local help file to match the current locale
	current_locale = "C"
	if locale.getlocale()[0] and not locale.getlocale()[0].startswith("en", 0, 2):
		current_locale = locale.getlocale()[0][:2]
		
	HELP_PATH = os.path.join(data_path, "..", "help/jokosher",
							 current_locale, "jokosher.xml")
	
	# use C (en) as the default help fallback
	if not os.path.exists(HELP_PATH):
		HELP_PATH = os.path.join(data_path, "..", "help/jokosher/C/jokosher.xml")

# add your own extension dirs with envar JOKOSHER_EXTENSION_DIRS, colon-separated
__extra_ext_dirs = os.environ.get('JOKOSHER_EXTENSION_DIRS','')
if __extra_ext_dirs:
	EXTENSION_PATHS = __extra_ext_dirs.split(':') + list(EXTENSION_PATHS)

""" ExtensionManager data """
AVAILABLE_EXTENSIONS = []

""" Locale constant """
LOCALE_APP = "jokosher"

""" Categories enum """
class Categories:
	(broken, unclassified, amplifiers, chorus, compressors,
	delays, distortions, equalizers, filters, flangers,
	miscellaneous, modulators, oscillators, phasers, reverbs,
	simulators) = range(16)

""" Set in Project.py """
VERSION = None
EFFECT_PRESETS_VERSION = None
LADSPA_FACTORY_REGISTRY = None
LADSPA_NAME_MAP = []
LADPSA_CATEGORIES_LIST = [
						(_("Broken"), "effect_broken.png"),
						(_("Unclassified"), "effect_unclassified.png"),
						(_("Amplifiers"), "effect_amplifiers.png"),
						(_("Chorus"), "effect_chorus.png"),
						(_("Compressors"), "effect_compressors.png"),
						(_("Delays"), "effect_delays.png"),
						(_("Distortions"), "effect_distortion.png"),
						(_("Equalizers"), "effect_equalizers.png"),
						(_("Filters"), "effect_filters.png"),
						(_("Flangers"), "effect_flangers.png"),
						(_("Miscellaneous"), "effect_miscellaneous.png"),
						(_("Modulators"), "effect_modulators.png"),
						(_("Oscillators"), "effect_oscillators.png"),
						(_("Phasers"), "effect_phasers.png"),
						(_("Reverbs"), "effect_reverbs.png"),
						(_("Simulators"), "effect_simulators.png")
						]
LADSPA_CATEGORIES_DICT = {
						"ladspa-SweepVFII" : Categories.modulators,
						"ladspa-SweepVFI" : Categories.modulators,
						"ladspa-PhaserII" : Categories.phasers,
						"ladspa-PhaserI" : Categories.phasers,
						"ladspa-ChorusII" : Categories.chorus,
						"ladspa-ChorusI" : Categories.chorus,
						"ladspa-Clip" : Categories.amplifiers,
						"ladspa-CabinetII" : Categories.simulators,
						"ladspa-CabinetI" : Categories.simulators,
						"ladspa-AmpV" : Categories.simulators,
						"ladspa-AmpIV" : Categories.simulators,
						"ladspa-AmpIII" : Categories.simulators,
						"ladspa-PreampIV" : Categories.simulators,
						"ladspa-PreampIII" : Categories.simulators,
						"ladspa-Compress" : Categories.compressors,
						"ladspa-Eq" : Categories.equalizers,
						"ladspa-ssm-masher" : Categories.broken, #no sound
						"ladspa-slew-limiter-rc" : Categories.broken, #no sound
						"ladspa-slide-tc" : Categories.broken, #chirps then dies
						"ladspa-signal-abs-cr" : Categories.modulators,
						"ladspa-vcf-hshelf" : Categories.broken, #erratic behavior.
						"ladspa-vcf-lshelf" : Categories.broken, #erratic behavior
						"ladspa-vcf-peakeq" : Categories.filters,
						"ladspa-vcf-notch" : Categories.filters,
						"ladspa-vcf-bp2" : Categories.filters,
						"ladspa-vcf-bp1" : Categories.broken, #no sound
						"ladspa-vcf-hp" : Categories.filters,
						"ladspa-vcf-lp" : Categories.filters,
						"ladspa-vcf-reslp" : Categories.filters,
						"ladspa-range-trans-cr" : Categories.amplifiers, #works, but the settings are impossible to use properly
						"ladspa-hz-voct-ar" : Categories.broken, #no sound
						"ladspa-Phaser1+LFO" : Categories.phasers,
						"ladspa-Chorus2" : Categories.chorus, #so so
						"ladspa-Chorus1" : Categories.chorus, # so so
						"ladspa-tap-vibrato" : Categories.modulators,
						"ladspa-tap-tubewarmth" : Categories.filters,
						"ladspa-tap-tremolo" : Categories.modulators,
						"ladspa-tap-sigmoid" : Categories.amplifiers,
						"ladspa-tap-reflector" : Categories.modulators,
						"ladspa-tap-pitch" : Categories.modulators,
						"ladspa-tap-pinknoise" : Categories.miscellaneous,
						"ladspa-tap-limiter" : Categories.amplifiers,
						"ladspa-tap-equalizer-bw" : Categories.equalizers,
						"ladspa-tap-equalizer" : Categories.equalizers,
						"ladspa-formant-vc" : Categories.modulators,
						"ladspa-tap-deesser" : Categories.filters,
						"ladspa-tap-dynamics-m" : Categories.filters, #could be in another category
						"ladspa-imp" : Categories.filters,
						"ladspa-pitchScaleHQ" : Categories.modulators, #crap
						"ladspa-mbeq" : Categories.equalizers,
						"ladspa-sc4m" : Categories.filters, #could be in another category
						"ladspa-artificialLatency" : Categories.miscellaneous,
						"ladspa-pitchScale" : Categories.modulators, #crap
						"ladspa-pointerCastDistortion" : Categories.distortions, #crap
						"ladspa-const" : Categories.distortions, #could be in another category
						"ladspa-lsFilter" : Categories.filters,
						"ladspa-revdelay" : Categories.delays,
						"ladspa-delay-c" : Categories.broken, #erratic behavior
						"ladspa-delay-l" : Categories.broken, #no change in sound?
						"ladspa-delay-n" : Categories.broken, #no change in sound?
						"ladspa-decay" : Categories.distortions, #controls make it unusable
						"ladspa-comb-c" : Categories.broken, #erratic behavior
						"ladspa-comb-l" : Categories.broken, #no change in sound?
						"ladspa-comb-n" : Categories.broken, #no change in sound and static
						"ladspa-allpass-c" : Categories.broken, #no change in sound?
						"ladspa-allpass-l" : Categories.broken, #no change in sound?
						"ladspa-allpass-n" : Categories.broken, #no change in sound?
						"ladspa-butthigh-iir" : Categories.filters,
						"ladspa-buttlow-iir" : Categories.filters,
						"ladspa-dj-eq-mono" : Categories.equalizers,
						"ladspa-notch-iir" : Categories.filters,
						"ladspa-lowpass-iir" : Categories.filters,
						"ladspa-highpass-iir" : Categories.filters,
						"ladspa-bandpass-iir" : Categories.filters,
						"ladspa-bandpass-a-iir" : Categories.filters,
						"ladspa-gongBeater" : Categories.modulators, #crap
						"ladspa-djFlanger" : Categories.flangers,
						"ladspa-giantFlange" : Categories.flangers,
						"ladspa-amPitchshift" : Categories.modulators,
						"ladspa-chebstortion" : Categories.distortions, #weak
						"ladspa-inv" : Categories.broken, #no change in sound, no options either
						"ladspa-zm1" : Categories.broken, #no change in sound, no options either
						"ladspa-sc1" : Categories.compressors, #could be in another category
						"ladspa-gong" : Categories.filters,
						"ladspa-freqTracker" : Categories.broken, #no sound
						"ladspa-rateShifter" : Categories.filters,
						"ladspa-fmOsc" : Categories.broken, #erratic behavior
						"ladspa-smoothDecimate" : Categories.filters,
						"ladspa-hardLimiter" : Categories.amplifiers,
						"ladspa-gate" : Categories.filters, #could be in another category
						"ladspa-satanMaximiser" : Categories.distortions,
						"ladspa-alias" : Categories.filters, #could be in another category
						"ladspa-valveRect" : Categories.filters,
						"ladspa-crossoverDist" : Categories.distortions, #crap
						"ladspa-dysonCompress" : Categories.compressors,
						"ladspa-delayorama" : Categories.delays,
						"ladspa-autoPhaser" : Categories.phasers,
						"ladspa-fourByFourPole" : Categories.filters,
						"ladspa-lfoPhaser" : Categories.phasers,
						"ladspa-gsm" : Categories.modulators,
						"ladspa-svf" : Categories.filters,
						"ladspa-foldover" : Categories.distortions,
						"ladspa-harmonicGen" : Categories.modulators, #crap
						"ladspa-sifter" : Categories.modulators, #sounds like Distortion
						"ladspa-valve" : Categories.distortions, #weak
						"ladspa-tapeDelay" : Categories.delays,
						"ladspa-dcRemove" : Categories.broken, #no change in sound, no options either
						"ladspa-fadDelay" : Categories.delays, #psychedelic stuff
						"ladspa-transient" : Categories.modulators,
						"ladspa-triplePara" : Categories.filters,
						"ladspa-singlePara" : Categories.filters,
						"ladspa-retroFlange" : Categories.flangers,
						"ladspa-flanger" : Categories.flangers,
						"ladspa-decimator" : Categories.filters,
						"ladspa-hermesFilter" : Categories.filters, #control needs to have 2 columns, doesn't fit screen
						"ladspa-multivoiceChorus" : Categories.chorus,
						"ladspa-foverdrive" : Categories.distortions,
						"ladspa-declip" : Categories.filters, #couldn't properly test it since I had no clipping audio
						"ladspa-comb" : Categories.filters,
						"ladspa-ringmod-1i1o1l" : Categories.modulators,
						"ladspa-shaper" : Categories.filters,
						"ladspa-divider" : Categories.filters,
						"ladspa-diode" : Categories.distortions,
						"ladspa-amp" : Categories.amplifiers,
						"ladspa-Parametric1" : Categories.filters,
						"ladspa-wshape-sine" : Categories.broken, #no change in sound?
						"ladspa-vcf303" : Categories.filters,
						"ladspa-limit-rms" : Categories.broken, #controls make it unusable
						"ladspa-limit-peak" : Categories.broken, #controls make it unusable
						"ladspa-expand-rms" : Categories.broken, #controls make it unusable
						"ladspa-expand-peak" : Categories.broken, #controls make it unusable
						"ladspa-compress-rms" : Categories.broken, #controls make it unusable
						"ladspa-compress-peak" : Categories.broken, #controls make it unusable
						"ladspa-identity-audio" : Categories.broken, #no change in sound?
						"ladspa-hard-gate" : Categories.filters,
						"ladspa-grain-scatter" : Categories.broken, #no sound
						"ladspa-fbdelay-60s" : Categories.delays,
						"ladspa-fbdelay-5s" : Categories.delays,
						"ladspa-fbdelay-1s" : Categories.delays,
						"ladspa-fbdelay-0-1s" : Categories.delays,
						"ladspa-fbdelay-0-01s" : Categories.delays,
						"ladspa-delay-60s" : Categories.delays,
						"ladspa-delay-1s" : Categories.delays,
						"ladspa-delay-0-1s" : Categories.delays,
						"ladspa-delay-0-01s" : Categories.delays,
						"ladspa-disintegrator" : Categories.filters, #crap
						"ladspa-triangle-fcsa-oa" : Categories.oscillators,
						"ladspa-triangle-fasc-oa" : Categories.broken, #no sound
						"ladspa-syncsquare-fcga-oa" : Categories.oscillators,
						"ladspa-syncpulse-fcpcga-oa" : Categories.oscillators,
						"ladspa-sum-iaic-oa" : Categories.filters,
						"ladspa-square-fa-oa" : Categories.oscillators,
						"ladspa-sinusWavewrapper" : Categories.filters,
						"ladspa-ratio-ncda-oa" : Categories.distortions,
						"ladspa-ratio-nadc-oa" : Categories.broken, #no sound
						"ladspa-random-fcsa-oa" : Categories.oscillators, #we GOTTA call this Atari or Arcade. It's the same sound!
						"ladspa-random-fasc-oa" : Categories.broken, #no sound
						"ladspa-sawtooth-fa-oa" : Categories.oscillators,
						"ladspa-pulse-fcpa-oa" : Categories.oscillators,
						"ladspa-pulse-fapc-oa" : Categories.oscillators,
						"ladspa-product-iaic-oa" : Categories.oscillators,
						"ladspa-lp4pole-fcrcia-oa" : Categories.filters,
						"ladspa-fmod-fcma-oa" : Categories.filters,
						"ladspa-fmod-famc-oa" : Categories.broken, #controls make it unusable
						"ladspa-amp-gcia-oa" : Categories.broken, #controls make it unusable
						"ladspa-difference-icma-oa" : Categories.amplifiers,
						"ladspa-difference-iamc-oa" : Categories.broken, #no sound
						"ladspa-sine-fcaa" : Categories.oscillators,
						"ladspa-sine-faac" : Categories.broken, #no sound
						"ladspa-hpf" : Categories.filters,
						"ladspa-lpf" : Categories.filters,
						"ladspa-adsr" : Categories.broken, #controls make it unusable, no sound
						"ladspa-amp-mono" : Categories.amplifiers,
						"ladspa-delay-5s" : Categories.delays
						}
DEBUG_STDOUT, DEBUG_GST = (False, False)

_export_template = ("description", "extension", "pipeline", "setSampleRate", "setBitRate") 
_export_formats = 	[
					("Ogg Vorbis", "ogg", "vorbisenc bitrate=%(bitrate)d ! oggmux", True, True),
					("MP3", "mp3", "lame bitrate=%(bitrate)d ", True, True),
					("Flac", "flac", "flacenc", True, False),
					("WAV", "wav", "wavenc", True, False),
					]

EXPORT_FORMATS = []

DEFAULT_SAMPLE_RATE = 44100
SAMPLE_RATES = [8000, 11025, 22050, 32000, 44100, 48000, 96000, 192000]

DEFAULT_BIT_RATE = 128
BIT_RATES = [32, 64, 96, 128, 160, 192, 224]

PLAYBACK_BACKENDS = [
	(_("Autodetect"), "autoaudiosink"),
	(_("Use GNOME Settings"), "gconfaudiosink"),
	("ALSA", "alsasink"),
	("OSS", "osssink"),
	("JACK", "jackaudiosink"),
	("PulseAudio", "pulsesink"),
	("Direct Sound", "directsoundsink"),
	("Core Audio", "osxaudiosink")
]

CAPTURE_BACKENDS = [
	(_("GNOME Settings"), "gconfaudiosrc"),
	("ALSA", "alsasrc"),
	("OSS", "osssrc"),
	("JACK", "jackaudiosrc"),
	("PulseAudio", "pulsesrc"),
	("Direct Sound", "dshowaudiosrc"),
	("Core Audio", "osxaudiosrc")
]

""" Default Instruments """
DEFAULT_INSTRUMENTS = []
""" init Settings """
settings = Settings()

""" Cache Instruments """
gobject.idle_add(idleCacheInstruments)


gobject.set_application_name(_("Jokosher Audio Editor"))
gobject.set_prgname(LOCALE_APP)
gtk.window_set_default_icon_name("jokosher")
# environment variable for pulseaudio type
os.environ["PULSE_PROP_media.role"] = "production"

# I have decided that Globals.py is a boring source file. So, here is a little
# joke. What does the tax office and a pelican have in common? They can both stick
# their bills up their arses. Har har har.
