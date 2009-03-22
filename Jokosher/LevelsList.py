#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	LevelsList.py
#	
#	This module contains the class which is responable for storing a list of
#	all of the audio levels of each channel of audio along with the time of that
#	level within the audio track. This data is used to draw the a graphical
#	representation of the audio waveform for the user.
#
#-------------------------------------------------------------------------------

import Utils

from array import array
import itertools
import sys
import bisect
import copy

class LevelsList:
	MAGIC_NUMBER = 0x00011011	# an integer with 4 unique bytes used to check endianness
	VERSION = 1
	ARRAY_TYPE = 'l'
	
	def __init__(self):
		self.channels = []
		self.times = array(self.ARRAY_TYPE)
	
	#_____________________________________________________________________
	
	def CreateChannels(self,  num_channels):
		self.channels = []
		for i in xrange(num_channels):
			self.channels.append(array(self.ARRAY_TYPE))
	
	#_____________________________________________________________________
	
	def copy(self):
		levelslist = LevelsList()
		levelslist.times = copy.copy(self.times)
		levelslist.channels = []
		for chan in self.channels:
			levelslist.channels.append(copy.copy(chan))
	
		return levelslist

	#_____________________________________________________________________
	
	def append(self, endtime, levels):
		"""
		Append a set of waveforms to the current list,
		and associates them with the given end time.
		"""
		if not self.channels:
			self.CreateChannels(len(levels))
		
		assert len(self.channels) == len(levels)
		# make sure the endtime is greater than the previous endtime
		# if this is the first endtime, make sure its bigger than 0
		assert endtime > (self.times[-1] if self.times else 0)
		
		self.times.append(endtime)
		
		for level,  chan in itertools.izip(levels,  self.channels):
			chan.append(level)
			assert len(self.times) == len(chan)
	
	#_____________________________________________________________________
	
	def append_time_delta(self, time_delta, levels):
		if self.times:
			last_time = self.times[-1]
		else:
			last_time = 0
			
		self.append(last_time + time_delta, levels)
	
	#_____________________________________________________________________
	
	def extend(self, basetime, levelslist):
		old_length = len(self.times)
		self.times.extend(levelslist.times)
		
		# shift the new endtimes to match the length of the original audio clip
		for idx in xrange(old_length, len(self.times)):
			time = self.times[idx]
			self.times[idx] = time + basetime
		
		assert len(self.channels) == len(levelslist.channels)
		for chan, lchan in itertools.izip(self.channels, levelslist.channels):
			chan.extend(lchan)
	
	
	#_____________________________________________________________________
	
	def fromfile(self,  path):
		try:
			self.__fromfile(path)
		except (EOFError, IOError):
			# on error delete all partially loaded data
			self.channels = []
			self.times = array(self.ARRAY_TYPE)
			raise CorruptFileError()
	
	#_____________________________________________________________________
	
	def __fromfile(self,  path):
		f = open(path,  "rb")
		info = array(self.ARRAY_TYPE)
		info.fromfile(f,  4)
		
		magic,  version,  length,  num_channels = info
		
		byteswap = False
		if info[0] != self.MAGIC_NUMBER:
			info.byteswap()
			if info[0] != self.MAGIC_NUMBER:
				raise CorruptFileError("unknown endianness in levels file")
			else:
				byteswap = True
		
		#currently there is only one version
		assert version == self.VERSION
		
		self.times = array(self.ARRAY_TYPE)
		self.times.fromfile(f,  length)
		if byteswap:
			self.times.byteswap()
		
		self.CreateChannels(num_channels)
		for chan in self.channels:
			chan.fromfile(f,  length)
			if byteswap:
				self.times.byteswap()
			assert len(self.times) == len(chan)
	
	#_____________________________________________________________________
	
	def tofile(self,  path):
		f = open(path,  "wb")
		info = array(self.ARRAY_TYPE)
		info.append(self.MAGIC_NUMBER)
		info.append(self.VERSION)
		info.append(len(self.times))
		info.append(len(self.channels))
		
		info.tofile(f)
		self.times.tofile(f)
		for chan in self.channels:
			chan.tofile(f)
	
	#_____________________________________________________________________
	
	def find_endtime_index(self, time):
		return bisect.bisect_left(self.times, time)
	
	#_____________________________________________________________________
	
	def slice_by_endtime(self, starttime, stoptime=None):
		if stoptime is None:
			stop_idx = len(self.times)
		else:
			assert starttime < stoptime
			stop_idx = self.find_endtime_index(stoptime)
			
		start_idx = self.find_endtime_index(starttime)
		levelslist = LevelsList()
		levelslist.times = self.times[start_idx:stop_idx]
		
		# adjust the endtimes so they are relative to the new start time.
		for idx, time in enumerate(levelslist.times):
			levelslist.times[idx] = time - starttime
		
		levelslist.channels = []
		for chan in self.channels:
			levelslist.channels.append(chan[start_idx:stop_idx])
		
		return levelslist
	
	#_____________________________________________________________________
	
	def __iter__(self):
		# FIXME: hard coded single channel
		if not self.channels:
			self.CreateChannels(1)
		return itertools.izip(self.times,  self.channels[0])
	
	#_____________________________________________________________________
	
	def __getitem__(self, index):
		# FIXME: hard coded single channel
		return (self.times[index], self.channels[0][index])
	
	#_____________________________________________________________________
	
	def __len__(self):
		return len(self.times)
	#_____________________________________________________________________

#=========================================================================

def add(list_one, list_two):
	levelslist = list_one.copy()
	levelslist.extend(list_two)
	return levelslist

#=========================================================================
	
class CorruptFileError(EnvironmentError):
	pass

#=========================================================================

