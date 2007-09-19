#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	PidginExtension.py
#	
#	This module handles setting a new status message for pidgin through dbus.
#
#-------------------------------------------------------------------------------
import Jokosher.Extension
import Jokosher.MixdownActions
import gtk
import pkg_resources
import dbus

import gettext
_ = gettext.gettext

#=========================================================================

class StatusAction(Jokosher.MixdownActions.MixdownAction):
	"""
	Defines a mixdown action that sets a status message in Pidgin.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		"""
		See Jokosher.MixdownActions.MixdownAction.__init__
		"""
		Jokosher.MixdownActions.MixdownAction.__init__(self)
		self.name = _("Set Pidgin Status")
		self.description = _("Set a new status message in Pidgin.")
		self.iconPath = pkg_resources.resource_filename(__name__, "pidgin.png")
			
		# create connection to the session bus
		self.bus = dbus.SessionBus()
		
		# get the purple object
		self.obj = self.bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
		
		# get the purple interface
		self.purple = dbus.Interface(self.obj, "im.pidgin.purple.PurpleInterface")
		
	#_____________________________________________________________________

	def ConfigureAction(self):
		"""
		See Jokosher.MixdownActions.MixdownAction.ConfigureAction
		"""
		self.window = gtk.Window()
		self.window.set_position(gtk.WIN_POS_CENTER)
		self.window.set_icon(self.dialogIcon)
		self.window.set_title(_("Set Pidgin Status"))
		
		self.vbox = gtk.VBox()
		self.vbox.set_spacing(6)
		self.vbox.set_border_width(12)
		
		self.table = gtk.Table(2, 2)
		
		self.titleLabel = gtk.Label(_("Title:"))
		self.statusLabel = gtk.Label(_("Status:"))
		self.messageLabel = gtk.Label(_("Message:"))

		self.titleEntry = gtk.Entry()
		self.statusCombo = gtk.ComboBox()
		self.statusModel = gtk.ListStore(str, int) # status text, status ID
		self.messageTextView = gtk.TextView()
		
		# set some properties
		self.statusCombo.clear()
		textrend = gtk.CellRendererText()
		self.statusCombo.pack_start(textrend)
		self.statusCombo.add_attribute(textrend, "text", 0)
		self.statusCombo.set_model(self.statusModel)
		
		self.scrolled = gtk.ScrolledWindow()
		self.scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.scrolled.set_shadow_type(gtk.SHADOW_IN)
		self.scrolled.add(self.messageTextView)
		
		self.table.attach(self.titleLabel, 0, 1, 0, 1, gtk.FILL)
		self.table.attach(self.titleEntry, 1, 2, 0, 1, gtk.FILL|gtk.EXPAND)
		self.table.attach(self.statusLabel, 0, 1, 1, 2, gtk.FILL)
		self.table.attach(self.statusCombo, 1, 2, 1, 2, gtk.FILL|gtk.EXPAND)
		self.table.attach(self.messageLabel, 0, 1, 2, 3, gtk.FILL)
		self.table.attach(self.scrolled, 1, 2, 2, 3, gtk.FILL|gtk.EXPAND, gtk.FILL|gtk.EXPAND)
		
		self.table.set_row_spacing(0, 6)
		self.table.set_row_spacing(1, 6)
		self.table.set_col_spacing(0, 12)
		self.table.set_col_spacing(1, 12)

		self.cancelButton = gtk.Button(stock=gtk.STOCK_CANCEL)
		self.cancelButton.connect("clicked", self.__DestroyWindow)
		self.setStatusButton = gtk.Button(_("Set Status"))
		self.setStatusButton.connect("clicked", self.__SetPidginStatus)

		self.buttonBox = gtk.HButtonBox()
		self.buttonBox.set_spacing(6)
		self.buttonBox.set_layout(gtk.BUTTONBOX_END)
		self.buttonBox.add(self.cancelButton)
		self.buttonBox.add(self.setStatusButton)

		self.vbox.pack_start(self.table, False, False)
		self.vbox.pack_end(self.buttonBox, False, False)
		
		self.window.add(self.vbox)
		self.window.show_all()
		
		# populate the status combo
		self.__PopulateStatusCombo()
		self.__LoadConfiguration()

	#_____________________________________________________________________

	def RunAction(self):
		"""
		See Jokosher.MixdownActions.MixdownAction.RunAction
		"""
		# see http://developer.pidgin.im/doxygen/dev/html/savedstatuses_8h.html
		# for more information about Pidgin's saved status API
		status = self.purple.PurpleSavedstatusNew(self.config["title"], self.config["status"])
		self.purple.PurpleSavedstatusSetMessage(status, self.config["message"])
		self.purple.PurpleSavedstatusActivate(status)
		
	#_____________________________________________________________________
	
	def __PopulateStatusCombo(self):
		"""
		This method populates the status combo model (self.statusModel) with the default
		statuses in Pidgin.
		"""
		# can't get these using dbus, we'll have to do it manually.
		statuses = [	(_("Offline"), 1),
				(_("Available"), 2),
				(_("Do not disturb"), 3),
				(_("Invisible"), 4),
				(_("Away"), 5),
				(_("Extended away"), 6),
				(_("Mobile"), 7)
				]
		for status in statuses:
			self.statusModel.append(status)
	
	#_____________________________________________________________________
	
	def __SetPidginStatus(self, widget):
		"""
		This method sets the pidgin status as specified by the user.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		titleText = self.titleEntry.get_text()
		
		statusText = self.statusModel[self.statusCombo.get_active()][0]
		statusID = self.statusModel[self.statusCombo.get_active()][1]
		
		bounds = self.messageTextView.get_buffer().get_bounds()
		messageText = self.messageTextView.get_buffer().get_text(bounds[0], bounds[1], False)
		
		if titleText and messageText and statusText:
			self.config["title"] = titleText
			self.config["status"] = statusID
			self.config["message"] = messageText
			self.emit("action-configured")
			self.window.destroy()
		else:
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_CLOSE,
				_("Please make sure all fields have been entered correctly."))
			dlg.run()
			dlg.destroy()
		
	#_____________________________________________________________________
	
	def __LoadConfiguration(self):
		"""
		Called when configuration needs to be loaded for the dialog
		"""
		if self.config.has_key("title"):
			self.titleEntry.set_text(self.config["title"])
		if self.config.has_key("message"):
			self.messageTextView.get_buffer().set_text(self.config["message"])
		
		# handle the active status item in the combo
		if self.config.has_key("status"):
			active = -1
			for item in self.statusModel:
				active += 1
				if item[1] == self.config["status"]:
					self.statusCombo.set_active(active)
					break
		
	#_____________________________________________________________________

	def __DestroyWindow(self, widget):
		"""
		Destroys the Pidgin MixdownAction window.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.window.destroy()
		
	#_____________________________________________________________________

#=========================================================================

class PidginExtension:
	"""
	The class implements the PidginExtension extension. This extension registers
	the mixdown action StatusAction using the RegisterMixdownAction method. It is
	then deregistered when an extension is deleted or disabled.
	"""
	EXTENSION_NAME = _("Pidgin Extension")
	EXTENSION_DESCRIPTION = _("Set a new status message in Pidgin")
	EXTENSION_VERSION = "0.1"
	
	#_____________________________________________________________________
	
	def check_dependencies(self):
		"""
		Called by the extension manager to assure that everything this extension
		needs is provided by the system.
		
		For the Pidgin extension, the existence of the purple dbus object is checked.
		
		Returns:
			A tuple in the following format:
				(True, "") if all requirements are met.
				(False, (Error1, Error2, ..., ErrorN)) if there's errors.
					The errors are strings that describe the problem.
		"""
		test = None
		error = "Couldn't connect to the pidgin dbus interface. Is pidgin running?"
		
		try:
			test = self.bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
			return (True, "")
		except Exception:
			return (False, (error))
		
	#_____________________________________________________________________
	
	def startup(self, api):
		"""
		Called by the extension manager during Jokosher startup
		or when the extension is added via ExtensionManagerDialog.
		
		Parameters:
			api -- a reference to the Extension API
		"""
		self.API = api
		self.mixdownActions = (StatusAction,)
		self.obj = self.bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
		self.API.mainapp.registerMixdownActionAPI.RegisterMixdownActions(self.mixdownActions)
		
	#_____________________________________________________________________
	
	def shutdown(self):
		"""
		Called by the extension manager when the extension is
		disabled or deleted.
		"""
		self.API.mainapp.registerMixdownActionAPI.DeregisterMixdownActions(self.mixdownActions)
		
	#_____________________________________________________________________

#=========================================================================
