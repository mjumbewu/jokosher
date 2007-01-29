#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles all of the processing associated with the
#	Mixdown Profile dialog.
#
#-------------------------------------------------------------------------------

import gtk.glade
import gobject
import pygst
pygst.require("0.10")
import gst
import Globals
import gettext
_ = gettext.gettext
import MixdownProfiles
import os

#=========================================================================

class MixdownProfileDialog:
	"""
	Handles all of the processing associated with the Mixdown Profile dialog.
	"""
	
	#_____________________________________________________________________

	def __init__(self, project, parent, profile=None):
		"""
		Creates a new instance of MixdownProfileDialog.
		
		Parameters:
			project -- the currently active Project.
			parent -- reference to the MainApp Jokosher window.
			profile -- a profile name, as saved by SaveSettings
		"""
		if project:
			self.project = project
		else:
			return
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "MixdownProfileDialog")

		self.signals = {
			"on_mixdownbutton_clicked" : self.OnMixdown,
			"on_savesettingsbutton_clicked" : self.OnSaveSettings,
			"on_addstepbutton_clicked" : self.OnAddStep
		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("MixdownProfileDialog")

		self.parent = parent
		self.window.set_icon(self.parent.icon)
		## centre the MixdownProfileDialog on the main jokosher window
		self.window.set_transient_for(self.parent.window)
		
		self.actionstable = self.res.get_widget("actionstable")
		
		# replace $PROJECTNAME with the project name in the window label
		projectnamelabel = self.res.get_widget("lbl_projectname")
		txt = projectnamelabel.get_text()
		txt = txt.replace("$PROJECTNAME", self.project.name)
		projectnamelabel.set_text(txt)

		# populate actions list
		self.possible_action_classes = [
			MixdownProfiles.ExportAsFileType,
			MixdownProfiles.RunAScript
		] # eventually allow extensions to add to this, but not yet

		self.combo_newstep = self.res.get_widget("newstep")
		self.combo_newstep_model = self.combo_newstep.get_model()
		for a in self.possible_action_classes:
			self.combo_newstep_model.append([a.create_name()])

		self.actions = []
		if profile:
			self.RestoreProfile(profile)
		else:		
			# create a "export as Ogg" button by default
			# specialcase ExportAsFileType
			export_action = MixdownProfiles.ExportAsFileType(self.project)
			self.AddAction(export_action)
			
		# If a profile was supplied, show a delete button for it
		
		self.window.show_all()

	#_____________________________________________________________________

	def AddAction(self, action):
		"""
		Adds a MixdownAction to this mixdown profile.
		
		Parameters:
			action -- a MixdownProfiles.MixdownAction subclass.
		"""
		rows = self.actionstable.get_property("n-rows")
		cols = self.actionstable.get_property("n-columns")
		if rows == 1 and len(self.actions) == 0:
			pass
		else:
			rows += 1
			self.actionstable.resize(rows,cols)
		button = gtk.Button()
		button.mixdownaction = action
		action.button = button
		action.update_button()
		button.connect("clicked", self.ConfigureButton)
		self.actionstable.attach(button,0,1,rows-1,rows)
		buttondel = gtk.Button(stock=gtk.STOCK_DELETE)
		buttondel.mixdownaction = action
		buttondel.connect("clicked", self.DeleteButton)
		buttondel.actionbutton = button
		if rows == 1:
			buttondel.set_sensitive(False) # you can't delete the first export
		self.actionstable.attach(buttondel,1,2,rows-1,rows)
		self.actionstable.show_all()
		self.actions.append(action)
	
	#_____________________________________________________________________

	def ConfigureButton(self, button):
		"""
		Called when the user clicks the button for an action, which
		pops its config window
		
		Parameters:
			button -- the button.
		"""
		button.mixdownaction.configure()

	#_____________________________________________________________________

	def DeleteButton(self, button):
		"""
		Called when the user clicks the delete button for an action, which
		removes that action
		
		Parameters:
			button -- the button.
		"""
		# remove the action from the list
		self.actions.remove(button.mixdownaction)
		# delete the action
		del(button.mixdownaction)
		# delete the buttons
		
		table = button.get_parent()
		actionbutton = button.actionbutton
		# walk through the table; when we find our button, delete it and
		# its associated action button, and then move everything up a row;
		# finally, resize the table to be one row smaller
		our_row = table.child_get_property(button, "top-attach")
		
		table.remove(button)
		table.remove(actionbutton)
		
		# move everything up a row
		# we do this by finding all the table's children which are in a row greater
		# than the buttons we've removed, and removing them too while stashing them
		# in a list. Then sort the list into incrementing row order, and finally
		# walk through the list readding them. We have to do this stupid dance
		# so that we readd them all in increasing row order, otherwise it'll 
		# possibly break by putting two things in a table cell, etc.
		removed_buttons_to_readd = []
		for c in table.get_children():
			this_child_row = table.child_get_property(c, "top-attach")
			this_child_col = table.child_get_property(c, "left-attach")
			if this_child_row > our_row:
				removed_buttons_to_readd.append((this_child_row - 1, this_child_col, c))
				table.remove(c)
		
		removed_buttons_to_readd.sort(cmp=lambda a,b: cmp(a[0],b[0]))
		
		for row_to_readd_to, col_to_readd_to, widget in removed_buttons_to_readd:
			table.attach(widget, col_to_readd_to, col_to_readd_to + 1,
													 row_to_readd_to, row_to_readd_to + 1)
		
		# finally resize the table down by one row
		rows = self.actionstable.get_property("n-rows")
		cols = self.actionstable.get_property("n-columns")
		rows -= 1
		self.actionstable.resize(rows,cols)
		

	#_____________________________________________________________________

	def OnAddStep(self, button):
		"""
		Called when the user clicks the "Add step" button to add a step
		
		Parameters:
			button -- the button
		"""
		active = self.combo_newstep.get_active()
		if active == 0: return
		action_class = self.possible_action_classes[active-1]
		# specialcase ExportAsFileType
		if action_class == MixdownProfiles.ExportAsFileType: 
			new_action = action_class(self.project)
		else:
			new_action = action_class()
		self.AddAction(new_action)
		
	#_____________________________________________________________________

	def OnClose(self, button):
		"""
		Called when the dialog gets closed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.window.destroy()
	
	#_____________________________________________________________________
	
	def OnMixdown(self, button):
		"""
		Called when the user clicks the Mix down button.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		# FIXME: show a progress bar in a window for these steps
		data = {}
		for a in self.actions:
			# FIXME: trap errors and abort if you find any
			a.run(data)
	
	#_____________________________________________________________________
	
	def OnSaveSettings(self, button):
		"""
		Called when the user clicks the Save these settings button.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""

		# create a window to ask for a title to save it as
		w = gtk.Window()
		vb = gtk.VBox()
		w.add(vb)
		vb.add(gtk.Label("Choose a name for this profile"))
		e = gtk.Entry()
		vb.add(e)
		bb = gtk.HButtonBox()
		savebtn = gtk.Button(stock=gtk.STOCK_SAVE)
		cancelbtn = gtk.Button(stock=gtk.STOCK_CANCEL)
		savebtn.connect("clicked", self.SaveProfile, e, w)
		cancelbtn.connect("clicked", lambda x:w.destroy())
		bb.add(savebtn)
		bb.add(cancelbtn)
		vb.add(bb)
		w.connect("delete_event", w.destroy)
		w.show_all()
		
	#_____________________________________________________________________
	
	def SaveProfile(self, button, entry, window):
		"""
		Called when the user clicks the Save button when naming the profile.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
			entry -- the entry in the save window.
			window -- the save window
		"""
		
		profile_title = entry.get_text()
		outputxmlitems = [a.serialise() for a in self.actions]
		outputxml = "<mixdownprofile>\n%s\n</mixdownprofile>" % '\n'.join(outputxmlitems)
		
		savefolder = os.path.expanduser('~/.jokosher/mixdownprofiles') # created by Globals
		profile_file = os.path.join(savefolder, profile_title)
		fp = open(profile_file, "w")
		fp.write(outputxml)
		fp.close()
		
		window.destroy()
	
	#_____________________________________________________________________

	def RestoreProfile(self, profile_title):
		"""
		Loads a previously saved profile.
		
		Parameters:
			profile_title -- a profile name
		"""
		savefolder = os.path.expanduser('~/.jokosher/mixdownprofiles') # created by Globals
		profile_file = os.path.join(savefolder, profile_title)
		from xml.dom import minidom
		dom = minidom.parse(profile_file)
		for el in dom.documentElement.childNodes:
			if el.nodeType == 1: # an element, not a text node
				action_name = el.nodeName
				action_obj = getattr(MixdownProfiles,action_name)
				# specialcase ExportAsFileType
				if action_obj == MixdownProfiles.ExportAsFileType:
					action = action_obj(self.project)
				else:
					action = action_obj()
				# now get all its saved properties
				for subel in el.childNodes:
					if subel.nodeType == 1:
						k = subel.nodeName
						if subel.childNodes:
							v = subel.firstChild.nodeValue
						else:
							v = ""
						action.config[k] = v
				# and add the action to this profile
				self.AddAction(action)

	#_____________________________________________________________________
	
#=========================================================================
