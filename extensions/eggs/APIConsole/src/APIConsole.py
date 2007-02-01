#	API Console
#	-----------
#	This extension is a simple Console for controlling jokosher via
#	the extension API. It is meant for developper use both internally
#	and externally for 3rd party extension devleloppers. Its fairly 
#	simple to use: just type in an API function name
#	(e.g. add_instrument("cello", "My Cello")) and hit enter. The
#	return value (if any) is prtined back at you. rinse and repeat

import Jokosher.Extension
import gtk
import gtk.glade
import os
import pkg_resources
import Globals

class APIConsole:
	EXTENSION_NAME = "API Console"
	EXTENSION_DESCRIPTION = "Offers a simple console to acces the Jokosher API"
	EXTENSION_VERSION = "0.0.1"
	
	def OnMenuItemClick(self,arg):
		xmlString = pkg_resources.resource_string(__name__,"APIConsole.glade")
		wTree = gtk.glade.xml_new_from_buffer(xmlString, len(xmlString),"APITestDialog")
		signal = {"on_Activate" : self.Execute}
		wTree.signal_autoconnect(signal)
		window = wTree.get_widget("APITestDialog")
		self.API.set_window_icon(window)
		self.command = wTree.get_widget("entry1")
		self.output = wTree.get_widget("textview1")
		self.scrollwindow = wTree.get_widget("scrolledwindow1")
		self.output_text = gtk.TextBuffer()
		self.output_text.insert_at_cursor("dir - a list of API functions\n" +
					"help <function> - show documentation for a function\n" +
					"clear - clear text buffer\n"
					"--------------------------------\n")
		self.output.set_buffer(self.output_text)
		self.output.scroll_mark_onscreen(self.output_text.get_insert())
		
		self.completion_model = gtk.ListStore(str)
		
		window.show_all()
	
	
	def Execute(self, arg):
		self.output_text.insert_at_cursor(">>>>"+self.command.get_text()+"\n")
		
		if self.command.get_text() == "dir" or self.command.get_text() == "ls":
			outputList = []
			for i in dir(self.API):
				i = getattr(self.API, i)
				if callable(i):
					outputList.append(i.__name__)
			self.output_text.insert_at_cursor("\n".join(outputList)+"\n\n")
					
		elif self.command.get_text().startswith("help"):
			cmd = self.command.get_text()[4:].strip()
			if hasattr(self.API, cmd):
				i = getattr(self.API, cmd)
				self.output_text.insert_at_cursor(i.__name__+":\n"+i.__doc__+"\n\n")
		
		elif self.command.get_text() == "clear":
			self.output_text.set_text("dir - a list of API functions\n" +
					"help <function> - show documentation for a function\n" +
					"clear - clear text buffer\n"
					"--------------------------------\n")
		
		else:
			try:
				rvalue = eval("self.API."+self.command.get_text())
				if rvalue:
					self.output_text.insert_at_cursor(str(rvalue)+"\n\n")
			except:
				self.output_text.insert_at_cursor("Malformed function call, unimplimented function, or some random exception!\n\n")
		
		self.command.set_text("")
		self.output.set_buffer(self.output_text)
		self.output.scroll_mark_onscreen(self.output_text.get_insert())
		
	#You know you're a Newfie when: You think the first day of salmon fishing season is a provincial holiday
	
	
	def startup(self, api):
		self.API = api
		self.menu_item = self.API.add_menu_item("API Console", self.OnMenuItemClick)

	def shutdown(self):
		self.menu_item.destroy()
