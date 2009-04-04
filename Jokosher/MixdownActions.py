#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This module handles the creation of mixdown actions.
#	
#
#-------------------------------------------------------------------------------

import os
import gtk, gtk.glade
import gobject

import Globals
import ProjectManager

import gettext
_ = gettext.gettext


class MixdownActionException(Exception):
	"""
	An exception that occurs when there is a problem when the RunAction() method
	in a MixdownAction. The 'message' attribute is a string to display to the user.
	"""
	def __init__(self, message):
		Exception.__init__(self, message)

#=========================================================================

class RegisterMixdownActionAPI:
	"""
	This class handles the registering and deregistering of MixdownActions.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		"""
		Creates a new instance of RegisterMixdownActionAPI.
		"""
		self.registeredActions = []
		
	#_____________________________________________________________________
	
	def RegisterMixdownActions(self, mixdownActions):
		"""
		Called when MixdownActions needs to be registered.
		Appends the MixdownActions specified to the registered mixdown action list (self.registeredActions)
	
		Parameters:
			mixdownActions -- reference to a tuple containing MixdownAction objects
		"""
		for action in mixdownActions:
			self.registeredActions.append(action)
		
	#_____________________________________________________________________

	def DeregisterMixdownActions(self, mixdownActions):
		"""
		Called when MixdownActions needs to be deregistered.
		Removes the MixdownActions specified from the registered mixdown action list (self.registeredActions)
	
		Parameters:
			mixdownAction -- reference to a tuple containing MixdownAction objects
		"""
		for action in mixdownActions:
			self.registeredActions.remove(action)
	
	#_____________________________________________________________________
	
	def ReturnAllActions(self):
		"""
		Returns all MixdownActions in the registered mixdown action list (self.registeredActions)
		"""
		return self.registeredActions
	
	#_____________________________________________________________________

#=========================================================================

class MixdownAction(gobject.GObject):
	"""
	Represents a mixdown action, used as a building block for mixdown profiles.
	"""

	"""
	Signals:
		"action-configured" -- MixdownAction has been configured
	"""
	
	__gsignals__ = {
		"action-configured" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}

	#_____________________________________________________________________
	
	def __init__(self):
		"""
		Creates a new instance of MixdownAction.
		"""
		gobject.GObject.__init__(self)
		
		# A MixdownAction object has a name, description and icon path.
		self.name = None
		self.description = None
		self.iconPath = None
		
		self.config = {}
		self.isConfigured = None
	
	#_____________________________________________________________________
	
	def ConfigureAction(self):
		"""
		Subclasses should override this method to do configuration.
		This method should handle the configuration of MixdownActions, such as
		modifying details associated with the MixdownAction.
		"""
		pass
		
	#_____________________________________________________________________
	
	def RunAction(self):
		"""
		Do whatever this action actually does.
		"""
		pass
		
	#_____________________________________________________________________
	
#=========================================================================

class ExportAsFileType(MixdownAction):
	"""
	Defines a mixdown action that exports the audio in the user's project to a given file.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, project):
		"""
		Special init function for this particular MixdownAction, which takes
		a reference to the project as a parameter; this is so we can call back
		into the project to do the export.
		This means that the core code must special-case this action creation,
		and if it's creating one of these then pass it a project.
		
		Parameters:
			project -- the current Jokosher Project.
		"""
		MixdownAction.__init__(self)
		self.name = _("Export File")
		self.description = _("Export a file to the destination of your choosing.")
		# stock gtk icon
		self.iconPath = gtk.STOCK_JUMP_TO
		
		self.project = project # note: this is special to this action, and needs
		                       # to be passed, so this action needs special handling
		                       # in the core.
	
	#_____________________________________________________________________
	
	def ConfigureAction(self):
		"""
		See MixdownAction.ConfigureAction
		"""
		self.configureExportTree = gtk.glade.XML(Globals.GLADE_PATH, "ConfigureExportFileAction")
		signals = {
			"on_cancel_button_clicked" : self.__OnCancel,
			"on_ok_button_clicked" : self.__OnOK,
			"on_local_radio_toggled" : self.__OnLocalRadioToggled,
			"on_server_radio_toggled" : self.__OnServerRadioToggled
		}
			
		self.configureExportTree.signal_autoconnect(signals)
		
		self.configureExportWindow = self.configureExportTree.get_widget("ConfigureExportFileAction")
		self.fileEntry = self.configureExportTree.get_widget("file_entry")
		self.formatCombo = self.configureExportTree.get_widget("format_combo")
		self.localRadio = self.configureExportTree.get_widget("local_radio")
		self.serverRadio = self.configureExportTree.get_widget("server_radio")
		self.detailsVBox = self.configureExportTree.get_widget("details_vbox")
		
		self.formatModel = gtk.ListStore(str, str, str) # description, extension, pipeline
			
		# set some properties
		self.formatCombo.set_model(self.formatModel)
		self.formatCombo.clear()
		desc = gtk.CellRendererText()
		self.formatCombo.pack_start(desc)
		self.formatCombo.add_attribute(desc, "text", 0)

		# construct the configuration widgets
		self.__ConstructTable()
		self.__CreateWidgets()
		self.__AttachWidgets()
		self.__BuildLocalHBox()
		self.__PopulateFormatComboBox()
		self.__LoadConfiguration()

		if self.localRadio.get_active():
			self.detailsVBox.pack_start(self.localHBox, False, False)
		else:
			self.detailsVBox.pack_start(self.serverTable, False, False)
		self.detailsVBox.show_all()
		
	#_____________________________________________________________________

	def RunAction(self):
		"""
		See MixdownAction.RunAction
		"""
		filePath = os.path.join( self.config["location"], "%s.%s" % ( self.config["filename"], self.config["filetype"] ) )
		try:
			self.project.Export(filePath, self.config["pipeline"])
		except ProjectManager.ProjectExportException, e:
			msg = "%s"
			if e.errno == ProjectManager.ProjectExportException.MISSING_ELEMENT:
				msg = _("An encoding plugin could not be found: %s.\nPlease make sure all the plugins required for the specified format are installed.")
			elif e.errno == ProjectManager.ProjectExportException.INVALID_ENCODE_BIN:
				msg = _("The encoding bin description is invalid: %s")
			msg %= e.message
			raise MixdownActionException(msg)
		
	#_____________________________________________________________________
	
	def __ConstructTable(self):
		"""
		Called when the server table (self.serverTable) needs to be constructed.
		Creates the server table.
		"""
		self.serverTable = gtk.Table(4, 2)
		self.serverTable.set_row_spacing(0, 6)
		self.serverTable.set_row_spacing(1, 6)
		self.serverTable.set_row_spacing(2, 6)
		self.serverTable.set_row_spacing(3, 6)
		self.serverTable.set_col_spacing(0, 12)
		self.serverTable.set_col_spacing(1, 12)
		
	#_____________________________________________________________________
	
	def __CreateWidgets(self):
		"""
		Called when widgets in the server table (self.serverTable) need to be created.
		Creates the widgets associated with the server table.
		"""
		self.serverType = gtk.Label(_("Server type:"))
		self.serverType.set_alignment(0, 0.5)
		
		self.serverTypeCombo = gtk.ComboBox()
		self.serverTypeCombo.clear()
		textrend = gtk.CellRendererText()
		self.serverTypeCombo.pack_start(textrend)
		self.serverTypeCombo.add_attribute(textrend, "text", 0)
		self.serverTypeModel = gtk.ListStore(str)
		self.serverTypeModel.append(("HTTP",))
		self.serverTypeModel.append(("FTP",))
		self.serverTypeCombo.set_model(self.serverTypeModel)
		
		self.serverLocation = gtk.Label(_("Server location:"))
		self.serverLocation.set_alignment(0, 0.5)
		self.serverLocationEntry = gtk.Entry()
		
		self.username = gtk.Label(_("Username:"))
		self.username.set_alignment(0, 0.5)
		self.usernameEntry = gtk.Entry()
		
		self.password = gtk.Label(_("Password:"))
		self.password.set_alignment(0, 0.5)
		self.passwordEntry = gtk.Entry()
		self.passwordEntry.set_visibility(False)
		
	#_____________________________________________________________________

	def __AttachWidgets(self):
		"""
		Called when the server widgets need to be added to the server table (self.serverTable).
		Attaches the server widgets to the server table.
		"""
		self.serverTable.attach(self.serverType, 0, 1, 0, 1)
		self.serverTable.attach(self.serverTypeCombo, 1, 2, 0, 1)
		self.serverTable.attach(self.serverLocation, 0, 1, 1, 2)
		self.serverTable.attach(self.serverLocationEntry, 1, 2, 1, 2)
		self.serverTable.attach(self.username, 0, 1, 2, 3)
		self.serverTable.attach(self.usernameEntry, 1, 2, 2, 3)
		self.serverTable.attach(self.password, 0, 1, 3, 4)
		self.serverTable.attach(self.passwordEntry, 1, 2, 3, 4)
		
	#_____________________________________________________________________

	def __BuildLocalHBox(self):
		"""
		Called when the location hbox needs to be created.
		Sets up the location hbox in configuration dialog.
		"""
		self.localHBox = gtk.HBox()
		self.localHBox.set_spacing(6)
		self.localEntry = gtk.Entry()
		self.localButton = gtk.Button()
		self.localButton.connect("clicked", self.__ShowDirectoryChooserDialog)
		self.openImage = gtk.Image()
		self.openImage.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
		self.localButton.set_image(self.openImage)
		self.localHBox.pack_start(gtk.Label(_("Location:")), False, False)
		self.localHBox.pack_start(self.localEntry, True, True)
		self.localHBox.pack_start(self.localButton, False, False)
	
	#_____________________________________________________________________
	
	def __PopulateFormatComboBox(self):
		"""
		Called when the format combo model (self.formatModel) needs to be populated.
		Populates the format combo model with Jokosher's currently available export formats.
		"""
		for format in Globals.EXPORT_FORMATS:
			self.formatModel.append((format["description"], format["extension"], format["pipeline"]))
				
	#_____________________________________________________________________
	
	def __LoadConfiguration(self):
		"""
		Called when the configuration for the configuration window needs to be set.
		Updates the widgets to reflect the configuration details that have been loaded.
		"""
		if self.config.has_key("filename"):
			self.fileEntry.set_text(self.config["filename"])
		if self.config.has_key("location"):
			self.localEntry.set_text(self.config["location"])
		if self.config.has_key("filetype"):
			active = -1
			for item in self.formatModel:
				active += 1
				if item[1] == self.config["filetype"]:
					self.formatCombo.set_active(active)
					break

	#_____________________________________________________________________
	
	def __FinishConfiguration(self):
		"""
		Called when configuration needs to be finished.
		This method finishes the action's configuration by modifying
		the configuration dictionary (self.config) to use the new
		configuration details.
		"""
		self.config["filename"] = self.fileEntry.get_text()
		self.config["location"] = self.localEntry.get_text()
		self.config["filetype"] = self.formatModel[self.formatCombo.get_active()][1]
		self.config["pipeline"] = self.formatModel[self.formatCombo.get_active()][2]
		
		fullPath = os.path.join( self.config["location"], "%s.%s" % ( self.config["filename"], self.config["filetype"] ) )
		
		if fullPath in self.project.GetInputFilenames():
			directory, fileName, ext = self.__MakeUniqueFilename(fullPath)
			self.config["filename"] = fileName
			self.config["location"] = directory
			self.config["filetype"] = ext.split(".")[1]
			
		Globals.settings.general["projectfolder"] = os.path.dirname(fullPath)
		Globals.settings.write()

	#_____________________________________________________________________
	
	def __ShowDirectoryChooserDialog(self, widget):
		"""
		Shows a gtk.FileChooserDialog, allowing the user
		to select which directory their audio should be exported to.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		chooser = gtk.FileChooserDialog((_('Select Export Location')), None, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		if os.path.exists(Globals.settings.general["projectfolder"]):
			chooser.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			chooser.set_current_folder(os.path.expanduser("~"))

		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_transient_for(self.configureExportWindow)
		response = chooser.run()
			
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			self.localEntry.set_text(filename)
		chooser.destroy()
		
	#_____________________________________________________________________
	
	def __OnCancel(self, widget):
		"""
		Called when the Cancel Button is clicked.
		Destroys the configuration window.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.configureExportWindow.destroy()
		
	#_____________________________________________________________________
		
	def __OnOK(self, widget):
		"""
		Called when the OK Button is clicked.
		Finishes the mixdown action's configuration.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# the local directory is the only option which works right now
		if self.localRadio.get_active():
			if self.fileEntry.get_text() and self.localEntry.get_text():
				self.__FinishConfiguration()
		
		self.emit("action-configured")
		self.configureExportWindow.destroy()
	
	#_____________________________________________________________________
	
	def __OnLocalRadioToggled(self, widget):
		"""
		Called when the local directory radio button is activated.
		Shows the location hbox.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		for children in self.detailsVBox.get_children():
			self.detailsVBox.remove(children)
		self.detailsVBox.pack_start(self.localHBox, False, False)
		self.detailsVBox.show_all()

	#_____________________________________________________________________

	def __OnServerRadioToggled(self, widget):
		"""
		Called when the server radio button is activated.
		Shows the server table.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		for children in self.detailsVBox.get_children():
			self.detailsVBox.remove(children)
		self.detailsVBox.pack_start(self.serverTable, False, False)
		self.detailsVBox.show_all()
		
	#_____________________________________________________________________
	
	def __MakeUniqueFilename(self, filename):
		"""
		From a given filename generates a name which doesn't exist
		by appending increasing numbers to it as necessary.
		
		Return:
			the unique filename
		"""
		dirName, baseName = os.path.split(filename)
		name, ext =  os.path.splitext(baseName)
		current = name
		count = 1
		while os.path.exists(os.path.join(dirName, current + ext)):
			current = "%s-%d" % (name, count)
			count += 1
		return (dirName, current, ext)
		
	#_____________________________________________________________________

#=========================================================================

class RunAScript(MixdownAction):
	"""
	Defines a mixdown action that runs a given script while mixing down.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		"""
		See MixdownAction.__init__
		"""
		MixdownAction.__init__(self)
		self.name = _("Run External Script")
		self.description = _("Run an external script from the destination of your choosing.")
		self.iconPath = os.path.join(Globals.IMAGE_PATH, "effect_miscellaneous.png")

	#_____________________________________________________________________

	def ConfigureAction(self):
		"""
		See MixdownAction.ConfigureAction.
		"""
		chooser = gtk.FileChooserDialog((_("Run External Script")), None, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		if os.path.exists(Globals.settings.general["projectfolder"]):
			chooser.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			chooser.set_current_folder(os.path.expanduser("~"))

		chooser.set_default_response(gtk.RESPONSE_OK)
		response = chooser.run()
			
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			self.config["script"] = filename
			self.emit("action-configured")
		chooser.destroy()
	
	#_____________________________________________________________________

	def RunAction(self):
		"""
		See MixdownAction.RunAction.
		"""
		import subprocess
		import os.path
		# Interestingly when you use shell=True Popen doesn't raise an OSError if the script doesn't exist
		# because the shell runs happily (you get a shell error on stderr instead).
		# So we need to raise it by hand, or use shell=False and require an interpreter line
		if os.path.exists(self.config["script"]):
			try:
				# needs to happen in a thread!
				subprocess.Popen(self.config["script"] ,shell=True).wait()
			except OSError:
				Globals.debug(_("An error occured with the script %s") % self.config["script"])
			except:
				Globals.debug(_("Error in script %s") % self.config["script"])
		
		else:
			Globals.debug(_("The script %s does not exist.") % self.config["script"])
				
	#_____________________________________________________________________
	
#=========================================================================

