#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Jokosher Extension API.
#
#-------------------------------------------------------------------------------

import os, gtk, imp, pickle, pkg_resources
import traceback
import Globals

import gettext
_ = gettext.gettext

# Define some constants
""" Jokosher user extension directory """
EXTENSION_DIR_USER = os.path.join(Globals.JOKOSHER_DATA_HOME, 'extensions/')

""" Append the default directory to the directory list """
PREFERRED_EXTENSION_DIR = Globals.EXTENSION_PATHS[0]

# A couple of small constants; they get used as the default response from a
# dialog, and they're nice and high so they don't conflict with anything else
RESP_INSTALL = 9999
RESP_REPLACE = 9998

"""
Work out whether this Extension is being imported by an file that's being
run directly, or whether it's being imported by a Jokosher session.
If this Extension is being run directly, which isn't right and probably means
that the user has just clicked on an extension in the file manager, offer the
user the possibility to install the extension in their home folder.
"""
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
		Globals.debug(_("To install it, move it to the directory %s\nand run Jokosher.") % (EXTENSION_DIR_USER))
		sys.exit(1)
		
	message = _("This is a Jokosher extension, which needs to be installed. Would you like to install it?")
	dlg = gtk.MessageDialog(message_format=message, type=gtk.MESSAGE_ERROR)
	dlg.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('Install'), RESP_INSTALL)
	dlg.set_default_response(RESP_INSTALL)
	ret = dlg.run()
	dlg.destroy()
	
	if ret == RESP_INSTALL:
		extension_path_and_file = extension_that_imported_me.f_globals['__file__']
		extension_file_name = os.path.split(extension_path_and_file)[1]
		new_extension_path_and_file = os.path.join(PREFERRED_EXTENSION_DIR, extension_file_name)
		if os.path.exists(new_extension_path_and_file):
			message_template = _("You already have a extension with the name %s installed; would you like to replace it?")
			message = message_template % os.path.splitext(extension_file_name)[0]
			dlg = gtk.MessageDialog(message_format=message, type=gtk.MESSAGE_QUESTION)
			dlg.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('Replace'), RESP_REPLACE)
			dlg.set_default_response(RESP_REPLACE)
			ret = dlg.run()
			dlg.destroy()
			if ret != RESP_REPLACE:
				sys.exit(0)
		# confirm that the new path exists!
		try:
			os.makedirs(os.path.split(new_extension_path_and_file)[0])
		except:
			pass # already exists
		# and move the extension
		os.rename(extension_path_and_file, new_extension_path_and_file)
		dlg = gtk.MessageDialog(message_format=_("Your new extension is now available in Jokosher!"), buttons=gtk.BUTTONS_OK)
		dlg.destroy()
		sys.exit(0)

############################################################################
############# The actual extension API #####################################
############################################################################
#required API imports
import ConfigParser
import gst, gobject

#_____________________________________________________________________

def exported_function(f):
	"""
	Wraps any exported functions so that exceptions do not cross the exported API.
	Any exceptions caught by this function, should be a return error code from 
	exported function.
	
	Parameters:
		f -- function to wrap.
		
	Returns:
		the wrapped function.
	"""
	def wrapped(*args, **kwargs):
		"""
		Parameters:
				*args -- parameters meant for the wrapped function.
				**kwargs -- dictionary of keyword:value parameters meant
							for the wrapped function.
							
		Returns:
			the wrapped function's return value.
		"""
		try:
			result = f(*args, **kwargs)
			return result
		except:
			Globals.debug("EXTENSION API BUG:\nUnhandled exception thrown in exported function: %s\n%s" %
				(f.func_name, traceback.format_exc()))
			return -2
		
	#_____________________________________________________________________
	
	wrapped.__doc__ = f.__doc__
	wrapped.__name__ = f.func_name
	return wrapped

#_____________________________________________________________________

