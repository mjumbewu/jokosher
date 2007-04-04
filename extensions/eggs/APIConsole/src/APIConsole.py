#
#	API Console
#	-----------
#	This extension is a simple Console for controlling jokosher via
#	the extension API. It is meant for developper use both internally
#	and externally for 3rd party extension devleloppers. Its fairly 
#	simple to use: just type in an API function name
#	(e.g. add_instrument("cello", "My Cello")) and hit enter. The
#	return value (if any) is prtined back at you. rinse and repeat
#
#-------------------------------------------------------------------------------

import Jokosher.Extension
import gtk
import gtk.glade
import os
import pkg_resources
import Globals

#=========================================================================

class APIConsole:
	"""
	Displays a terminal to execute Jokosher Extension API commands.
	"""
	
	EXTENSION_NAME = "API Console"
	EXTENSION_DESCRIPTION = "Offers a simple console to acces the Jokosher API"
	EXTENSION_VERSION = "0.0.1"
	
	#_____________________________________________________________________
	
	def startup(self, api):
		"""
		Initializes the extension.
		
		Parameters:
			api -- reference to the Jokosher extension API.
		"""
		self.api = api
		self.history = []
		self.historyIndex = 0
		self.menu_item = self.api.add_menu_item("API Console", self.OnMenuItemClick)
		self.defaultOutput = "dir - a list of api functions\n" + \
					"help <function> - show documentation for a function\n" + \
					"clear - clear text buffer\n" + \
					"exit - close the API Console\n" + \
					"------------------------------------\n"

	#_____________________________________________________________________

	def shutdown(self):
		"""
		Destroys any object created by the extension when it is disabled.
		"""
		self.menu_item.destroy()

	#_____________________________________________________________________
	
	def OnMenuItemClick(self, menuItem):
		"""
		Called when the user clicks on this extension's menu item.
		
		Parameters:
			menuItem -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		xmlString = pkg_resources.resource_string(__name__,"APIConsole.glade")
		wTree = gtk.glade.xml_new_from_buffer(xmlString, len(xmlString),"APITestDialog")
		
		signals = 	{
					"on_Activate" : self.Execute,
					"on_entryCommand_key_press_event" : self.OnKeyPressCommand
					}
		wTree.signal_autoconnect(signals)
		
		self.window = wTree.get_widget("APITestDialog")
		self.command = wTree.get_widget("entryCommand")
		self.output = wTree.get_widget("textviewOutput")
		self.scrollwindow = wTree.get_widget("scrolledwindow")
		
		self.api.set_window_icon(self.window)
		self.output_text = gtk.TextBuffer()
		self.output_text.insert_at_cursor(self.defaultOutput)
		self.output.set_buffer(self.output_text)
		self.output.scroll_mark_onscreen(self.output_text.get_insert())
		
		self.completion_model = gtk.ListStore(str)
		
		self.window.show_all()
	
	#_____________________________________________________________________
	
	def OnKeyPressCommand(self, widget, event):
		"""
		Called when the user presses a key in the command entry.
		Used for manipulating the command history.
		
		Parameters:
			widget -- GTK widget firing this event.
			event -- keyboard event fired.
			
		Returns:
			True -- stop GTK signal propagation.
			False -- continue GTK signal propagation.
		"""
		if event.keyval == 65362:		# up arrow: show the previous command in the history
			if len(self.history) > 0 and self.historyIndex+1 < len(self.history):
				self.historyIndex += 1
				self.command.set_text(self.history[self.historyIndex])
			return True
		
		elif event.keyval == 65364:		# down arrow: show the next command in the history
			if len(self.history) > 0 and self.historyIndex-1 >= -1:
				self.historyIndex -= 1
				
				if self.historyIndex >= 0:
					self.command.set_text(self.history[self.historyIndex])
				else:
					self.command.set_text("")
			return True
		
		elif event.keyval == 65293:		# enter key: create a new history entry and reset the index
			self.historyIndex = -1
			self.history.insert(0, self.command.get_text())
			return False
		
		else:
			return False
	
	#_____________________________________________________________________
	
	def Execute(self, entry):
		"""
		Executes the command given by the user.
		
		Parameters:
			entry -- GTK callback parameter.
		"""
		self.output_text.insert_at_cursor(">%s\n" % self.command.get_text())
		
		if self.command.get_text() == "dir" or self.command.get_text() == "ls":
			outputList = []
			for method in dir(self.api):
				method = getattr(self.api, method)
				if callable(method):
					outputList.append(method.__name__)
			self.output_text.insert_at_cursor("\n".join(outputList) + "\n\n")
					
		elif self.command.get_text().startswith("help"):
			cmd = self.command.get_text()[4:].strip()
			if hasattr(self.api, cmd):
				method = getattr(self.api, cmd)
				self.output_text.insert_at_cursor("%s:\n%s\n\n" % (method.__name__, method.__doc__))
		
		elif self.command.get_text() == "clear":
			self.output_text.set_text(self.defaultOutput)
		
		elif self.command.get_text() == "exit":
			self.window.destroy()
			
		else:
			try:
				rvalue = eval("self.api.%s" % self.command.get_text())
				if rvalue:
					self.output_text.insert_at_cursor(str(rvalue) + "\n\n")
			except Exception, e:
				self.output_text.insert_at_cursor("Exception caught:\n%s\n\n" % e)
		
		self.command.set_text("")
		self.output.set_buffer(self.output_text)
		self.output.scroll_mark_onscreen(self.output_text.get_insert())
		
	#_____________________________________________________________________
	
	#You know you're a Newfie when: You think the first day of salmon fishing season is a provincial holiday

#=========================================================================
