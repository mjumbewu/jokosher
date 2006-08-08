
import pygst
pygst.require("0.10")
import gst
import gobject
import time
from Monitored import *

#=========================================================================

class TransportManager(Monitored):

	""" This class handles the current play cursor position
	"""

	FPS = 30. 				# Position update rate in Frames Per Second
	TICKS_PER_BEAT = 256 	# Timing resolution - number of ticks ber beat
	SEEK_RATE = 5.			# How many times normal speed the position moves when seeking
	
	MODE_HOURS_MINS_SECS = 1
	MODE_BARS_BEATS = 2

	#_____________________________________________________________________

	def __init__(self, initialMode, mainpipeline):
		Monitored.__init__(self)
		
		self.pipeline = mainpipeline
		self.position = 0
		self.PrevPosition = 0
		self.bpm = 120.			# Tempo in BPM
		self.meter_nom = 4		# Meter nominator
		self.meter_denom = 4	# Meter denominator
		
		self.isPlaying = False
		self.isReversing = False
		self.isForwarding = False
		self.RedrawTimeLine = False # set by SetMode to force redraw
		                            # in TimeLine
		self.UpdateTimeout = False
		
		self.mode = initialMode
		self.startPosition = 0

	#_____________________________________________________________________
	
	def Play(self, movePlayhead):
		#the state must be set to paused before playing
		if self.pipeline.get_state(0)[1] != gst.STATE_PAUSED:
			return
			
		self.isPlaying = True
		if self.startPosition > 0.01:
			self.SeekTo(self.startPosition)
			
		self.pipeline.set_state(gst.STATE_PLAYING)
		if movePlayhead:
			self.StartUpdateTimeout()
		
	#_____________________________________________________________________
		
	def Stop(self):
		self.isPlaying = False
		self.startPosition = 0.
		self.SetPosition(0.0)
		
	#_____________________________________________________________________
		
	def Reverse(self, turnOn):
		if self.isReversing == turnOn:
			#there is no change in reversing state
			return
		
		self.isReversing = turnOn
		if turnOn:
			if self.isPlaying:
				#Pause playback while seeking
				self.pipeline.set_state(gst.STATE_PAUSED)
			self.StartUpdateTimeout()
		else:
			self.SeekTo(self.GetPosition())
			if self.isPlaying:
				#resume playback if it was playing before
				self.pipeline.set_state(gst.STATE_PLAYING)
		
	#_____________________________________________________________________
		
	def Forward(self, turnOn):
		if self.isForwarding == turnOn:
			#there is no change in the forwarding state
			return
	
		self.isForwarding = turnOn
		if turnOn:
			if self.isPlaying:
				#Pause playback while seeking
				self.pipeline.set_state(gst.STATE_PAUSED)
			self.StartUpdateTimeout()
		else:
			self.SeekTo(self.GetPosition())
			if self.isPlaying:
				#resume playback if it was playing before
				self.pipeline.set_state(gst.STATE_PLAYING)
		
	#_____________________________________________________________________
	
	def GetPosition(self):
		return self.position
	
	#_____________________________________________________________________
	
	def SetPosition(self, pos):
		self.PrevPosition = self.position
		self.position = pos
		self.StateChanged()

	#_____________________________________________________________________

	def SetMode(self, mode):
		"""
		   For undo compatibility please use Project.SetTransportMode().
		   That method should be used instead in most cases.
		"""
		self.mode = mode
		self.RedrawTimeLine = True
		self.StateChanged()
		
	#_____________________________________________________________________
	
	def GetPositionAsBarsAndBeats(self):
		mins = self.position / 60.
		beats = int(mins * self.bpm)
		ticks = ((mins - (beats / float(self.bpm))) * self.bpm) * self.TICKS_PER_BEAT
		bars = int(beats / self.meter_nom)
		beats -= bars * self.meter_nom
		return (bars+1, beats+1, ticks)
		
	#_____________________________________________________________________
	
	def GetPositionAsHoursMinutesSeconds(self):
		hours = int(self.position / 3600)
		mins = int((self.position % 3600) / 60)
		secs = int(self.position % 60)
		millis = int((self.position * 10000) % 10000)
		
		return (hours, mins, secs, millis)
	
	#_____________________________________________________________________

	def SetBPM(self, bpm):
		self.bpm = bpm
		self.StateChanged()
		
	#_____________________________________________________________________

	def SetMeter(self, nom, denom):
		self.meter_nom = nom
		self.meter_denom = denom
		self.StateChanged()

	#_____________________________________________________________________
	
	def StartUpdateTimeout(self):
		if not self.UpdateTimeout:
			gobject.timeout_add(int(1000/self.FPS), self.OnUpdate)
			self.UpdateTimeout = True
	
	#_____________________________________________________________________
	
	def OnUpdate(self):
		if self.isReversing:
			newpos = self.position - self.SEEK_RATE/self.FPS
			self.SetPosition(max(newpos, 0))
		elif self.isForwarding:
			self.SetPosition(self.position + self.SEEK_RATE/self.FPS)
		elif self.isPlaying:
			try:
				newpos = self.pipeline.query_position(gst.FORMAT_TIME)[0]
			except gst.QueryError:
				pass
			else:
				pos = float(newpos) / gst.SECOND + self.startPosition
				self.SetPosition(pos)
		else:
			self.UpdateTimeout = False
			#Prevent the timeout from calling us again
			return False
			
		#Make sure the timeout calls us again
		return True
		
	#_____________________________________________________________________
	
	def SeekTo(self, pos):
		#make sure we cant seek to before the beginning
		pos = max(0, pos)
		
		if self.isPlaying:
			self.pipeline.seek( 1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH,
					gst.SEEK_TYPE_SET, long(pos * gst.SECOND), 
					gst.SEEK_TYPE_NONE, -1)
		
		self.startPosition = pos
		self.SetPosition(pos)
	
	#_____________________________________________________________________
	
#=========================================================================