class ExtensionAPI:
	"""
	Defines the API for implementing external extensions for Jokosher.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, mainapp):
		"""
		Creates a new instance of ExtensionAPI.
		
		Parameters:
			mainapp -- reference the MainApp Jokosher window.
		"""
		self.mainapp = mainapp
		self.jokosher = mainapp
		
		self.CONFIGPATH = os.path.join(EXTENSION_DIR_USER, '../extension-config')
		self.DATAPATH = os.path.join(EXTENSION_DIR_USER, '../extension-data')
		
		self.extDataFilename = os.path.join(self.DATAPATH, "extData")
		
		# See if there is a config and data directory, if not, create them
		if not os.path.exists(self.CONFIGPATH):
			os.makedirs(self.CONFIGPATH)
			
		if not os.path.exists(self.DATAPATH):
			os.makedirs(self.DATAPATH)
		
		# try to load the extension data dictionary
		try:
			fp = open(self.extDataFilename)
			self.extData = pickle.load(fp)
			fp.close()
		except:
			self.extData = {}
			
	#_____________________________________________________________________
	
	@exported_function	
	def add_menu_item(self, menu_item_name, callback_function):
		"""
		Adds a menu item to a Jokosher extension menu.
		
		Parameters:
			menu_item_name -- name of the new menu.
			callback_function -- function to be called when the menu is invoked.
								
		Returns:
			reference to the new menu item.
		"""
		extensions_menu = self.mainapp.gtk_builder.get_object("extensionsmenu").get_submenu()
		if isinstance(menu_item_name, gtk.MenuItem):
			new_menu_item = menu_item_name
		else:
			new_menu_item = gtk.MenuItem(menu_item_name)
		
		new_menu_item.connect("activate", callback_function)
		extensions_menu.prepend(new_menu_item)
		new_menu_item.show()
		
		return new_menu_item
	
	#_____________________________________________________________________
	
	@exported_function
	def play(self, play_state=True):
		"""
		Manipulates the Project's playback status in Jokosher.
		
		Parameters:
			play_state -- 	True = play the Project from the beginning.
							False = stop all playback.
		"""
		if play_state:
			#Commence playing
			self.mainapp.Play()
			
	#_____________________________________________________________________

	@exported_function	
	def stop(self):
		"""
		Stops the project if it's currently playing.
		Same as play(play_state=False).
		"""
		self.mainapp.Stop()
		
	#_____________________________________________________________________
	
	@exported_function
	def record(self):
		"""
		Starts the project recording
		
		"""
		self.mainapp.Record()
		
	#____________________________________________________________________	

	@exported_function
	def add_file_to_selected_instrument(self, uri, position=0):
		"""
		Creates a new Event from a given file and adds it to the first
		selected Instrument, at the given position.
		
		Parameters:
			uri -- file with the Event to load.
			position -- position in seconds to insert the new Event at.
		
		Returns:
			0 = the Event was loaded successfully.
			1 = bad URI or file could not be loaded.
			2 = no Instrument selected.
		"""
		selInstr = None
		for instr in self.mainapp.project.instruments:
			if instr.isSelected:
				selInstr = instr
				break
		
		if not selInstr:
			#No instrument selected
			return 2
		
		selInstr.addEventFromFile(position, uri)
		#TODO: find out if the add failed and return 1
		return 0
	
	#_____________________________________________________________________

	@exported_function
	def add_file_to_instrument(self, instr_id, uri, position=0):
		"""
		Creates a new Event from a given file and adds it to the Instrument 
		with the correspondent id, at the given position.
		
		Parameters:
			instr_id -- unique id of the Instrument.
			uri -- file with the Event to load.
			position -- position in seconds to insert the new Event at.
		
		Returns:
			0 = the Event was loaded successfully.
			1 = bad URI or file could not be loaded.
			2 = the Instrument with id 'instr_id' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				instr.addEventFromFile(position, uri)
				#TODO: find out if the add failed and return 1
				return 0
	
		return 2
	
	#_____________________________________________________________________

	@exported_function
	def list_available_instrument_types(self):
		"""
		Obtain a list of tuples in the format:
			(instr_name, instr_type, instr_pixbuf)
		for each of the *.instr files that have been cached.
		
		Considerations:
			These Instruments are *not* the ones in the current Project,
			but those available for any Jokosher Project.
			
		Returns:
			a list with tuples describing each available Instrument in Jokosher.
		"""
		
		return [(x[0], x[1], x[2].copy(), x[3]) for x in Globals.getCachedInstruments()]
	
	#_____________________________________________________________________
		
	@exported_function
	def add_instrument(self, instr_type, instr_name=None):
		"""
		Adds an Instrument to the current Project.
		
		Parameters:
			instr_type -- type of the Instrument to be added.
			instr_name -- name of the Instrument to be added. This value can be
							obtained via get_available_instruments().
		
		Returns:
			-1 = that Instrument type does not exist.
			>0 = if the Instrument is successfully added,
				the return value will be the ID of that Instrument.
		"""
		for instr in Globals.getCachedInstruments():
			if instr[1] == instr_type:
				if instr_name:
					newInstr = self.mainapp.project.AddInstrument(instr_name, instr[1])
				else:
					newInstr = self.mainapp.project.AddInstrument(instr[0], instr[1])
					#instr[0] is the default Instrument name
					#instr[1] is the Instrument type
					#instr[2] is the Instrument icon in the .instr file
				return newInstr.id
		return -1
	
	#_____________________________________________________________________
		
	@exported_function
	def list_project_instruments(self):
		"""
		Obtain a list of tuples in the format:
			(instr_id_number, instr_name, instr_type, instr_pixbuf)
		for each of the Instruments currently shown in the Project.
		
		Returns:
			a list with tuples describing each Instrument in the Project.
		"""
		return [(instr.id, instr.name, instr.instrType, instr.pixbuf.copy()) for instr in self.mainapp.project.instruments]
	
	#_____________________________________________________________________
		
	@exported_function
	def delete_instrument(self, instrumentID):
		"""
		Removes an Instrument from the Project.
		
		Parameters:
			instrumentID -- ID of the Instrument to be removed.
		"""
		self.mainapp.project.DeleteInstrument(instrumentID)
		
		#time for a Newfie Joke: 
		#How many Newfies does it take to go ice fishing?
		#Four. One to cut a hole in the ice and three to push the boat through.
		
	#_____________________________________________________________________

	def __get_config_dict_fn(self):
		"""
		Calculates the config dictionary filename for the calling extension.
		
		Returns:
			the config dictionary filename for the calling extension.
		"""
		# Next, check if this extension has a saved config dict
		# we go back twice because our immediate caller is (get|set)_config_value
		mycallerframe = inspect.currentframe().f_back.f_back
		mycallerfn = os.path.split(mycallerframe.f_code.co_filename)[1]
		mycaller = os.path.splitext(mycallerfn)[0]
		config_dict_fn = os.path.join(self.CONFIGPATH, mycaller + ".config")
		
		return os.path.normpath(config_dict_fn)

	#_____________________________________________________________________

	@exported_function
	def get_config_value(self, key):
		"""
		Obtains the config value saved under this key.
		
		Parameters:
			key -- config key to obtain the value of.
			
		Returns:
			the value of the config key, or None if the value doesn't exist.
		"""
		try:
			# Open the extension's config dict
			# Return the value
			config_dict_fn = self.__get_config_dict_fn()
			fp = open(config_dict_fn)
			config_dict = pickle.load(fp)
			fp.close()
			return config_dict[key]
		except:
			return None
		
	#_____________________________________________________________________

	@exported_function
	def set_config_value(self, key, value):
		"""
		Sets a new config value under a given key for later retrieval.
		
		Parameters:
			key -- name of the key to save the value under.
			value -- value to save.
		"""
		config_dict_fn = self.__get_config_dict_fn()
		if os.path.exists(config_dict_fn):
			fp = open(config_dict_fn)
			config_dict = pickle.load(fp)
			fp.close()
		else:
			config_dict = {}
			
		# Set the config value
		config_dict[key] = value
		
		# And save it again
		fp = open(config_dict_fn, "wb")
		pickle.dump(config_dict, fp)
		fp.close()
		
	#_____________________________________________________________________
	
	def __get_data_filename_fn(self):
		"""
		Generates an unique filename for an extension data file.
		
		Returns:
			the unique data filename.
		"""
		filename = ""
		for i in xrange(1000000):
			filename = os.path.join(self.DATAPATH, "%s.dat" % i)
			if not os.path.exists(filename):
				return filename
			
	#_____________________________________________________________________

	@exported_function
	def get_data_file(self, extName, key):
		"""
		Obtain the data file saved under this key.
		
		Parameters:
			extName -- name of the extension loading the file.
			key -- config key to obtain the data file of.
			
		Returns:
			the data retrieved, or None if the value doesn't exist
				or couldn't be loaded.
		"""
		try:
			fp = open(self.extData[extName][key])
			data = pickle.load(fp)
			fp.close()
			return data
		except:
			return None
		
	#_____________________________________________________________________

	@exported_function
	def set_data_file(self, extName, key, data):
		"""
		Stores a new data file under a given key for later retrieval.
		It must a serializable object.
		
		Parameters:
			extName -- name of the extension loading the file.
			key -- name of the key to save this data under.
			data -- data to store.
		"""
		# see if the dict exists, if not then create it
		if extName not in self.extData:
			self.extData[extName] = {}
			
		# if the data doesn't exist, add the tuple to self.extData
		if key not in self.extData[extName]:
			self.extData[extName][key] = self.__get_data_filename_fn()
		
		# write the serialized file
		fp = open(self.extData[extName][key], "wb")
		pickle.dump(data, fp)
		fp.close()
		
		# write the newly modified self.extData dictionary
		fp = open(self.extDataFilename, "wb")
		pickle.dump(self.extData, fp)
		fp.close()
		
	#_____________________________________________________________________

	@exported_function
	def set_instrument_volume(self, instr_id, instr_volume):
		"""
		Sets the volume of an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to change the value to.
			instr_volume -- value the volume of the Instrument should be set to.
			
		Returns:
			0 = the volume was successfully changed.
			1 = the Instrument with id 'instr_id' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				instr.SetVolume(min(instr_volume, 1))
				return 0
		return 1
	
	#_____________________________________________________________________

	@exported_function
	def get_instrument_volume(self, instr_id):
		"""
		Obtains the volume of an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to obtain the volume from.
			
		Returns:
			volume = volume of the Instrument.
			1 = the Instrument with id 'instr_id' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				return instr.volume
		return 1
	
	#_____________________________________________________________________

	@exported_function
	def toggle_mute_instrument(self, instr_id):
		"""
		Mutes an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to mute.
			
		Returns:
			0 = the Instrument was successfully muted.
			1 = the Instrument with id 'instr_id' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				instr.ToggleMuted(False)
				return 0
		return 1
	
	#_____________________________________________________________________

	@exported_function
	def get_instrument_effects(self, instr_id):
		"""
		Obtains the current effects applied to an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to obtain the effects from.
		
		Returns:
			list = list of effects applied to the Instrument.
			1 = the Instrument with id 'instr_id' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				#return a copy so they can't append or remove items from our list
				return instr.effects[:]

		return 1
	
	#_____________________________________________________________________

	@exported_function
	def list_available_effects(self):
		"""
		Obtain the available LADSPA effects.
		
		Returns:
			a list with all available LADSPA effects.
		"""
		#return a copy so they can't append or remove items from our list
		return Globals.LADSPA_NAME_MAP[:]
	
	#_____________________________________________________________________

	@exported_function
	def add_instrument_effect(self, instr_id, effect_name):
		"""
		Adds an effect to an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to add the effect to.
			effect_name -- name of the effect to be added to Instrument.
			
		Returns:
			0 = the effect was successfully added to the Instrument.
			1 = the Instrument with id 'instr_id' was not found.
			2 = the LADSPA plugin named 'effect_name' was not found.
		"""
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:
				for effect in Globals.LADSPA_NAME_MAP:
					if effect[0] == effect_name:
						instr.AddEffect(effect_name)
						return 0
				return 2
		return 1
	
	#_____________________________________________________________________

	@exported_function
	def remove_instrument_effect(self, instr_id, effect_num):
		"""
		Removes an effect from an Instrument.
		
		Parameters:
			instr_id -- ID of the Instrument to remove the effect from.
			effect_num -- index of the effect inside the Instrument's effects array.
		
		Returns:
			0 = the effect was successfully removed.
			1 = effect_num out of range.
			2 = the Instrument with id 'instr_id' was not found.
			3 = unknown GStreamer error.
		"""		
		for instr in self.mainapp.project.instruments:
			if instr.id == instr_id:	
				if effect_num < len(instr.effects):
					try:
						instr.RemoveEffect(instr.effects[effect_num])
					except:
						return 3
					return 0
				return 1
		return 2
	
	#_____________________________________________________________________

	#TODO: function for editing existing effects

	@exported_function
	def create_new_instrument_type(self, defaultName, typeString, imagePath):
		"""
		Creates a new Instrument type in the user's JOKOSHER_DATA_HOME/instruments folder.
		It will then be automatically loaded on startup.
		
		Parameters:
			defaultName -- the en_GB name of the Instrument.
			typeString -- a unique type string to this particular Instrument file.
			imagePath -- absolute path to the Instrument's image (png).
		
		Returns:
			0 = the new Instrument type was successfully created.
			1 = file already exists or defaultName is already used by a loaded Instrument.
			2 = cannot load image file.
			3 = cannot write to JOKOSHER_DATA_HOME/instruments or JOKOSHER_DATA_HOME/instruments/images.
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
		except (gobject.GError, TypeError):
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
	
	#_____________________________________________________________________
	
	@exported_function
	def delete_instrument_type(self, typeString):
		"""
		Deletes an instrument type from the user's JOKOSHER_DATA_HOME/instruments 
		directory (deleting default instruments isn't allowed)
		
		Parameters:
			typeString -- The instrument type, the instrument name is translated
						so we can't use that one
		
		Returns:
			0 = Instrument successfully deleted
			1 = Instrument is a default instrument and cannot be deleted
			2 = Error deleting instrument files
			3 = Error removing instrument from cache
			4 = Cannot find an instrument with that type string
		"""
		if typeString in Globals.DEFAULT_INSTRUMENTS:
			return 1
			
		instrList = [x for x in Globals.getCachedInstruments() if typeString == x[1]]
		if not instrList:
			return 4
		else:
			instr = instrList[0]
				
		Globals.debug("Deleting instrument type")
		instr_path = os.path.join(Globals.INSTR_PATHS[1], typeString + ".instr")
		image_path = instr[3]
		try:
			os.remove(instr_path)
			os.remove(image_path)
		except:
			return 2
		try:
			Globals.instrumentPropertyList.remove(instr)
		except:
			return 3
			
		return 0
		
	#_____________________________________________________________________
	
	@exported_function
	def add_export_format(self, description, extension, encodeBin, setSampleRate, setBitRate, checkIfValid=True):
		"""
		Adds a new format that the user can select from the filetype drop down box
		in the 'Mixdown Project' dialog.
		
		Parameters:
			description -- string for the drop down box. i.e: 'Ogg Vorbis (.ogg)'.
			extension -- string of the file extension without a '.'. i.e: 'ogg'.
			encodeBin -- string used by gst.parse_bin_from_description to create
						a bin that can encode and mux the audio when added to a
						pipeline. i.e: 'vorbisenc ! oggmux'.
			setSampleRate -- If True this encodeBin will allow the user to set their own sample rate.
			setBitRate -- If True this will allow the user to set their own bit rate.
			checkIfValid -- If True, Jokosher will check if the encodeBin string is valid before adding
						it to the export dialog. If you know a string to be correct, this parameter
						should be False because checking will make startup take longer.
		Returns:
			0 = the new export format was successfully added to Jokosher.
			1 = invalid options.
			2 = a format with the same three values already exists.
			3 = cannot parse or create encoder/muxer bin.
		"""
		if not description or not extension and not encodeBin:
			return 1
			
		if checkIfValid:
			try:
				bin = gst.parse_bin_from_description("audioconvert ! %s" % encodeBin, True)
				del bin
			except gobject.GError:
				return 3
		
		propslist = (description, extension, encodeBin, setSampleRate, setBitRate)
		propsdict = dict(zip(Globals._export_template, propslist))
		if propsdict in Globals.EXPORT_FORMATS:
			return 2
		else:
			Globals.EXPORT_FORMATS.append(propsdict)
			return 0
		
	#_____________________________________________________________________
		
	@exported_function
	def remove_export_format(self, description, extension, encodeBin):
		"""
		Removes an export format that was previously added using add_export_format.
		
		Parameters:
			description -- string for the drop down box. i.e: 'Ogg Vorbis (.ogg)'.
			extension -- string of the file extension without a '.'. i.e: 'ogg'.
			encodeBin -- string used by gst.parse_bin_from_description to create
						a bin that can encode and mux the audio when added to a
						pipeline. i.e: 'vorbisenc ! oggmux'.
		Returns:
			0 = successfully removed the export format.
			1 = no export format exists with those parameters.
		"""
		propslist = (description, extension, encodeBin)
		propsdict = dict(zip(Globals._export_template, propslist))
		if propsdict in Globals.EXPORT_FORMATS:
			Globals.EXPORT_FORMATS.remove(propsdict)
			return 0
		else:
			return 1
		
	#_____________________________________________________________________
	
	@exported_function
	def get_export_formats(self):
		"""
		Returns the list of dictionaries of available export formats
		that Jokosher knowns about. Even if a format is not listed
		here, you can still export with it by passing the gst-launch
		formatted string to export_to_file.
		An example format dictionary for Ogg: 
		{"description":"Ogg Vorbis", "extension":"ogg", "pipeline":"vorbisenc ! oggmux"}
		"""
		newList = []
		for formatDict in Globals.EXPORT_FORMATS:
			newList.append(formatDict.copy())
		
		return newList
	
	#_____________________________________________________________________
	
	@exported_function
	def export_to_file(self, uri, encodeBin):
		"""
		Exports the entire project to a single audio file at the URI given,
		and encoded with the Gstreamer encoding bin given.
		
		Parameters:
			uri -- string of the location to save the file.
			encodeBin -- gst-launch formatted string used to create the 
					bin that will encode the audio before being written to disk.
		"""
		self.mainapp.project.Export(uri, encodeBin)
	
	#_____________________________________________________________________
	
	@exported_function
	def hide_main_window(self, timeout=0):
		"""
		Makes the main Jokosher window invisible.
		
		Parameters:
			timeout -- Number of milliseconds to wait before reshowing the window (0 for infinity).
		"""
		self.mainapp.window.hide()
		if timeout:
			gobject.timeout_add(timeout, self.show_main_window)
	
	#_____________________________________________________________________
	
	@exported_function
	def show_main_window(self):
		"""
		Makes the main Jokosher window visible.
		
		Returns:
			False -- stop calling the callback on a timeout_add.
		"""
		self.mainapp.window.show()
		#in case we we're called by gobject.timeout_add
		return False
	
	#_____________________________________________________________________
	
	@exported_function
	def quit(self):
		"""
		Quits Jokosher.
		"""
		self.mainapp.OnDestroy()
	
	#_____________________________________________________________________
	
	@exported_function
	def get_bpm(self):
		"""
		Returns the current beats per minute for the Project.
		"""
		return self.mainapp.project.bpm	
		
	#_____________________________________________________________________
	
	@exported_function
	def set_bpm(self, bpm):
		"""
		Sets the current beats per minute for the Project.
		
		Parameters:
			bpm -- the beats per minute to set.
		"""
		self.mainapp.project.SetBPM(float(bpm))
		
	#_____________________________________________________________________
	
	@exported_function
	def get_meter(self):
		"""
		Returns the current meter of the project as a tuple.
		"""
		return (self.mainapp.project.meter_nom, self.mainapp.project.meter_denom)
		
	#_____________________________________________________________________
	
	@exported_function
	def set_meter(self, nom, denom):
		"""
		Changes the current time signature.
		
		Example:
			nom = 3
			denom = 4
			
			would result in the following signature:
				3/4
		
		Parameters:
			nom -- new time signature nominator.
			denom --new time signature denominator.
		"""
		self.mainapp.project.SetMeter(nom, denom)
		
	#_____________________________________________________________________
	
	@exported_function
	def set_window_icon(self, window):
		"""
		Sets the specified window to use the Jokosher icon.
		
		Parameters:
			window -- the window which will use the Jokosher icon as its icon in the window border.
		"""
		window.set_icon(self.mainapp.icon)
		
	#_____________________________________________________________________
	
	@exported_function
	def get_position(self):
		"""
		Gives the current position in pipeline
		
		Returns: time in seconds
		"""
		return self.mainapp.project.transport.GetPosition()
			
	#_____________________________________________________________________
	
	@exported_function
	def get_position_as_hours_minutes_seconds(self):
		"""
		Gives the current position in pipeline
		
		Returns: position as a tuple (hours, minutes, seconds, milliseconds)
		"""
		return self.mainapp.project.transport.GetPositionAsHoursMinutesSeconds()
			
	#_____________________________________________________________________
	
	@exported_function
	def get_position_as_bars_and_beats(self):
		"""
		Gives the current position in pipeline
		
		Returns: position as a tuple (bars, beats, ticks)
		"""
		return self.mainapp.project.transport.GetPositionAsBarsAndBeats()
			
	#____________________________________________________________________	
	
	@exported_function
	def add_end_of_stream_handler(self, function):
		"""
		Adds a function to receive and end-of-stream notification.
		
		Parameters:
			function --	the function that will receive the notification
			
		Returns:
			0 = end of stream handler successfully added
			1 = no project currently open
		"""
		if self.mainapp.project:
			self.mainapp.project.AddEndOfStreamHandler(function)
			return 0
		else:
			return 1
		
	#____________________________________________________________________	

	@exported_function
	def remove_end_of_stream_handler(self, function):
		"""
		Removes a function from the end-of-stream-handler list
		
		Parameters:
			function -- the function to remove
		
		Returns:
			0 = end of stream handler successfully removed
			1 = no project currently open
		"""
		if self.mainapp.project:
			self.mainapp.project.RemoveEndOfStreamHandler(function)
			return 0
		else:
			return 1
		
		
	#____________________________________________________________________	

	@exported_function
	def seek(self, start_position, end_position=0):
		"""
		Performs a seek on the pipeline
		
		Parameters:
			start_position -- position to seek to
			end_position -- position where playing will stop
		"""
		self.mainapp.project.transport.SeekTo(start_position, end_position)
		
	#____________________________________________________________________	

	@exported_function
	def get_button_states(self):
		"""
		Obtains the states of the transport toggle buttons
		
		Returns:
			a dictionary containing a set of tuples representing the
			toggle state and sensitive state of the transport buttons
		"""
		stateDict = {}
		for buttonName in ("play","record","stop","reverse","forward"):
			button = getattr(self.mainapp, buttonName)
			if hasattr(button, "get_active"):
				active = button.get_active()
			else:
				active = None
			stateDict[buttonName] = (active, button.get_property("sensitive"))
		return stateDict
	#____________________________________________________________________	

	@exported_function
	def get_pipeline_state(self):
		"""
		Obtains up the state of the pipeline
		
		Returns:
			the state of the pipeline 
		"""
		return self.mainapp.project.mainpipeline.get_state(0)[1]
		
	#____________________________________________________________________	

	@exported_function
	def set_window_parent(self, window):
		"""
		Sets the main Jokosher window as the parent for the given window.
		
		Parameters:
			window -- window who's parent is to be set as the main window.
		"""
		window.set_transient_for(self.mainapp.window)
	
	#_____________________________________________________________________
	
	@exported_function
	def get_position_as_hours_minutes_seconds(self):
		"""
		Obtains the current playback position in hours, minutes, seconds.
		
		Returns:
			tuple of the current position as (hours, minutes, seconds, milliseconds).
			None - no project is currently open
		"""
		if self.mainapp.project:
			return self.mainapp.project.transport.GetPositionAsHoursMinutesSeconds()
		else:
			return None
	#_____________________________________________________________________
	
API = None
