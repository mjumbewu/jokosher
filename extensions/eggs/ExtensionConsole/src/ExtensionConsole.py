#
#	Extension Console
#	-----------
#	A fully fleged python console with powerful features such as
#	tab completion which allows you access to the 
#	Jokosher extension API and the interal Jokosher code.
#-------------------------------------------------------------------------------

import Jokosher.Extension
import pyconsole, SearchDialog
import pkg_resources
import pango
import gtk
import sys

#=========================================================================

class ExtensionConsole:
	
	EXTENSION_NAME = "Extension Console"
	EXTENSION_DESCRIPTION = "A fully functional python console with access to the extension API and the Jokosher internals"
	EXTENSION_VERSION = "1.1"
	
	CONSOLE_BANNER = "Jokosher Extension Console"
	
	#_____________________________________________________________________
	
	def startup(self, api):
		"""
		Initializes the extension.
		
		Parameters:
			api -- reference to the Jokosher extension API.
		"""
		self.api = api
		self.menuItem = self.api.add_menu_item("Extension Console", self.OnMenuItemClick)
		
		xmlString = pkg_resources.resource_string(__name__, "ConsoleDialog.ui")
		self.gtkBuilder = gtk.Builder()
		self.gtkBuilder.add_from_string(xmlString)
		
		self.savedStdin = sys.stdin
		sys.stdin = StdinWrapper()
		
		self.signals = {
			"OnClose" : self.OnClose,
			"OnSearch" : self.OnSearch,
		}
		
		self.gtkBuilder.connect_signals(self.signals)
		
		#the default namespace for the console
		self.namespace = {
				"jokosher": self.api.mainapp,
				"api": self.api
		}
		
		self.window = self.gtkBuilder.get_object("ConsoleDialog")
		self.vbox = self.gtkBuilder.get_object("ConsoleVBox")
		self.search = None
		self.swin = gtk.ScrolledWindow()
		self.swin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.vbox.pack_start(self.swin)
		
		self.console = pyconsole.Console(banner=self.CONSOLE_BANNER,
				use_rlcompleter=False,
				locals=self.namespace)
		self.console.modify_font(pango.FontDescription("Monospace"))
		
		self.swin.add(self.console)
		self.window.hide()

	#_____________________________________________________________________

	def shutdown(self):
		"""
		Destroys any object created by the extension when it is disabled.
		"""
		self.window.destroy()
		sys.stdin = self.savedStdin

	#_____________________________________________________________________
	
	def OnMenuItemClick(self, menuItem):
		"""
		Called when the user clicks on this extension's menu item.
		
		Parameters:
			menuItem -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		self.window.show_all()
	
	#_____________________________________________________________________
	
	def OnClose(self, widget, event=None):
		"""
		Called when the user clicks on the close button either in the
		dialog, or on the window decorations.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		self.window.hide()
		return True
		
	#_____________________________________________________________________
	
	def OnSearch(self, widget, event=None):
		"""
		Called when the user clicks on the search button.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		if self.search:
			self.search.dlg.present()
		else:
			self.search = SearchDialog.SearchDialog(self.window, self.console.get_buffer().insert_at_cursor)
		return True
	#_____________________________________________________________________

#=========================================================================

class StdinWrapper:
	def __getattr__(self, attr):
		raise pyconsole.StdinError
		
#=========================================================================
