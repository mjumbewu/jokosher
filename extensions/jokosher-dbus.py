import Jokosher.Extension
import gobject
import dbus
import dbus.service
if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
    import dbus.glib

class HelloWorldObject(dbus.service.Object):
    def __init__(self, bus_name, object_path='/org/gnome/Jokosher'):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method('org.gnome.Jokosher')
    def play(self):
        API.play()

def startup(api):
	global API
	API = api
	session_bus = dbus.SessionBus()
	bus_name = dbus.service.BusName('org.gnome.Jokosher', bus=session_bus)
	object = HelloWorldObject(bus_name)
