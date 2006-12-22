#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	TransportManager.py
#	
#	This class handles the current cursor position and the gstreamer
#	bits for rewinding, fast forwarding and seeking.
#	
#
#-------------------------------------------------------------------------------

import pygst
pygst.require("0.10")
import gst
import gobject
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

	def __init__(self, initialMode, project):
		"""
			initalMode - the initial mode for the timeline display
			             will be one of:
			                 MODE_HOURS_MINS_SECS or
			                 MODE_BARS_BEATS
			project - reference to the main project
		"""
		Monitored.__init__(self)
		
		self.project = project
		self.pipeline = self.project.mainpipeline
		self.position = 0
		self.PrevPosition = 0
		self.bpm = 120			# Tempo in BPM
		self.meter_nom = 4		# Meter nominator
		self.meter_denom = 4	# Meter denominator
		
		self.isPlaying = False
		self.isPaused = False
		self.isReversing = False
		self.isForwarding = False
		self.RedrawTimeLine = False # set by SetMode to force redraw
		                            # in TimeLine
		self.UpdateTimeout = False
		
		self.mode = initialMode

	#_____________________________________________________________________
	
	def Play(self, newAudioState):
		"""
			Called when play button has been pressed (or whilst exporting 
			in which case newAudioState will be set to AUDIO_EXPORTING)
		"""
		#the state must be set to paused before playing
		if self.pipeline.get_state(0)[1] != gst.STATE_PAUSED:
			return
			
		self.isPlaying = True
		self.project.SetAudioState(newAudioState)
		
		if self.position > 0:
			self.SeekTo(self.position)
		
		self.pipeline.set_state(gst.STATE_PLAYING)
		#for normal playback then we need to start the timeout that will 
		#control the movement of the playhead
		if not self.project.GetIsExporting():
			self.StartUpdateTimeout()
		
	#_____________________________________________________________________
		
	def Pause(self):
		"""
		Pause the pipeline
		"""
		self.isPlaying = False
		self.isPaused = True
		self.project.SetAudioState(self.project.AUDIO_PAUSED)
		self.pipeline.set_state(gst.STATE_PAUSED)
	
	#_____________________________________________________________________
		
	def Stop(self):
		"""
			Called when stop button has been pressed
		"""
		self.isPlaying = False
		self.project.SetAudioState(self.project.AUDIO_STOPPED)
		self.SetPosition(0.0)
		self.pipeline.set_state(gst.STATE_READY)
		
	#_____________________________________________________________________
		
	def Reverse(self, turnOn):
		"""
			Called when rewind button is
			   a) pressed - turnOn = True
			   b) released - turnOn = False
		"""
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
		"""
			Called when fast forward button is
			   a) pressed - turnOn = True
			   b) released - turnOn = False
		"""
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
		"""
			Gives current position
		"""
		return self.position
	
	#_____________________________________________________________________
	
	def SetPosition(self, pos):
		"""
			Change current position variable (calls StateChanged to
			trigger response on all classes that listening to this)
		"""
		if self.position != pos:
			self.PrevPosition = self.position
			self.position = pos
			self.StateChanged()

	#_____________________________________________________________________

	def SetMode(self, mode):
		"""
		   For undo compatibility please use Project.SetTransportMode().
		   That method should be used instead in most cases.
		"""
		if self.mode != mode:
			self.mode = mode
			self.RedrawTimeLine = True
			self.StateChanged("transport-mode", mode)
		
	#_____________________________________________________________________
	
	def GetPositionAsBarsAndBeats(self):
		"""
			Returns a tuple of the current position as (bar, beats, ticks)
		"""
		mins = self.position / 60.
		beats = int(mins * self.bpm)
		ticks = ((mins - (beats / float(self.bpm))) * self.bpm) * self.TICKS_PER_BEAT
		bars = int(beats / self.meter_nom)
		beats -= bars * self.meter_nom
		return (bars+1, beats+1, ticks)
		
	#_____________________________________________________________________
	
	def GetPositionAsHoursMinutesSeconds(self):
		"""
			Returns a tuple of the current position as (hours, minutes, seconds)
		"""
		hours = int(self.position / 3600)
		mins = int((self.position % 3600) / 60)
		secs = int(self.position % 60)
		millis = int((self.position * 10000) % 10000)
		
		return (hours, mins, secs, millis)
	
	#_____________________________________________________________________

	def SetBPM(self, bpm):
		"""
			Changes current beats per minute
		"""
		if self.bpm != bpm:
			self.bpm = bpm
			self.StateChanged("transport-bpm")
		
	#_____________________________________________________________________

	def SetMeter(self, nom, denom):
		"""
			Changes current meter
		"""
		if self.meter_nom != nom or self.meter_denom != denom:
			self.meter_nom = nom
			self.meter_denom = denom
			self.StateChanged("transport-time-sig")

	#_____________________________________________________________________
	
	def StartUpdateTimeout(self):
		"""
			Starts the timeout that will control the
			playhead display
		"""
		if not self.UpdateTimeout:
			gobject.timeout_add(int(1000/self.FPS), self.OnUpdate)
			self.UpdateTimeout = True
	
	#_____________________________________________________________________
	
	def OnUpdate(self):
		"""
			The timeout callback - called every 1/FPS to move the
			playhead display on
		"""
		if self.isReversing:
			newpos = self.position - self.SEEK_RATE/self.FPS
			self.SetPosition(max(newpos, 0))
		elif self.isForwarding:
			self.SetPosition(self.position + self.SEEK_RATE/self.FPS)
		elif self.isPlaying:
			try:
				#if pipeline should be playing and has not quite 
				#yet started then ignore this time through
				if self.pipeline.get_state(0)[1] == gst.STATE_PAUSED:
					return True
				self.QueryPosition()
			except gst.QueryError:
				pass
		else:
			self.UpdateTimeout = False
			#Prevent the timeout from calling us again
			return False
			
		#Make sure the timeout calls us again
		return True
		
	#_____________________________________________________________________
	
	def SeekTo(self, pos):
		"""
			Performs pipeline seek to alter position of playback
		"""
		#make sure we cant seek to before the beginning
		pos = max(0, pos)
		if self.isPlaying or self.isPaused:
			self.pipeline.seek( 1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH,
					gst.SEEK_TYPE_SET, long(pos * gst.SECOND), 
					gst.SEEK_TYPE_NONE, -1)
		self.SetPosition(pos)
		
	#_____________________________________________________________________
	
	def QueryPosition(self):
		"""
			Reads current position by querying pipeline
		"""
		pos = self.pipeline.query_position(gst.FORMAT_TIME)[0]
		self.SetPosition(float(pos) / gst.SECOND)
		
	#_____________________________________________________________________
	
#=========================================================================

