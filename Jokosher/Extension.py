# The Jokosher Extension API
# write proper docstrings so that we can autogenerate the docs

import os, sys, gtk, imp, Globals
import gettext
_ = gettext.gettext

# Define some constants
EXTENSION_DIR_USER = os.path.expanduser('~/.jokosher/extensions/')
EXTENSION_DIRS = [EXTENSION_DIR_USER, '/usr/lib/jokosher/extensions/']
# add your own extension dirs with envar JOKOSHER_EXTENSION_DIRS, colon-separated
OVERRIDE_EXTENSION_DIRS = os.environ.get('JOKOSHER_EXTENSION_DIRS','')
if OVERRIDE_EXTENSION_DIRS:
	EXTENSION_DIRS = OVERRIDE_EXTENSION_DIRS.split(':') + EXTENSION_DIRS
PREFERRED_EXTENSION_DIR = EXTENSION_DIRS[0]

# A couple of small constants; they get used as the default response from a
# dialog, and they're nice and high so they don't conflict with anything else
RESP_INSTALL = 9999
RESP_REPLACE = 9998

# Work out whether I'm being imported by a extension that's being run directly
# or whether I'm being imported by a extension run by Jokosher. If I'm being
# run directly then that isn't right, and probably means that the user has
# just clicked on an extension in the file manager. To be nice to them, we
# offer to install the extension in their .jokosher folder.
import inspect
extension_that_imported_me = inspect.currentframe().f_back
try:
	thing_that_imported_extension = extension_that_imported_me.f_back 
except:
	thing_that_imported_extension = None
	
if thing_that_imported_extension is None and \
			os.path.split(extension_that_imported_me.f_code.co_filename)[1] != 'JokosherApp.py':
	# the extension is being run directly; pop up the error 
	try:
		import gtk
	except:
		# no Gtk either! Print a message and die
		import sys
		Globals.debug(_("This is a Jokosher extension; it is not meant to be run directly."))
		Globals.debug(_("To install it, move it to the directory %s\nand run Jokosher.") % (EXTENSION_DIR_LOCAL))
		sys.exit(1)
		
	message = _("This is a Jokosher extension, which needs to be installed. Would you like to install it?")
	d = gtk.MessageDialog(message_format=message, type=gtk.MESSAGE_ERROR)
	d.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('Install'), RESP_INSTALL)
	d.set_default_response(RESP_INSTALL)
	ret = d.run()
	d.destroy()
	if ret == RESP_INSTALL:
		extension_path_and_file = extension_that_imported_me.f_globals['__file__']
		extension_file_name = os.path.split(extension_path_and_file)[1]
		new_extension_path_and_file = os.path.join(PREFERRED_EXTENSION_DIR, extension_file_name)
		if os.path.exists(new_extension_path_and_file):
			message_template = _("You already have a extension with the name %s installed; would you like to replace it?")
			message = message_template % os.path.splitext(extension_file_name)[0]
			d = gtk.MessageDialog(message_format=message, type=gtk.MESSAGE_QUESTION)
			d.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('Replace'), RESP_REPLACE)
			d.set_default_response(RESP_REPLACE)
			ret = d.run()
			d.destroy()
			if ret != RESP_REPLACE:
				sys.exit(0)
		# confirm that the new path exists!
		try:
			os.makedirs(os.path.split(new_extension_path_and_file)[0])
		except:
			pass # already exists
		# and move the extension
		os.rename(extension_path_and_file, new_extension_path_and_file)
		d = gtk.MessageDialog(message_format=_("Your new extension is now available in Jokosher!"), buttons=gtk.BUTTONS_OK)
		d.destroy()
		sys.exit(0)

############################################################################
############# The actual extension API #####################################
############################################################################
#required API imports
import ConfigParser
import gst

