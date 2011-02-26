#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This module is used to present a dialog which allows the user to create, modify and
#	remove mixdown profiles.
#
#-------------------------------------------------------------------------------

import gtk
import gobject

import Globals
import MixdownProfileManager
import MixdownActions

import gettext
_ = gettext.gettext

#=========================================================================

class MixdownProfileDialog:
	"""
	This class allows the user to create, modify and remove mixdown profiles.
	"""
	
	#_____________________________________________________________________

	def __init__(self, mainapp, project, profile=None):
		"""
		Creates a new instance of MixdownProfileDialog.
		
		Parameters:
			project -- the currently active Project.
			mainapp -- reference to the MainApp Jokosher window.
		"""
		if profile:
			self.profile = profile
		else:
			self.profile = None
			
		self.mainapp = mainapp
		self.project = project
		
		self.gtk_builder = Globals.LoadGtkBuilderFilename("MixdownProfileDialog.ui")

		self.signals = {
			"on_add_profile_button_clicked" : self.OnAddProfile,
			"on_remove_profile_button_clicked" : self.OnRemoveProfile,
			"on_configure_action_button_clicked" : self.OnConfigureAction,
			"on_add_action_button_clicked" : self.OnAddAction,
			"on_remove_action_button_clicked" : self.OnRemoveAction,
			"on_cancel_button_clicked" : self.OnDestroy,
			"on_mixdown_button_clicked" : self.OnMixdown
		}

		self.gtk_builder.connect_signals(self.signals)

		self.window = self.gtk_builder.get_object("MixdownProfileDialog")
		self.window.set_default_size(450, 400)
		self.window.set_icon(self.mainapp.icon)

		self.profileCombo = self.gtk_builder.get_object("profile_combo")
		self.treeView = self.gtk_builder.get_object("actions_treeview")
		self.mixdownButton = self.gtk_builder.get_object("mixdown_button")
		self.configureLabel = self.gtk_builder.get_object("action_configured_label")
		
		self.manager = MixdownProfileManager.MixdownProfileManager(self)
		
		self.treeViewModel = gtk.ListStore(gtk.gdk.Pixbuf, str, object) # pixbuf, details, class instance
		self.profileComboModel = gtk.ListStore(str)
		
		self.treeView.set_model(self.treeViewModel)
		self.profileCombo.set_model(self.profileComboModel)
		
		iconCell = gtk.CellRendererPixbuf()
		iconColumn = gtk.TreeViewColumn()
		iconColumn.pack_start(iconCell, False)
		iconColumn.add_attribute(iconCell, "pixbuf", 0)
		
		detailsCell = gtk.CellRendererText()
		detailsColumn = gtk.TreeViewColumn()
		detailsColumn.pack_start(detailsCell, False)
		detailsColumn.add_attribute(detailsCell, "markup", 1)
		
		self.treeView.append_column(iconColumn)
		self.treeView.append_column(detailsColumn)
		
		self.profileCombo.clear()
		textrend = gtk.CellRendererText()
		self.profileCombo.pack_start(textrend)
		self.profileCombo.add_attribute(textrend, "text", 0)
		self.profileCombo.connect("changed", self.OnProfileComboBoxChanged)
		
		self.treeViewSelection = self.treeView.get_selection()
		self.treeViewSelection.connect("changed", self.OnSelectionChanged)
		self.treeViewSelection.set_mode(gtk.SELECTION_SINGLE)
		
		self.PopulateProfileComboBoxModel()
		
		# the previously selected item in the treeview
		self.lastSelected = None
		# the previously selected action instance in the treeview
		self.lastAction = None
		
		if self.profile:
			self.SetActiveProfileItem(self.profile)
		elif self.CountRowsInTreeModel(self.profileComboModel) > 0:
			self.profileCombo.set_active(0)
			
		self.window.show_all()
		
	#_____________________________________________________________________
	
	def SetActiveProfileItem(self, profileName):
		"""
		Called when an item in the profile combo (self.profileCombo) should be made
		the active item.
		Sets the active item in profile combo by the profile name specified
		
		Parameters:
			profileName -- name of the profile which should be active.
		"""
		active = -1
		for item in self.profileComboModel:
			active += 1
			if item[0] == self.profile:
				self.profileCombo.set_active(active)
				break
			
	#_____________________________________________________________________
	
	def OnSelectionChanged(self, widget):
		"""
		Called when a treeview (self.treeView) selection has been made.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.treeViewSelection.count_selected_rows() > 0:
			self.OnCheckActionConfigured()
			self.UpdateSelectedActionAppearence()
		else:
			return
		
	#_____________________________________________________________________
	
	def UpdateSelectedActionAppearence(self):
		"""
		Called when a MixdownAction is selected in the action treeview (self.treeView).
		Changes the appearence of the selected action.
		"""
		selected = self.treeViewSelection.get_selected()
		action = self.treeViewModel [selected[1]] [2]
		
		# set the foreground colour of the text to white
		newText = "<span size='larger' weight='bold'>%s</span>\n" % action.name  \
		+ "<span size='smaller' foreground='white'>%s</span>" % action.description
		self.treeViewModel [selected[1]] [1] = newText
		
		# modify the last selected item in the model to use the default colour grey
		if self.lastSelected:
			oldText = "<span size='larger' weight='bold'>%s</span>\n" % self.lastAction.name  \
			+ "<span size='smaller' foreground='dim grey'>%s</span>" % self.lastAction.description
			self.treeViewModel [self.lastSelected[1]] [1] = oldText
		
		self.lastAction = action
		self.lastSelected = selected
		
	#_____________________________________________________________________
	
	def OnCheckActionConfigured(self):
		"""
		Called to check if a MixdownAction has been configured.
		Checks to see if the selected action is configured and updates
		the configure label accordingly.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.treeViewSelection.count_selected_rows() > 0:
			profileName = self.profileComboModel[self.profileCombo.get_active()][0]
			selected = self.treeViewSelection.get_selected()
			action = self.treeViewModel [selected[1]] [2]
			if action.isConfigured:
				self.configureLabel.set_markup(_("<b>%s is configured</b>" % action.name))
			else:
				self.configureLabel.set_markup(_("<b>%s is not configured</b>" % action.name))
		else:
			self.configureLabel.set_text("")
			
	#_____________________________________________________________________
	
	def AddActionToActionModel(self, profileName, action):
		"""
		Called when a MixdownAction needs to be added to the action model (self.treeViewModel).
		Adds the information associated with the MixdownAction to the action model.
		
		Parameters:
			profileName -- name of the mixdown profile to add the action to.
			action -- the MixdownAction instance which will be added to the action model.
		"""
		self.treeViewModel.append( self.ReturnActionDisplayDetails(action) )
		self.SaveProfileActions(profileName)
		
	#_____________________________________________________________________
	
	def ReturnActionDisplayDetails(self, action):
		"""
		Called when action details need to be displayed in the action model (self.treeViewModel).
		Returns the details needed for the action to be added to the treeview (self.treeView).
		
		Parameters:
			action -- the MixdownAction instance which will be added to the action model.
		"""
		pixbuf = self.ReturnActionPixbuf(action)
		
		detailsText = "<span size='larger' weight='bold'>%s</span>\n" % action.name  \
		+ "<span size='smaller' foreground='dim grey'>%s</span>" % action.description
		
		return (pixbuf, detailsText, action)
		
	#_____________________________________________________________________
	
	def UpdateProfileModel(self, signalDetails):
		"""
		Called when the profile combo model (self.profileComboModel) needs updating.
		Updates the combo box model with the files that reside in the mixdownprofiles directory
		(JOKOSHER_DATA_HOME/mixdownprofiles/).
		
		Parameters:
			signalName -- the signal details which are passed to this method.
		"""
		profileName = None
		active = self.profileCombo.get_active()

		if signalDetails == "deleteProfile":
			if active:
				active -= 1
		
		self.profileComboModel.clear()
		for item in self.manager.GetMixdownProfileList():
			self.profileComboModel.append((item,))
			self.profileCombo.show_all()
			if active > 0:
				self.profileCombo.set_active(active)
			else:
				self.profileCombo.set_active(0)
		
		if self.CountRowsInTreeModel(self.profileComboModel) > 0:
			profileName = self.profileComboModel[self.profileCombo.get_active()][0]
		self.UpdateActionTreeViewModel(profileName)
			
	#_____________________________________________________________________
		
	def UpdateActionTreeViewModel(self, profileName):
		"""
		Called when the action treeview (self.treeView) needs updating.
		Updates the MixdownActions in the treeview.
		
		Parameters:
			profileName -- the name of the profile to use to retrieve MixdownActions from.
		"""
		self.treeViewModel.clear()
		if profileName:
			actions = self.manager.ReturnAllActionsFromMixdownProfile(profileName)
			if actions:
				for action in actions:
					action.connect("action-configured", self.ActionIsConfigured)
					self.treeViewModel.append( self.ReturnActionDisplayDetails(action) )
		self.OnCheckActionConfigured()

	#_____________________________________________________________________
	
	def ActionIsConfigured(self, action):
		"""
		Called when a MixdownAction has been configured.
		Saves the MixdownActions present in the action treeview (self.treeView)
		to the currently selected profile (self.profileCombo).
		
		Parameters:
			action -- the MixdownAction instance which has just been configured.
		"""
		profileName = self.profileComboModel[self.profileCombo.get_active()][0]
		self.SaveProfileActions(profileName)
		
	#_____________________________________________________________________
	
	def ReturnActionPixbuf(self, action):
		"""
		Called when the action treeview (self.treeView) needs to insert a
		pixbuf associated with a MixdownAction.
		Returns a pixbuf from the icon path specified by the MixdownAction.
		
		Parameters:
			action -- the MixdownAction instance from which a pixbuf will be returned.
			
		Returns:
			pixbuf -- A gtk.gdk.Pixbuf associated with the MixdownAction.
		"""
		if action.iconPath.startswith("gtk"):
			pixbuf = self.treeView.render_icon(action.iconPath, gtk.ICON_SIZE_DIALOG)
		else:
			pixbuf = gtk.gdk.pixbuf_new_from_file(action.iconPath)
	
		if pixbuf.get_property("width") and pixbuf.get_property("height") != 48:
			scaled = pixbuf.scale_simple(48, 48, gtk.gdk.INTERP_BILINEAR)
			return scaled
		else:
			return pixbuf
	
	#_____________________________________________________________________

	def PopulateProfileComboBoxModel(self):
		"""
		Populates the profile combo model (self.profileComboModel) with profiles
		in JOKOSHER_DATA_HOME/mixdownprofiles/
		"""
		for profile in self.manager.GetMixdownProfileList():
			self.profileComboModel.append((profile,))
			
	#_____________________________________________________________________
	
	def OnProfileComboBoxChanged(self, widget):
		"""
		Called when the profile combo box (self.profileCombo) contents change.
		Updates the action treeview (self.treeView) with the MixdownActions in
		the newly selected profile.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.CountRowsInTreeModel(self.profileComboModel) > 0:
			profileName = self.profileComboModel[self.profileCombo.get_active()][0]
			self.UpdateActionTreeViewModel(profileName)
		else:
			# if there is nothing in the combo model, then clear any actions that may be
			# remaining in the action treeview
			self.treeViewModel.clear()
			
	#_____________________________________________________________________

	def OnAddProfile(self, widget):
		"""
		Called when the Add Mixdown Profile button is clicked.
		Shows a dialog allowing the user to add MixdownActions
		to the currently selected profile (self.profileCombo).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.ShowAddProfileDialog()
		
	#_____________________________________________________________________
	
	def ShowAddProfileDialog(self):
		"""
		Shows the Add Mixdown Profile dialog, allowing the user to create a MixdownProfile.
		"""
		buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK)
		
		iconBox = gtk.HBox()
		iconBox.set_border_width(12)
		iconBox.set_spacing(12)
		iconImage = gtk.Image()
		iconImage.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
		iconLabel = gtk.Label(_("Please enter the name of the mixdown profile you wish to create."))
		iconLabel.set_line_wrap(True)
		
		iconBox.pack_start(iconImage, False, False)
		iconBox.pack_start(iconLabel, False, False)
		
		entryBox = gtk.HBox()
		entryBox.set_spacing(12)
		entryBox.set_border_width(6)
		profileEntry = gtk.Entry()
		entryBox.pack_start(gtk.Label(_("Profile name:")), False, False)
		entryBox.pack_start(profileEntry, True, True)
		
		dlg = gtk.Dialog(_("Create Mixdown Profile"), self.window, gtk.DIALOG_DESTROY_WITH_PARENT, buttons)
		dlg.set_default_size(375, 200)
		dlg.set_has_separator(False)
		dlg.set_default_response(gtk.RESPONSE_OK)
		
		dlg.vbox.set_spacing(6)
		dlg.vbox.pack_start(iconBox, False, False)
		dlg.vbox.pack_start(entryBox, False, False)
		dlg.vbox.show_all()
		response = dlg.run()
		
		if response == gtk.RESPONSE_OK:
			msgdlg = gtk.MessageDialog(self.window,
					gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_INFO,
					gtk.BUTTONS_CLOSE)
			if profileEntry.get_text():
				self.manager.SaveMixdownProfile(profileEntry.get_text())
				msgdlg.set_markup(_("Successfully created mixdown profile <b>%s.profile</b>.") % profileEntry.get_text())
				msgdlg.run()
				msgdlg.destroy()
			else:
				msgdlg.set_markup(_("Cannot create mixdown profile. Please make sure you have specified a profile name."))
				msgdlg.set_property("message-type", gtk.MESSAGE_ERROR)
				msgdlg.run()
				msgdlg.destroy()
		dlg.destroy()
		
	#_____________________________________________________________________
	
	def ShowActionErrorDialog(self, actionName, extensionName):
		"""
		Called when an error has occured while loading MixdownActions.
		Shows a dialog informing the user that a MixdownAction has failed to load.
		
		Parameters:
			actionName -- the name of the MixdownAction which cannot be loaded.
			extensionName -- the name of the extension that the MixdownAction can't be loaded from.
		"""
		msgdlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_CLOSE)
		message = _("<big><b>Cannot load mixdown action <i>%(action-name)s</i>.</b></big>\n\nPlease make sure the extension <b>%(extention-name)s</b> is enabled." % {'action-name': actionName, 'extention-name': extensionName})
		msgdlg.set_markup(message)
		msgdlg.run()
		msgdlg.destroy()
		
	#_____________________________________________________________________

	def OnRemoveProfile(self, widget):
		"""
		Called when the Remove Mixdown Profile button is clicked.
		Removes the currently selected profile in the profile
		combo box (self.profileCombo).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.CountRowsInTreeModel(self.profileComboModel) > 0:
			profileName = self.profileComboModel[self.profileCombo.get_active()][0]
			self.manager.DeleteMixdownProfile(profileName)
		else:
			return
	
	#_____________________________________________________________________

	def OnConfigureAction(self, widget):
		"""
		Called when the Configure Mixdown Action button is clicked.
		Calls the selected MixdownAction's ConfigureAction method.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.treeViewSelection.count_selected_rows() > 0:
			selected = self.treeViewSelection.get_selected()
			action = self.treeView.get_model() [selected[1]] [2]
			action.ConfigureAction()
		else:
			return
		
	#_____________________________________________________________________

	def OnAddAction(self, widget):
		"""
		Called when the Add Mixdown Action button is clicked.
		Shows the Add Mixdown Action dialog, allowing the user to add a MixdownAction
		to the currently selected profile (self.profileCombo).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.CountRowsInTreeModel(self.profileComboModel) > 0:
			if self.profileComboModel[self.profileCombo.get_active()][0]:
				self.ShowAddActionDialog()
		else:
			return

	#_____________________________________________________________________

	def OnRemoveAction(self, widget):
		"""
		Called when the Remove Action button is clicked.
		Removes the currently selected action from the action
		treeview (self.treeView)
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.treeViewSelection.count_selected_rows() > 0:
			profileName = self.profileComboModel[self.profileCombo.get_active()][0]
			iterpos = self.treeViewSelection.get_selected()[1]
			self.treeView.get_model().remove(iterpos)
			self.SaveProfileActions(profileName)
		else:
			return
	
	#_____________________________________________________________________
	
	def ShowAddActionDialog(self):
		"""
		Called when the Add Mixdown Action button is clicked.
		Shows a dialog which allows the user to add a MixdownAction
		to the currently selected profile (self.profileCombo)
		"""
		AddMixdownActionDialog(self)
	
	#_____________________________________________________________________

	def SaveProfileActions(self, name):
		"""
		Called when MixdownActions in a profile need to be saved.
		Saves MixdownActions to the profile specified.
		
		Parameters:
			name -- name of the profile which the mixdown actions will be saved to.
		"""
		actions = []
		for row in self.treeView.get_model():
			actions.append(row[2])
		self.manager.SaveMixdownProfile(name, actions)
		
	#_____________________________________________________________________

	def OnDestroy(self, widget):
		"""
		Called when the window is closed. Destroys the window.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.window.destroy()
	
	#_____________________________________________________________________
	
	def OnMixdown(self, widget):
		"""
		Called when the user clicks the Mixdown button.
		Calls the RunAction method on the MixdownActions
		in the action treeview (self.treeView). See RunAction in MixdownActions.py
		for more details.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""

		for row in self.treeViewModel:
			action = row[2]
			try:
				action.RunAction()
			except MixdownActions.MixdownActionException, e:
				text = _("An error occured while running the mixdown action: %s") % action.name
				text = "%s\n\n%s" % (text, e.message)
				dlg = gtk.MessageDialog(self.window,
				          gtk.DIALOG_DESTROY_WITH_PARENT,
				          gtk.MESSAGE_ERROR,
				          gtk.BUTTONS_CLOSE,
				          text)
				dlg.connect('response', lambda dlg, response: dlg.destroy())
				dlg.show()
				return
			
	
	#_____________________________________________________________________
	
	def CountRowsInTreeModel(self, treeModel):
		"""
		Called when the number of rows in the action treeview (self.treeView) is needed.

		Parameters:
			treeModel -- the model to use when counting the number of rows.

		Returns:
			rows -- number of rows in the action treeview.
		"""
		rows = treeModel.iter_n_children(None)
		return rows
	
	#_____________________________________________________________________


