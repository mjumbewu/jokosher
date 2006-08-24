# The Jokosher Extension API
# write proper docstrings so that we can autogenerate the docs

import os, sys, gtk, imp
import gettext
_ = gettext.gettext

# Define some constants
EXTENSION_DIR_USER = os.path.expanduser('~/.jokosher/extensions/')
EXTENSION_DIRS = [EXTENSION_DIR_USER, '/usr/lib/jokosher/extensions/']
# add your own extension dirs with envar JOKOSHER_EXTENSION_DIRS, colon-separated
OVERRIDE_EXTENSION_DIRS = os.environ.get('JOKOSHER_EXTENSION_DIRS','')
if OVERRIDE_EXTENSION_DIRS:
	EXTENSION_DIRS = OVERRIDE_EXTENSION_DIRS.split(':') + EXTENSION_DIRS
PREFERRED_EXTENSION_DIR = EXTENSION_DIRS[0]

RESP_INSTALL = 9999
RESP_REPLACE = 9998

# Work out whether I'm being imported by a extension that's being run directly
# or whether I'm being imported by a extension run by Jokosher
import inspect
extension_that_imported_me = inspect.currentframe().f_back
try:
	thing_that_imported_extension = extension_that_imported_me.f_back 
except:
	thing_that_imported_extension = None
	
if thing_that_imported_extension is None and \
			os.path.split(extension_that_imported_me.f_code.co_filename)[1] != 'JokosherApp.py':
	# the extension is being run directly; pop up the error 
	try:
		import gtk
	except:
		# no Gtk either! Print a message and die
		import sys
		print "This is a Jokosher extension; it is not meant to be run directly."
		print "To install it, move it to the directory %s\nand run Jokosher." % (EXTENSION_DIR_LOCAL)
		sys.exit(1)
	d = gtk.MessageDialog(message_format="This is a Jokosher extension, which needs "+\
	                      "to be installed. Would you like to install it?",
	                      type=gtk.MESSAGE_ERROR)
	d.add_buttons(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,'Install',RESP_INSTALL)
	d.set_default_response(RESP_INSTALL)
	ret = d.run()
	d.destroy()
	if ret == RESP_INSTALL:
		extension_path_and_file = extension_that_imported_me.f_globals['__file__']
		extension_file_name = os.path.split(extension_path_and_file)[1]
		new_extension_path_and_file = os.path.join(PREFERRED_EXTENSION_DIR, extension_file_name)
		if os.path.exists(new_extension_path_and_file):
			d = gtk.MessageDialog(message_format="You already have a extension with "+\
					"the name %s installed; would you like to " +\
					"replace it?" % os.path.splitext(extension_file_name)[0],
					type=gtk.MESSAGE_QUESTION)
			d.add_buttons(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,'Replace',RESP_REPLACE)
			d.set_default_response(RESP_REPLACE)
			ret = d.run()
			d.destroy()
			if ret <> RESP_REPLACE:
				sys.exit(0)
		# confirm that the new path exists!
		try:
			os.makedirs(os.path.split(new_extension_path_and_file)[0])
		except:
			pass # already exists
		# and move the extension
		os.rename(extension_path_and_file, new_extension_path_and_file)
		d = gtk.MessageDialog(message_format="Your new extension is now available in "+\
		                      "Jokosher!",buttons=gtk.BUTTONS_OK)
		d.destroy()
		sys.exit(0)

############################################################################
############# The actual extension API ########################################
############################################################################

class ExtensionAPI:
	def __init__(self, mainapp):
		self.mainapp = mainapp
		
	def add_menu_item(self, menu_item_name, callback_function):
		"""
		   Adds a menu item to a Jokosher extension menu.
		"""
		extensions_menu = self.mainapp.wTree.get_widget("extensionsmenu").get_submenu()
		new_menu_item = gtk.MenuItem(menu_item_name)
		new_menu_item.connect("activate", callback_function)
		extensions_menu.prepend(new_menu_item)
	
	def play(self, play_state=True):
		"""
		   If play_state is True, it will play the project from the beginning.
		   Otherwise, it will stop all playing.
		"""
		#Stop current playing (if any) and set to playhead to the beginning
		self.mainapp.Stop()
		if play_state:
			#Commence playing
			self.mainapp.Play()
		
	def stop(self):
		"""
		   Stops the project if it is currently playing.
		   Same as play(play_state=False)
		"""
		self.mainapp.Stop()
		
	def add_file_to_selected_instrument(self, uri):
		"""
		   Creates a new event from the file at the given URI and 
		   adds it to the first selected instrument.
		   Return values:
		   0: success
		   1: bad URI or file could not be loaded
		   2: no instrument selected
		"""
		instr = None
		for i in self.mainapp.project.instruments:
			if i.isSelected:
				instr = i
				break
		
		if not instr:
			#No instrument selected
			return 2
		
		instr.addEventFromFile(0, uri)
		#TODO: find out if the add failed and return 1
		return 0


def LoadAllExtensions():
	for exten_dir in EXTENSION_DIRS:
		if not os.path.isdir(exten_dir):
			continue
		for f in os.listdir(exten_dir):
			fn, ext = os.path.splitext(f)
			if ext == ".py":
				print "importing extension", f,
				exten_file, filename, description = imp.find_module(fn, [exten_dir])
				
				try:
					module = imp.load_module(fn, exten_file, filename, description)
					print "done."
				except:
					print "failed."
				if exten_file:
					exten_file.close()
				
				try:
					module.startup(API)
				except:
					pass
		
API = None
