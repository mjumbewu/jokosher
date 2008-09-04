#
#		THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#		THE 'COPYING' FILE FOR DETAILS
#
#		AudioBackend.py
#
#		This file offers functions to retrieve information about the
#		audio devices available with the current audio backend, and
#		the capabilities that those devices support.
#
#-------------------------------------------------------------------------------

import gst, gobject
import Globals

#=========================================================================

def ListPlaybackDevices(sink=None, probe_name=True):
	if not sink:
		# get preference from Globals
		sink = Globals.settings.playback["audiosink"]
		
	try:
		bin = gst.parse_bin_from_description(sink, False)
	except gobject.GError, gst.ElementNotFoundError:
		Globals.debug("Cannot list playback devices: cannot parse bin", sink)
		return list()
	
	try:
		element = bin.sinks().next()
	except StopIteration:
		Globals.debug("Cannot list playback devices: no sink device in the bin", sink)
		
	return ListDeviceProbe(element, probe_name)
	
#_____________________________________________________________________
	
def ListCaptureDevices(src=None, probe_name=True):
	if not src:
		# get preference from Globals
		src = Globals.settings.recording["audiosrc"]
	try:
		bin = gst.parse_bin_from_description(src, False)
	except gst.ElementNotFoundError:
		Globals.debug("Cannot list capture devices: cannot parse bin", src)
		return list()
	
	try:
		element = bin.iterate_sources().next()
	except StopIteration:
		Globals.debug("Cannot list capture devices: no source device in the bin", src)
		
	return ListDeviceProbe(element, probe_name)
	
#_____________________________________________________________________

def ListDeviceProbe(element, probe_name):
	element_name = element.get_factory().get_property("name")
	dev_info_list = []
	
	element.set_state(gst.STATE_READY)
	
	if gobject.type_is_a(element, gst.interfaces.PropertyProbe) and hasattr(element.props, "device"):
		element.probe_property_name("device")
		devices = element.probe_get_values_name("device")
		
		if not "default" in devices:
			# assume default device is "default"
			dev_info_list.append(("default", ""))
		
		if probe_name and hasattr(element.props, "device-name"):
			for dev in devices:
				element.set_property("device", dev)
				name = element.get_property("device-name")
				dev_info_list.append((dev,name))
		else:
			for dev in devices:
				dev_info_list.append((dev,""))
	else:
		Globals.debug("Cannot list devices: property probe not supported on", element_name)
		
	element.set_state(gst.STATE_NULL)
	
	return dev_info_list

#_____________________________________________________________________

def GetRecordingSampleRate(device="hw:0"):
	""" 
	Checks for available recording sample rates.
	
	Parameters:
		device -- ALSA device to poll for values. "hw:0" by default.
	
	Returns:
		any of the following depending on the sound card:
		1) an int representing the only supported sample rate.
		2) an IntRange class with IntRange.low and IntRange.high being the min and max sample rates.
		3) a list of ints representing all the supported sample rates.
	"""
	return GetGstElementSampleRate("alsasrc", "src", device=device)
	
#_____________________________________________________________________

def GetGstElementSampleRate(elementName, padName, **properties):
	"""
	Checks for available sample rates for the given GStreamer element.
	
	Parameters:
		elementName -- the name of the gstreamer element (ie "alsasrc").
		padName -- the name of the pad to query ("src" or "sink").
		properties -- and properties to set on the element.
		
	Returns:
		any of the following depending on the gstreamer element:
		1) an int representing the only supported sample rate.
		2) an IntRange class with IntRange.low and IntRange.high being the min and max sample rates.
		3) a list of ints representing all the supported sample rates.
	"""
	element = gst.element_factory_make(elementName)

	for key, value in properties.iteritems():
		element.set_property(key, value)

	# open device (so caps are probed)
	element.set_state(gst.STATE_READY)

	try:
		caps = element.get_pad(padName).get_caps()
		val = caps[0]["rate"]
	except:
		val = None
		
	# clean up
	element.set_state(gst.STATE_NULL)
	del element
	
	return val

#_____________________________________________________________________

def GetChannelsOffered(device):
	"""
	Checks for the number of available channels on a device.
	
	Parameters:
		device -- ALSA device (e.g. hw:0) to poll for available channels.
		
	Returns:
		the number of channels available on a device.
	"""
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

"""
The following function, is meant for testing this file independantly from the rest.
"""
if __name__ == "__main__":
	print GetRecordingSampleRate()
