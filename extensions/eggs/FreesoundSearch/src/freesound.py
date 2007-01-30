import os.path
import urllib2, urllib
from xml.dom import minidom
from xml.xpath import Evaluate

# First, set up cookie handling!
# from http://www.voidspace.org.uk/python/articles/cookielib.shtml

COOKIEFILE = 'cookies.lwp'
# the path and filename to save your cookies in

cj = None
ClientCookie = None
cookielib = None

# Let's see if cookielib is available
try:
	import cookielib
except ImportError:
	# If importing cookielib fails
	# let's try ClientCookie
	try:
		import ClientCookie
	except ImportError:
		# ClientCookie isn't available either
		urlopen = urllib2.urlopen
		Request = urllib2.Request
	else:
		# imported ClientCookie
		urlopen = ClientCookie.urlopen
		Request = ClientCookie.Request
		cj = ClientCookie.LWPCookieJar()

else:
	# importing cookielib worked
	urlopen = urllib2.urlopen
	Request = urllib2.Request
	cj = cookielib.LWPCookieJar()
	# This is a subclass of FileCookieJar
	# that has useful load and save methods


if cj is not None:
# we successfully imported
# one of the two cookie handling modules

	if os.path.isfile(COOKIEFILE):
		# if we have a cookie file already saved
		# then load the cookies into the Cookie Jar
		cj.load(COOKIEFILE)

	# Now we need to get our Cookie Jar
	# installed in the opener;
	# for fetching URLs
	if cookielib is not None:
		# if we use cookielib
		# then we get the HTTPCookieProcessor
		# and install the opener in urllib2
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
		urllib2.install_opener(opener)

	else:
		# if we use ClientCookie
		# then we get the HTTPCookieProcessor
		# and install the opener in ClientCookie
		opener = ClientCookie.build_opener(ClientCookie.HTTPCookieProcessor(cj))
		ClientCookie.install_opener(opener)

SAMPLE_ATTRIBUTES = {
	"date": "/freesound/sample/date",
	"originalFilename": "/freesound/sample/originalFilename",
	"image": "/freesound/sample/image",
	"previewURL": "/freesound/sample/preview",
	"image": "/freesound/sample/image",
	"samplerate": "/freesound/sample/samplerate",
	"bitrate": "/freesound/sample/bitrate",
	"bitdepth": "/freesound/sample/bitdepth",
	"channels": "/freesound/sample/channels",
	"duration": "/freesound/sample/duration",
	"filesize": "/freesound/sample/filesize",
	"description": "/freesound/sample/descriptions/description/text"
}

class Sample:
	def __init__(self, sid):
		self.sid = sid
		
	def Fetch(self):
		# fetch thyself
		req = Request("http://freesound.iua.upf.edu/samplesViewSingleXML.php?id=%s" % self.sid)
		handle = urlopen(req)
		data = handle.read()
		dom = minidom.parseString(data)
		for attribute, xpath in SAMPLE_ATTRIBUTES.items():
			try:
				setattr(self,attribute,Evaluate(xpath, dom)[0].firstChild.nodeValue)
			except:
				setattr(self,attribute,None)

class Freesound:
	def __init__(self, username=None, password=None):
		self.loggedIn = False
		if username and password:
			self.Login(username, password)
			
	def Login(self, username, password):
		data = {"username": username,
			"password": password,
			"login": "1",
			"redirect": "../tests/login.php"}
		req = Request("http://freesound.iua.upf.edu/forum/login.php", 
				urllib.urlencode(data))
		handle = urlopen(req)
		#TODO: remove this print
		print "Freesound lib: logged in"
		self.loggedIn = True

	def Search(self, query):
		data = {"search": query}
		req = Request("http://freesound.iua.upf.edu/searchTextXML.php", 
				urllib.urlencode(data))
		handle = urlopen(req)
		data = handle.read()
		dom = minidom.parseString(data)
		if dom.documentElement.nodeName != "freesound":
			raise "Search failed"
		return [Sample(x.getAttribute("id")) for x in
				dom.getElementsByTagName('sample')]
