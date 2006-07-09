import ConfigParser
import os

class Settings:

	general = {"mixdownformat": "value", "recentprojects": "value", "samplerate": "value", "sampleformat": "value", "startupaction" : "value"}
	recording = {"device": "value", "fileformat": "value", "devicecardnum": "value"}
	playback = {"device": "value", "devicecardnum": "value"}
	
	def __init__(self, filename = None):
		if not filename:
			self.filename = os.path.join(os.environ['HOME'], '.jokosher')
		else:
			self.filename = filename
		self.config = ConfigParser.ConfigParser()

		self.read()

	def read(self):
		self.config.read(self.filename)
	
		if not self.config.has_section("General"):
			self.config.add_section("General")
		if not self.config.has_section("Recording"):
			self.config.add_section("Recording")
		if not self.config.has_section("Playback"):
			self.config.add_section("Playback")
	
		for key, value in self.config.items("General"):
			self.general[key] = value
		for key, value in self.config.items("Recording"):
			self.recording[key] = value
		for key, value in self.config.items("Playback"):
			self.playback[key] = value
		
	def write(self):
		for key in self.general:
			self.config.set("General", key, self.general[key])
		for key in self.recording:
			self.config.set("Recording", key, self.recording[key])
		for key in self.playback:
			self.config.set("Playback", key, self.playback[key])

		file = open(self.filename, 'w')
		self.config.write(file)
		file.close()
	
settings = Settings()

INSTRUMENT_HEADER_WIDTH = 0
JOKOSHER_PATH = None