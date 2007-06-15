#
#	Extension Console
#	-----------
#	A fully fleged python console with powerful features such as
#	tab completion which allows you access to the 
#	Jokosher extension API and the interal Jokosher code.
#-------------------------------------------------------------------------------

import Jokosher.Extension
import pyconsole
import pango
import gtk
import sys

#=========================================================================

class ExtensionConsole:
	
	EXTENSION_NAME = "Extension Console"
	EXTENSION_DESCRIPTION = "A fully functional python console with access to the extension API and the Jokosher internals"
	EXTENSION_VERSION = "1.0"
	
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
		
		self.savedStdin = sys.stdin
		sys.stdin = StdinWrapper()
		
		#the default namespace for the console
		self.namespace = {
				"jokosher": self.api.mainapp,
				"api": self.api
		}
		
		self.window = gtk.Window()
		self.window.set_title("Jokosher Extension Console")
		self.swin = gtk.ScrolledWindow()
		self.swin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.window.add(self.swin)
		
		self.console = pyconsole.Console(banner=self.CONSOLE_BANNER,
				use_rlcompleter=False,
				locals=self.namespace)
		self.console.modify_font(pango.FontDescription("Monospace"))
		
		self.swin.add(self.console)
		self.window.set_default_size(500, 400)
		self.window.connect("delete_event", self.OnClose)
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
	
	def OnClose(self, window, event):
		"""
		Called when the user clicks on this extension's menu item.
		
		Parameters:
			window -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		self.window.hide()
		return True
		
	#_____________________________________________________________________

#=========================================================================

class StdinWrapper:
	def __getattr__(self, attr):
		raise pyconsole.StdinError
		
#=========================================================================
