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
	except (gobject.GError, gst.ElementNotFoundError):
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
	except (gobject.GError, gst.ElementNotFoundError):
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
	
	if hasattr(element.props, "device"):
		default_device = element.__class__.props.device.default_value
		if gobject.type_is_a(element, gst.interfaces.PropertyProbe):
			element.probe_property_name("device")
			devices = element.probe_get_values_name("device")
			
			if not default_device in devices:
				dev_info_list.append((default_device, ""))
			
			if probe_name and hasattr(element.props, "device-name"):
				for dev in devices:
					element.set_property("device", dev)
					
					element.set_state(gst.STATE_READY)
					# certain elements like pulsesrc won't load the device-name until STATE_READY
					name = element.get_property("device-name")
					element.set_state(gst.STATE_NULL)
					
					dev_info_list.append((dev,name))
			else:
				for dev in devices:
					dev_info_list.append((dev,""))
		else:
			dev_info_list.append((default_device, ""))
	else:
		Globals.debug("Cannot list devices: property probe not supported on", element_name)
		
	return dev_info_list

#_____________________________________________________________________

def GetRecordingSampleRate(device=None):
	""" 
	Checks for available recording sample rates.
	
	Parameters:
		device -- Backend dependent device to poll for values.
	
	Returns:
		any of the following depending on the sound card:
		1) an int representing the only supported sample rate.
		2) an IntRange class with IntRange.low and IntRange.high being the min and max sample rates.
		3) a list of ints representing all the supported sample rates.
	"""
	
	src = Globals.settings.recording["audiosrc"]
	try:
		bin = gst.parse_bin_from_description(src, False)
	except (gobject.GError, gst.ElementNotFoundError):
		Globals.debug("Cannot get sample rate: cannot parse bin", src)
		return list()
	
	try:
		element = bin.iterate_sources().next()
	except StopIteration:
		Globals.debug("Cannot get sample rate: no source device in the bin", src)
	
	if device:
		element.set_property("device", device)

	# open device (so caps are probed)
	bin.set_state(gst.STATE_READY)

	try:
		pad = element.src_pads().next()
		caps = pad.get_caps()
		val = caps[0]["rate"]
	except:
		val = None
		
	# clean up
	bin.set_state(gst.STATE_NULL)
	del element, bin
	
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
	src_desc = Globals.settings.recording["audiosrc"]
	try:
		bin = gst.parse_bin_from_description(src_desc, False)
	except (gobject.GError, gst.ElementNotFoundError):
		Globals.debug("Cannot get number of channels: cannot parse bin", src_desc)
		return 0
	
	try:
		src = bin.iterate_sources().next()
	except StopIteration:
		Globals.debug("Cannot list capture devices: no source device in the bin", src_desc)
		
	src.set_property("device", device)
	src.set_state(gst.STATE_PAUSED)
	
	try:
		#Assume the card only offers one src (we can't handle more anyway)
		for pad in src.src_pads():
			caps = pad.get_caps()
	except:
		Globals.debug("Couldn't get source pad for %s"%device)
		src.set_state(gst.STATE_NULL)
		return 0
	
	nums = []
	for struct in caps:
		channels = caps[0]["channels"]
		if isinstance(channels, gst.IntRange):
			if channels.high > 20000:
				#Assume we're being given the max number of channels for gstreamer, so take low number
				nums.append(channels.low)
			else:
				#Otherwise take the high number
				nums.append(channels.high)
		else:
			nums.append(channels)

	numChannels = max(nums)
	Globals.debug("Detected channels = %s from caps:" % numChannels, caps.to_string())

	if numChannels > 8:
		# audioconvert can't handle more than 8 channels
		numChannels = 8

	#if numChannels == 2:
		#Assume one stereo input
	#	numChannels = 1

	src.set_state(gst.STATE_NULL)
	return numChannels

"""
The following function, is meant for testing this file independantly from the rest.
"""
if __name__ == "__main__":
	print(GetRecordingSampleRate())
