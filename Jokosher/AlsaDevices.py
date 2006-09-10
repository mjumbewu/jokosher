#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       AlsaDevices.py
#       
#       This file offers ALSA specific helper functions.
#
#-------------------------------------------------------------------------------


import dbus
import gst, gst.interfaces

#=========================================================================

def GetAlsaList(type):
	"""Returns a dictionary containing ALSA device names and their correspoding ALSA ids (e.g. hw:0).

	Keyword arguments:
	type -- specifies the type of ALSA device we are looking for, playback or capture."""

	#Get HAL Manager
	bus = dbus.SystemBus()
	object = bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager")
	manager = dbus.Interface(object, "org.freedesktop.Hal.Manager")
	
	found = {}
	#Find all alsa devices of the requested type
	devices = manager.FindDeviceStringMatch("alsa.type", type)
	#Add the ALSA default card to the list
	found["Default"] = "default"
	for device in devices:
		#Iterate through all the ALSA devices found and insert them in to a dictionary
		device_object = bus.get_object("org.freedesktop.Hal", device)
		properties = device_object.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
		name = properties["alsa.device_id"]
		cardnum = "hw:" + str(properties["alsa.card"]) #FIXME: This may cause problems with plughw devices
		#Avoid duplicate entries
		if cardnum not in found.values():
			found[name] = cardnum
		
	return found

 #_____________________________________________________________________

def GetRecordingMixers(device):
	"""Returns a list containing all the channels which have recording switched on.

	Keyword arguments:
	device -- specifies which ALSA device (e.g. hw:0) to return values for."""

	recmixers = []
	alsamixer = gst.element_factory_make('alsamixer')
	alsamixer.set_property('device', device)
	alsamixer.set_state(gst.STATE_PAUSED)
	
	if alsamixer.implements_interface(gst.interfaces.Mixer):
		for track in alsamixer.list_tracks():
			#Check for recordinging status
			if track.flags & gst.interfaces.MIXER_TRACK_INPUT and track.flags & gst.interfaces.MIXER_TRACK_RECORD:
				# Ignore 'Capture' channel due to it being a requirement for recording on most low-end cards
				if (track.label != 'Capture'): #FIXME: Can't use the word "Capture" explicitly, this string gets translated in non-english locales
					recmixers.append(track)
	else:
		print ('Could not get the mixer for ALSA device %s, check your permissions' % (device,)) #TODO: Raise an exception here and have a GUI dialog displayed
		recmixers = []
	
	alsamixer.set_state(gst.STATE_NULL)
	
	return recmixers
