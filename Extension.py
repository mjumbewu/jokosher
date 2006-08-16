# The Jokosher Extension API
# write proper docstrings so that we can autogenerate the docs

import os, sys, gtk, imp
import gettext
_ = gettext.gettext

# Define some constants
PLUGIN_DIR_USER = os.path.expanduser('~/.jokosher/extensions/')
PLUGIN_DIRS = [PLUGIN_DIR_USER, '/usr/lib/jokosher/extensions/']
# add your own plugin dirs with envar JOKOSHER_PLUGIN_DIRS, colon-separated
OVERRIDE_PLUGIN_DIRS = os.environ.get('JOKOSHER_EXTENSION_DIRS','')
if OVERRIDE_PLUGIN_DIRS:
  PLUGIN_DIRS = OVERRIDE_PLUGIN_DIRS.split(':') + PLUGIN_DIRS
PREFERRED_PLUGIN_DIR = PLUGIN_DIRS[0]

RESP_INSTALL = 9999
RESP_REPLACE = 9998

# Work out whether I'm being imported by a plugin that's being run directly
# or whether I'm being imported by a plugin run by Jokosher
import inspect
plugin_that_imported_me = inspect.currentframe().f_back
try:
  thing_that_imported_plugin = plugin_that_imported_me.f_back 
except:
  pass
	
if thing_that_imported_plugin is None and \
 os.path.split(plugin_that_imported_me.f_code.co_filename)[1] != 'JokosherApp.py':
	# the plugin is being run directly; pop up the error 
	try:
		import gtk
	except:
		# no Gtk either! Print a message and die
		import sys
		print "This is a Jokosher plugin; it is not meant to be run directly."
		print "To install it, move it to the directory %s\nand run Jokosher." % (
		  PLUGIN_DIR_LOCAL)
		sys.exit(1)
	d = gtk.MessageDialog(message_format="This is a Jokosher plugin, which needs "+\
	                      "to be installed. Would you like to install it?",
	                      type=gtk.MESSAGE_ERROR)
	d.add_buttons(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,'Install',RESP_INSTALL)
	d.set_default_response(RESP_INSTALL)
	ret = d.run()
	d.destroy()
	if ret == RESP_INSTALL:
		plugin_path_and_file = plugin_that_imported_me.f_globals['__file__']
		plugin_file_name = os.path.split(plugin_path_and_file)[1]
		new_plugin_path_and_file = os.path.join(PREFERRED_PLUGIN_DIR,plugin_file_name)
		if os.path.exists(new_plugin_path_and_file):
			d = gtk.MessageDialog(message_format="You already have a plugin with "+\
		                       "the name %s installed; would you like to " +\
		                       "replace it?" % os.path.splitext(plugin_file_name)[0],
		                       type=gtk.MESSAGE_QUESTION)
			d.add_buttons(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,'Replace',RESP_REPLACE)
			d.set_default_response(RESP_REPLACE)
			ret = d.run()
			d.destroy()
			if ret <> RESP_REPLACE:
				sys.exit(0)
		# confirm that the new path exists!
		try:
			os.makedirs(os.path.split(new_plugin_path_and_file)[0])
		except:
			pass # already exists
		# and move the plugin
		os.rename(plugin_path_and_file, new_plugin_path_and_file)
		d = gtk.MessageDialog(message_format="Your new plugin is now available in "+\
		                      "Jokosher!",buttons=gtk.BUTTONS_OK)
		d.destroy()
		sys.exit(0)

############################################################################
############# The actual plugin API ########################################
############################################################################

class ExtensionAPI:
	def __init__(self):
		pass
		
	def add_menu_item(self, menu_item_name, callback_function):
		"Adds a menu item to a Jokosher menu."
		extensions_menu = self.mainapp.wTree.get_widget("extensionsmenu").get_submenu()
		new_menu_item = gtk.MenuItem(menu_item_name)
		new_menu_item.connect("activate", callback_function)
		extensions_menu.prepend(new_menu_item)


def LoadAllExtensions():
	for d in PLUGIN_DIRS:
		if not os.path.isdir(d): continue
		for f in os.listdir(d):
			fn,ext = os.path.splitext(f)
			if ext == ".py":
				print "importing extension",f,
				fil, filename, description = imp.find_module(fn, [d])
				try:
					try:
						m = imp.load_module(fn, fil, filename, description)
						print "done."
					except:
						print "failed."
				finally:
					if fil: fil.close()
				try:
					m.startup(API)
				except:
					pass
		
API = ExtensionAPI()
