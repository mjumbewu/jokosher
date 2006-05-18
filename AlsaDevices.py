import dbus

def GetAlsaList(type):
	#Get HAL Manager
	bus = dbus.SystemBus()
	object = bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager")
	manager = dbus.Interface(object, "org.freedesktop.Hal.Manager")
	
	found = {}
	devices = manager.FindDeviceStringMatch("alsa.type", type)
	found["Default"] = "default"
	for device in devices:
		device_object = bus.get_object("org.freedesktop.Hal", device)
		properties = device_object.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
		name = properties["alsa.device_id"]
		cardnum = "hw:" + str(properties["alsa.card"])
		found[name] = cardnum
		
	return found
