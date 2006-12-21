import Jokosher.Extension
import gobject
import dbus
import dbus.service
#if we are using the old version of dbus, we need dbus's glib too.
if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
	import dbus.glib

# Extension meta information
EXTENSION_NAME = "Jokosher DBus API"
EXTENSION_DESCRIPTION = "Allows other processes to call Jokosher extension API functions using DBus"
EXTENSION_VERSION = "0.1"

# Extension constants
JOKOSHER_DBUS_PATH = "/org/gnome/Jokosher"
JOKOSHER_DBUS_NAME = "org.gnome.Jokosher"

class HelloWorldObject(dbus.service.Object):
	def __init__(self, bus_name, object_path=JOKOSHER_DBUS_PATH):
		dbus.service.Object.__init__(self, bus_name, object_path)

	## DBus API Methods ##
	#_______________________________________
	@dbus.service.method(JOKOSHER_DBUS_NAME)
	def play(self):
		API.play()
	
	@dbus.service.method(JOKOSHER_DBUS_NAME)	
	def stop(self):
		API.stop()
		
	## DBus API Signals ##
	#_______________________________________
	@dbus.service.signal(JOKOSHER_DBUS_NAME)
	def signal_play(self, message):
		pass	
	
	@dbus.service.signal(JOKOSHER_DBUS_NAME)
	def signal_stop(self, message):
		pass


#initialize the extension
def startup(api):
	global API, dbusObject
	API = api
	session_bus = dbus.SessionBus()
	bus_name = dbus.service.BusName('org.gnome.Jokosher', bus=session_bus)
	dbusObject = HelloWorldObject(bus_name)

#disable/shutdown the extension
def shutdown():
	#TODO, remove the org.gnome.Jokosher dbus service
	pass