import dbus
try:
	import alsaaudio
except:
	# we warn about this in Project.CheckGstreamerVersions
	pass
	
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

	lastmixer = None
	for mixer in mixers:
		try:
			#We may get more than one mixer with the same name, these have incremental IDs. I'm assuming they always appear consecutively within the mixers() list (empirical evidence supports this)
			if lastmixer == mixer:
				id += 1
			else:
				id = 0
			mixdev = alsaaudio.Mixer(mixer, id, device)
			#Ignore 'Capture' channel due to it being a requirement for recording on most low-end cards
			if mixdev.getrec() == [0, 0] and mixdev.mixer() != 'Capture':
				recmixers.append(mixdev)
		except alsaaudio.ALSAAudioError:
			pass

	print device, recmixers
	return recmixers