class ExtensionAPI:
	def __init__(self, mainapp):
		self.mainapp = mainapp
		
	def add_menu_item(self, menu_item_name, callback_function):
		"""
		   Adds a menu item to a Jokosher extension menu.
		"""
		extensions_menu = self.mainapp.wTree.get_widget("extensionsmenu").get_submenu()
		new_menu_item = gtk.MenuItem(menu_item_name)
		new_menu_item.connect("activate", callback_function)
		extensions_menu.prepend(new_menu_item)
	
	def play(self, play_state=True):
		"""
		   If play_state is True, it will play the project from the beginning.
		   Otherwise, it will stop all playing.
		"""
		#Stop current playing (if any) and set to playhead to the beginning
		self.mainapp.Stop()
		if play_state:
			#Commence playing
			self.mainapp.Play()
		
	def stop(self):
		"""
		   Stops the project if it is currently playing.
		   Same as play(play_state=False)
		"""
		self.mainapp.Stop()
		
	def add_file_to_selected_instrument(self, uri, position=0):
		"""
		   Creates a new event from the file at the given URI and 
		   adds it to the first selected instrument at position (in seconds).
		   Return values:
		   0: success
		   1: bad URI or file could not be loaded
		   2: no instrument selected
		"""
		instr = None
		for i in self.mainapp.project.instruments:
			if i.isSelected:
				instr = i
				break
		
		if not instr:
			#No instrument selected
			return 2
		
		instr.addEventFromFile(position, uri)
		#TODO: find out if the add failed and return 1
		return 0
		
	def get_available_instruments(self):
		"""
		   Returns a list of instrument 'type' strings.
		   The list will contain exactly one string for each
		   available type of instrument.
		"""
		return [x[1] for x in Globals.getCachedInstruments()]
		
	def add_instrument(self, instr_type):
		"""
		   Adds an instrument with the type 'instr_type'
		   from get_available_instruments() to the project.
		   Return values:
		   -1: that project type does not exist
		   >0: success
		   If the instrument is successfully added,
		   the return value will be the ID of that instrument.
		"""
		for i in Globals.getCachedInstruments():
			if i[1] == instr_type:
				instr_index = self.mainapp.project.AddInstrument(i[0], i[1], i[2])
				self.mainapp.UpdateDisplay()
				return instr_index
		return -1
		
	def delete_instrument(self, instrumentID):
		"""
		   Removes the instrument with the ID
		   that equals instrumentID.
		"""
		self.mainapp.project.DeleteInstrument(instrumentID)
		self.mainapp.UpdateDisplay()
		#time for a Newfie Joke: 
		#How many Newfies does it take to go ice fishing?
		#Four. One to cut a hole in the ice and three to push the boat through.

	def create_new_instrument_type(self, defaultName, typeString, imagePath):
		"""
		   Creates and new instrument type in the user's 
		   ~/.jokosher/instruments folder. It will then be automatically
		   loaded on startup.
		   
		   defaultName - the en_GB name of the instrument
		   typeString - a unique string to this particular instrument file
		   imagePath - absolute path to the instruments image
		   
		   Return values:
		   0: sucess
		   1: file exists or defaultName is already used by a loaded instrument
		   2: cannot load image
		   3: cannot write to ~/.jokosher/instruments or ~/.jokosher/instruments/images
		"""
		typeList = [x[1] for x in Globals.getCachedInstruments()]
		if typeString in typeList:
			#if the typeString is already being used, just add a number to the end like "guitar2"
			count = 1
			path = os.path.join(Globals.INSTR_PATHS[1], "%s" + ".instr")
			typeString = typeString + str(count)
			while typeString in typeList and not os.path.exists(path% (typeString)):
				count += 1
				typeString  = typeString[:-1] + str(count)
				
		#check if the type string is being used by any other loaded instrument
		if defaultName in [x[0] for x in Globals.getCachedInstruments()]:
			Globals.debug("An instrument already loaded with name", defaultName)
			return 1
		
		try:
			pixbuf = gtk.gdk.pixbuf_new_from_file(imagePath)
		except gobject.GError:
			return 2
		if pixbuf.get_width() != 48 or pixbuf.get_height() != 48:
			pb = pixbuf.scale_simple(48, 48, gtk.gdk.INTERP_BILINEAR)
			pixbuf = pb
		try:
			pixbuf.save(Globals.INSTR_PATHS[1] + "/images/" + typeString + ".png", "png")
		except gobject.GError:
			return 3
		
		Globals.debug("Creating new instrument type")
		instr = ConfigParser.ConfigParser()
		instr.add_section("core")
		instr.add_section("i18n")
		instr.set("core", "icon", typeString + ".png")
		instr.set("core", "type", typeString)
		instr.set("i18n", "en", defaultName)

		instrument_file = os.path.join(Globals.INSTR_PATHS[1], typeString + ".instr")
		try:
			file = open(instrument_file, 'w')
			instr.write(file)
		except IOError:
			if file:
				file.close()
			return 3
		else:
			file.close()
		
		#refresh the instrument list so our new instrument gets loaded.
		Globals.getCachedInstruments(checkForNew=True)
		
		return 0
		
	def add_export_format(self, description, extension, encoderName, muxerName=None, requiresAudioconvert=False):
		"""
		   Adds a new format that the use can select from
		   the filetype drop down box in the 'Mixdown Project' dialog.
		   Description - string for the drop down box. ex: 'Ogg Vorbis (.ogg)'
		   Extension - string of the file extension without a '.'. ex: 'ogg'
		   encoderName - string used by element_factory_make for the encoder. ex: 'vorbisenc'
		   muxerName - string used by element_factory_make for the muxer. ex: 'oggmux', None (if no muxer is used)
		   requiresAudioconvert - True if an audioconvert is needed between the level element and the encoder.
		   
		   Return values:
		   0: success
		   1: invalid options
		   2: cannot create encoder/muxer element
		"""
		
		if not description or not extension and not encoderName:
			return 1
		try:
			element = gst.element_factory_make(encoderName)
			if muxerName:
				element = gst.element_factory_make(muxerName)
			del element
		except gst.PluginNotFoundError:
			return 2
			
		propslist = (description, extension, encoderName, muxerName, requiresAudioconvert)
		propsdict = dict(zip(Globals._export_template, propslist))
		Globals.EXPORT_FORMATS.append(propsdict)
		
		return 0


def LoadAllExtensions():
	"""
		 Walk through all the EXTENSION_DIRS and import every .py file we find.
	"""
	for exten_dir in EXTENSION_DIRS:
		if not os.path.isdir(exten_dir):
			continue
		#get a list of all the file that end in .py
		fileList = [x for x in os.listdir(exten_dir) if x.endswith(".py")]
		for f in fileList:
			module = None
			fn = os.path.splitext(f)[0]
			Globals.debug("importing extension", f)
			exten_file, filename, description = imp.find_module(fn, [exten_dir])
			
			try:
				module = imp.load_module(fn, exten_file, filename, description)
				Globals.debug("done.")
			except Exception, e:
				Globals.debug("failed.")
				Globals.debug(e)
				if exten_file:
					exten_file.close()
				continue
			if exten_file:
				exten_file.close()
			
			# run the module's startup() function if it has one (it should do),
			# and throw away errors. (FIXME: should throw away "it doesn't exist",
			# but report any others so problems can be debugged.)
			if module:
				try:
					module.startup(API)
				except:
					pass
			#don't block the gui when loading many extensions
			while gtk.events_pending():
				gtk.main_iteration()
		
API = None
