import dbus
import alsaaudio

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
		#Avoid duplicate entries
		if cardnum not in found.values():
			found[name] = cardnum
		
	return found

def GetRecordingMixers(device):
	"""Returns a list containing all the channels which have recording switched on."""
	
	recmixers = []
	mixers = alsaaudio.mixers(device)

	for mixer in mixers:
		mixdev = alsaaudio.Mixer(mixer)
		try:
			#Ignore 'Capture' channel due to it being a requirement for recording on most low-end cards
			if mixdev.getrec() == [0, 0] and mixdev.mixer() != 'Capture':
				recmixers.append(mixdev)
		except alsaaudio.ALSAAudioError:
			pass

	return recmixers
