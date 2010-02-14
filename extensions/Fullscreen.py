import Jokosher.Extension
import gtk

EXTENSION_NAME = "Fullscreen"
EXTENSION_DESCRIPTION = "Make the Jokosher window fullscreen"
EXTENSION_VERSION = "1"

API = None

def do_fullscreen(menu_item):
	if menu_item.get_active():
		API.jokosher.window.fullscreen()
	else:
		API.jokosher.window.unfullscreen()

def startup(api):
	global API
	API = api
	api.add_menu_item(gtk.CheckMenuItem("View Fullscreen"), do_fullscreen)
	
def shutdown():
	pass
