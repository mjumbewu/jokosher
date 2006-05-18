
import pygst
pygst.require("0.10")
import gst
import threading
import time
from Monitored import *

#=========================================================================

class TransportManager(Monitored):

	""" This class handles the current play cursor position
	"""

	FPS = 30. 				# Position update rate in Frames Per Second
	TICKS_PER_BEAT = 256 	# Timing resolution - number of ticks ber beat
	SEEK_RATE = 10.			# How many times normal speed the position moves when seeking
	
	MODE_HOURS_MINS_SECS = 1
	MODE_BARS_BEATS = 2

	#_____________________________________________________________________

	def __init__(self, initialMode):
		Monitored.__init__(self)
		
		self.position = 0
		self.PrevPosition = 0
		self.bpm = 120.			# Tempo in BPM
		self.meter_nom = 4		# Meter nominator
		self.meter_denom = 4	# Meter denominator
		
		self.oldTime = time.time()
		self.stopThread = threading.Event()
		self.threadStopped = threading.Event()
		self.thread = threading.Thread(target=self.ThreadProc, name="TransportManager")
		self.thread.start()
		
		self.isPlaying = False
		self.isReversing = False
		self.isForwarding = False
		self.RedrawTimeLine = False # set by SetMode to force redraw
		                            # in TimeLine
		
		self.mode = initialMode

	#_____________________________________________________________________

	""" Note TransportManagers are equal without regard to the threading
	"""
	def __eq__(self, tm):
		if(self.position != tm.position):
			return False
		if(self.bpm != tm.bpm):
			return False
		if(self.meter_nom != tm.meter_nom):
			return False
		if(self.meter_denom != tm.meter_denom):
			return False

		if(self.isPlaying != tm.isPlaying):
			return False
		if(self.isReversing != tm.isReversing):
			return False
		if(self.isForwarding != tm.isForwarding):
			return False
		
		if(self.mode != tm.mode):
			return False

		return True
		
	#_____________________________________________________________________
		
	def Destroy(self):
		self.stopThread.set()
		self.threadStopped.wait()
				
	#_____________________________________________________________________
		
	def ThreadProc(self):
		while True:
			self.stopThread.wait(1. / self.FPS)
			if self.stopThread.isSet():
				self.threadStopped.set()
				return
			else:
				if self.isPlaying:
					t = time.time()
					self.position += t - self.oldTime
					self.oldTime = t
					self.StateChanged()
					
				if self.isForwarding:
					t = time.time()
					self.position += (t - self.oldTime) * self.SEEK_RATE
					self.oldTime = t
					self.StateChanged()
					
				if self.isReversing:
					t = time.time()
					self.position -= (t - self.oldTime) * self.SEEK_RATE
					self.position = max(0, self.position)
					self.oldTime = t
					self.StateChanged()

	#_____________________________________________________________________
		
	def Play(self):
		self.isPlaying = True
		
	#_____________________________________________________________________
		
	def Stop(self):
		self.isPlaying = False
		
	#_____________________________________________________________________
		
	def Reverse(self, rev):
		self.isReversing = rev
		self.oldTime = time.time()
		
	#_____________________________________________________________________
		
	def Forward(self, fwd):
		self.isForwarding = fwd
		self.oldTime = time.time()
		
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
		mins = int(self.position / 60.)
		hours = int(mins / 60.)
		mins -= hours * 60
		secs = int(self.position)
		secs -= (hours * 60 * 60) + (mins * 60)
		millis = (self.position - int(self.position)) * 1000
		
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
		
	
#=========================================================================

