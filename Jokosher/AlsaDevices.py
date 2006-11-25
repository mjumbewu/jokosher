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
import gst
import Globals

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
		Globals.debug('Could not get the mixer for ALSA device %s, check your permissions' % device) #TODO: Raise an exception here and have a GUI dialog displayed
		recmixers = []
	
	alsamixer.set_state(gst.STATE_NULL)
	
	return recmixers

#_____________________________________________________________________

def GetRecordingSampleRate(device="default"):
	""" 
	   May return any of the following depending on the sound card:
	   1) an int representing the only supported sample rate
	   2) an IntRange class with IntRange.low and IntRange.high being the min and max sample rates
	   3) a list of ints representing all the supported sample rates
	"""
	element = gst.element_factory_make("alsasrc", "alsasrc")

	# must set proper device to get precise caps
	element.set_property("device", device)

	# open device (so caps are probed)
	element.set_state(gst.STATE_READY)
	pad = element.get_pad("src")
	caps = pad.get_caps()
	del pad

	val = None
	try:
		val = caps[0]["rate"]
	except KeyError:
		pass
		
	# clean up
	element.set_state(gst.STATE_NULL)
	del element
	
	return val
	
#_____________________________________________________________________

def GetChannelsOffered(device):
	#TODO: Quite a few assumptions here...
	src = gst.element_factory_make('alsasrc')
	src.set_property("device", device)
	src.set_state(gst.STATE_READY)
	
	try:
		#Assume the card only offers one src (we can't handle more anyway)
		for pad in src.src_pads():
			caps = pad.get_caps()
	except:
		Globals.debug("Couldn't get source pad for %s"%device)
		src.set_state(gst.STATE_NULL)
		return 0

	numChannels = caps[0]["channels"]
	if isinstance(numChannels, gst.IntRange):
		if numChannels.high > 20000:
			#Assume we're being given the max number of channels for gstreamer, so take low number
			numChannels = numChannels.low
		else:
			#Otherwise take the high number
			numChannels = numChannels.high

	if numChannels == 2:
		#Assume one stereo input
		numChannels = 1

	src.set_state(gst.STATE_NULL)
	return numChannels

if __name__ == "__main__":
	print GetRecordingSampleRate()
