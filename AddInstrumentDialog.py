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

import gtk
import gtk.glade
import gobject
import os
from ConfigParser import SafeConfigParser
import Globals
import locale, gettext

#=========================================================================

class AddInstrumentDialog:
	""" This class handles all of the processing associated with the
		Add Instrument dialog.
	"""	
	#_____________________________________________________________________

	def __init__(self, project, parent):
		self.parent = parent
		self.project = project
		
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

		self.tree.connect("item-activated", self.OnSelected)
		self.tree.connect("selection-changed", self.OnSelectionChanged)

		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
			
		for i in getCachedInstruments():
			self.model.append(i)
		
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
		
	#_____________________________________________________________________
	
	def OnSelected(self, iconview, path):
		"""An instrument is selected"""
		
		self.OnOK()

	#_____________________________________________________________________
			
	def OnOK(self, button=None):
		"""OK pushed on the dialog"""
		
		sel = self.tree.get_selected_items()
		for i in sel:
			currentItem = self.model[i[0]]
			self.project.AddInstrument(currentItem[0], currentItem[1], currentItem[2])
	
		self.parent.UpdateDisplay()
		self.parent.undo.set_sensitive(True)
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
		
		for i in getCachedInstruments():
			if search_text.lower() in i[0].lower():
				self.model.append(i)
		
		self.tree.set_model(self.model)
		
	#_____________________________________________________________________

#=========================================================================
#static list of all the instrument files (to prevent having to reimport files)
instrumentPropertyList = []

def _cacheInstruments():
	"""The current list of instruments, cached"""
	
	global instrumentPropertyList

	if len(instrumentPropertyList) > 0:
		return
		
	basepath = os.path.dirname(os.path.abspath(__file__))
	instrpath = os.path.join(basepath, "Instruments")
	
	files = os.walk(instrpath).next()[2]
	instrFiles = [x for x in files if x.endswith(".instr")]
	for f in instrFiles:
		config = SafeConfigParser()
		config.read(os.path.join(instrpath, f))
		
		if config.has_option('core', 'type') and config.has_option('core', 'icon'):
			icon = config.get('core', 'icon')
			type = config.get('core', 'type')
		else:
			continue
		
		#getlocale() will usually return  a tuple like: ('en_GB', 'UTF-8')
		lang = locale.getlocale()[0]
		if config.has_option('i18n', lang):
			name = config.get('i18n', lang)
		elif config.has_option('i18n', lang.split("_")[0]):
			#in case lang was 'de_DE', use only 'de'
			name = config.get('i18n', lang.split("_")[0])
		elif config.has_option('i18n', 'en'):
			#fall back on english (or a PO translation, if there is any)
			name = gettext.gettext(config.get( 'i18n', 'en'))
		else:
			continue
		
		pixbufPath = os.path.join(instrpath, "images", icon)
		pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
		
		instrumentPropertyList.append((name, type, pixbuf))
	
	#sort the instruments alphabetically
	#using the lowercase of the name (at index 0)
	instrumentPropertyList.sort(key=lambda x: x[0].lower())
	
def getCachedInstruments():
	"""Update the instrument cache"""
	
	global instrumentPropertyList
	if len(instrumentPropertyList) == 0:
		_cacheInstruments()
	return instrumentPropertyList

gobject.idle_add(_cacheInstruments)
