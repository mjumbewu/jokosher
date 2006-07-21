import dbus
import gst, gst.interfaces
	
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
	alsamixer = gst.element_factory_make('alsamixer')
	alsamixer.set_property('device', device)
	alsamixer.set_state(gst.STATE_PAUSED)
	
	if alsamixer.implements_interface(gst.interfaces.Mixer):
		for track in alsamixer.list_tracks():
			#Check for recordinging status
			if track.flags & gst.interfaces.MIXER_TRACK_INPUT and track.flags & gst.interfaces.MIXER_TRACK_RECORD:
				# Ignore 'Capture' channel due to it being a requirement for recording on most low-end cards
				if (track.label != 'Capture'):
					recmixers.append(track)
				else:
					print ('Could not get the mixer for ALSA device %s, check your permissions' % (device,))
					recmixers = []
	
	alsamixer.set_state(gst.STATE_NULL)
	
	return recmixers
