
import gtk
import gtk.glade
import gobject
import os
from ConfigParser import SafeConfigParser
import Globals
import operator #for sorting instrument list

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

		self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, str, str, str)
			
		for i in getCachedInstruments():
			self.model.append(i)
		
		self.tree.set_model(self.model)
			
		self.tree.set_text_column(0)
		self.tree.set_pixbuf_column(1)
		self.tree.set_orientation(gtk.ORIENTATION_VERTICAL)
		self.tree.set_selection_mode(gtk.SELECTION_MULTIPLE)
		self.tree.set_item_width(90)
		self.tree.set_size_request(72, -1)
		self.dlg.resize(350, 300)
		
		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)
		
	#_____________________________________________________________________
	
	def OnSelected(self, iconview, path):
		self.OnOK()

	#_____________________________________________________________________
			
	def OnOK(self, button=None):
		sel = self.tree.get_selected_items()
		for i in sel:
			currentItem = self.model[i[0]]
			
			filenameList = []
			for i in currentItem[3].split(","):
				filenameList.append(i.strip())
				
			if len(filenameList) == 1 and len(filenameList[0]) == 0:
				filenameList = []
				#this instrument has no imports, so add this instrument
				self.project.AddInstrument(currentItem[0], currentItem[1], currentItem[4])
		
			for k in instrumentPropertyList:
				if len(filenameList) == 0:
					break
				if k[2] in filenameList:
					self.project.AddInstrument(k[0], k[1], k[4])
					filenameList.remove(k[2])
	
		self.parent.UpdateDisplay()
		self.parent.undo.set_sensitive(True)
		self.dlg.destroy()
		
	#_____________________________________________________________________
	
	def OnCancel(self, button):
		self.dlg.destroy()
		
	#_____________________________________________________________________

	def OnSelectionChanged(self, button):
		sel = self.tree.get_selected_items()

		if len(sel) <= 0:
			self.okbutton.set_sensitive(False)
		else:
			self.okbutton.set_sensitive(True)
			
	#_____________________________________________________________________
	
	def OnSearchChange(self, widget):
		search_text = self.search_entry.get_text()
		self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, str, str, str)
		
		for i in getCachedInstruments():
			if search_text.lower() in i[0].lower():
				self.model.append(i)
		
		self.tree.set_model(self.model)
		
	#_____________________________________________________________________

#=========================================================================
#static list of all the instrument files (to prevent having to reimport files)
instrumentPropertyList = []

def _cacheInstruments():
	global instrumentPropertyList

	if len(instrumentPropertyList) > 0:
		return
		
	basepath = os.path.dirname(os.path.abspath(__file__))
	instrpath = os.path.join(basepath, "Instruments")
	
	for path,dirs,files in os.walk(instrpath):
		for f in files:
			if f[-6:] == ".instr":
				config = SafeConfigParser()
				config.read(os.path.join(instrpath, f))
				
				if config.has_option('core', 'name') and config.has_option('core', 'icon'):
					name = config.get('core', 'name')
					icon = config.get('core', 'icon')
				else:
					continue
				
				pixbufPath = os.path.join(instrpath, "images", icon)
				pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
	
				if config.has_option('core', 'import'):
					importfiles = config.get('core', 'import')
				else:
					importfiles = ""
				
				instrumentPropertyList.append((name, pixbuf, f, importfiles, pixbufPath))
	
	#sort the instruments alphabetically
	#using the name (at index 0)
	instrumentPropertyList.sort(key=operator.itemgetter(0))
	
def getCachedInstruments():
	global instrumentPropertyList
	if len(instrumentPropertyList) == 0:
			_cacheInstruments()
	return instrumentPropertyList

gobject.idle_add(_cacheInstruments)
