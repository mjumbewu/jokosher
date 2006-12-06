#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	AddInstrumentDialog.py
#	
#	This module handles the dialog for adding instruments to a project. Don't
#	you just love instruments. We do. In fact, I suspect Laszlo has printed a
#	picture of the dialog box out and sleeps next to it.
#
#-------------------------------------------------------------------------------

import gtk.glade
import Globals
import textwrap
import gettext
_ = gettext.gettext


#=========================================================================

class AddInstrumentDialog:
	""" This class handles all of the processing associated with the
		Add Instrument dialog.
	"""	
	#_____________________________________________________________________

	def __init__(self, project, parent, instr=None):
		self.parent = parent
		self.project = project
		self.instr = instr

		self.res = gtk.glade.XML(Globals.GLADE_PATH, "AddInstrumentDialog")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
			"on_instrument_search_changed" : self.OnSearchChange,
		}
		
		self.res.signal_autoconnect(self.signals)
		
		self.dlg = self.res.get_widget("AddInstrumentDialog")
		self.tree = self.res.get_widget("Instruments")
		self.search_entry = self.res.get_widget("instrument_search")
		self.okbutton = self.res.get_widget("okButton")
		self.okbutton.set_sensitive(False)
		
		if self.instr: 
			self.dlg.set_title(_("Change Instrument Type"))
			self.res.get_widget("instructions").set_text(
					  _("Choose the new instrument type for %s") % self.instr.name)
			self.okbutton.set_label("gtk-ok")

		

		self.tree.connect("item-activated", self.OnSelected)
		self.tree.connect("selection-changed", self.OnSelectionChanged)

		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
			
		for i in Globals.getCachedInstruments():
			lineList = [x.center(12) for x in textwrap.wrap(i[0], 11)]
			j = "\n".join(lineList)
			self.model.append((j, i[1], i[2]))
		
		self.tree.set_model(self.model)
			
		self.tree.set_text_column(0)
		self.tree.set_pixbuf_column(2)
		self.tree.set_orientation(gtk.ORIENTATION_VERTICAL)
		self.tree.set_selection_mode(gtk.SELECTION_MULTIPLE)
		self.tree.set_item_width(90)
		self.tree.set_size_request(72, -1)
		self.dlg.resize(350, 300)
		
		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)
		#FIXME: the following lines are a workaround for bug 70799
		#Also glade file changed to make dialog initially invisible
		#otherwise it appears in the original place, then moves
		x, y = self.dlg.get_position()
		self.dlg.move(x, y + 25)
		self.dlg.show()
		#end FIXME:
	#_____________________________________________________________________
	
	def OnSelected(self, iconview, path):
		"""An instrument is selected"""
		
		self.OnOK()

	#_____________________________________________________________________
			
	def OnOK(self, button=None):
		"""OK pushed on the dialog"""
		
		sel = self.tree.get_selected_items()
		if not self.instr:
			for i in sel:
				item = self.model[i[0]]
				#find the actual instrument using index 1 (the instrument type)
				#because the name has been wrapped in self.model and can't be used
				instrItem = [x for x in Globals.getCachedInstruments() if x[1] == item[1]][0]
				self.project.AddInstrument(*instrItem)
		else:
			item = self.model[sel[0][0]]
			instrItem = [x for x in Globals.getCachedInstruments() if x[1] == item[1]][0]
			self.instr.ChangeType(instrItem[1], instrItem[0])

		self.parent.UpdateDisplay()
		self.dlg.destroy()
		
	#_____________________________________________________________________
	
	def OnCancel(self, button):
		"""Cancel button is pressed"""
		
		self.dlg.destroy()
		
	#_____________________________________________________________________

	def OnSelectionChanged(self, button):
		"""If a new instrument icon is chosen, this method is called"""
		sel = self.tree.get_selected_items()

		if len(sel) <= 0:
			self.okbutton.set_sensitive(False)
		else:
			self.okbutton.set_sensitive(True)
			
	#_____________________________________________________________________
	
	def OnSearchChange(self, widget):
		"""A new letter is added to the search box, so update the search"""
		
		search_text = self.search_entry.get_text()
		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
		
		for i in Globals.getCachedInstruments():
			if search_text.lower() in i[0].lower():
				self.model.append(i)
		
		self.tree.set_model(self.model)
		
	#_____________________________________________________________________

#=========================================================================