#=========================================================================

class AddMixdownActionDialog:
	"""
	This class allows the user to add a MixdownAction to the list of MixdownActions in
	the MixdownProfileDialog.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, profileDialog):
		"""
		Creates a new instance of MixdownProfileDialog.
		
		Parameters:
			profileDialog -- reference to the MixdownProfileDialog object which calls this class.
		"""
		self.profileDialog = profileDialog
		self.add_action_gtk_builder = Globals.LoadGtkBuilderFilename("AddMixdownActionDialog.ui")
		
		signals = {
			"on_cancel_button_clicked" : self.OnCancelAction,
			"on_add_action_button_clicked" : self.OnAddAction,
		}
			
		self.add_action_gtk_builder.connect_signals(signals)
	
		self.addActionDialog = self.add_action_gtk_builder.get_object("AddMixdownActionDialog")
		self.treeView = self.add_action_gtk_builder.get_object("treeview")
		self.actionLabel = self.add_action_gtk_builder.get_object("action_label")
		
		self.treeModel = gtk.ListStore(gtk.gdk.Pixbuf, str, object) # pixbuf, details, class instance
		self.treeView.set_model(self.treeModel)
		
		self.treeView.append_column(gtk.TreeViewColumn(_("Icon"), gtk.CellRendererPixbuf(), pixbuf=0))
		self.treeView.append_column(gtk.TreeViewColumn(_("Name"), gtk.CellRendererText(), markup=1))
		
		self.treeViewSelection = self.treeView.get_selection()
		self.treeViewSelection.connect("changed", self.UpdateSelectedActionAppearence)
		self.treeViewSelection.set_mode(gtk.SELECTION_SINGLE)
		
		self.profileName = self.profileDialog.profileComboModel[self.profileDialog.profileCombo.get_active()][0]
		
		self.lastAction = None
		self.lastSelected = None
		
		# set some properties for the widgets
		self.addActionDialog.set_transient_for(self.profileDialog.window)
		self.addActionDialog.set_icon(self.profileDialog.window.get_icon())
		self.actionLabel.set_markup(_("Please select the mixdown actions you would like to add to mixdown profile <b>%s.</b>") % self.profileName)
	
		self.PopulateActionModel()
	
	#_____________________________________________________________________
	
	def UpdateSelectedActionAppearence(self, widget):
		"""
		Called when a MixdownAction is selected in the add action treeview (self.treeView).
		Changes the appearence of the selected action.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selected = self.treeViewSelection.get_selected()
		action = self.treeModel [selected[1]] [2]
		
		# set the foreground colour of the text to white
		newText = "<span size='larger' weight='bold'>%s</span>\n" % action.name  \
		+ "<span size='smaller' foreground='white'>%s</span>" % action.description
		self.treeModel [selected[1]] [1] = newText
		
		# modify the last selected item in the model to use the default colour grey
		if self.lastSelected:
			oldText = "<span size='larger' weight='bold'>%s</span>\n" % self.lastAction.name  \
			+ "<span size='smaller' foreground='dim grey'>%s</span>" % self.lastAction.description
			self.treeModel [self.lastSelected[1]] [1] = oldText
		
		self.lastAction = action
		self.lastSelected = selected
	
	#_____________________________________________________________________

	def ReturnAllActions(self):
		"""
		Returns all actions in MixdownActions.py, excluding the MixdownAction class.
		
		Returns:
			actionList -- list of MixdownAction instances
		"""
		actionList = []
		for action in self.profileDialog.mainapp.registerMixdownActionAPI.ReturnAllActions():
			# we have to pass Project to ExportAsFileType for it to work
			if action.__name__ == "ExportAsFileType":
				actionList.append( action(self.profileDialog.project) )
			else:
				actionList.append( action() )
		# a list of MixdownAction instances should be returned
		return actionList

	#_____________________________________________________________________

	def PopulateActionModel(self):
		"""
		Called when the action model (self.treeModel) needs to be populated.
		"""
		for action in self.ReturnAllActions():
			self.treeModel.append( self.profileDialog.ReturnActionDisplayDetails(action) )
		
	#_____________________________________________________________________

	def OnAddAction(self, widget):
		"""
		Called when the Add Action button is clicked.
		Adds the selected MixdownAction to the profile dialog's action
		model (self.profileDialog.treeViewModel).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.treeViewSelection.count_selected_rows() > 0:
			selected = self.treeViewSelection.get_selected()
			action = self.treeModel [selected[1]] [2]
			self.profileDialog.AddActionToActionModel(self.profileName, action)
		else:
			return
		self.addActionDialog.destroy()
			
	#_____________________________________________________________________
	
	def OnCancelAction(self, widget):
		"""
		Called when the Cancel button is clicked.
		Destroys the Add Mixdown Action dialog
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.addActionDialog.destroy()
	
	#_____________________________________________________________________

#=========================================================================
