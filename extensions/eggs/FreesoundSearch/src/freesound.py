import os.path
import urllib2, urllib
from xml.dom import minidom
from xml.xpath import Evaluate

# First, set up cookie handling!
# from http://www.voidspace.org.uk/python/articles/cookielib.shtml

COOKIEFILE = 'cookies.lwp'
# the path and filename to save your cookies in

cookieJar = None
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
		cookieJar = ClientCookie.LWPCookieJar()

else:
	# importing cookielib worked
	urlopen = urllib2.urlopen
	Request = urllib2.Request
	cookieJar = cookielib.LWPCookieJar()
	# This is a subclass of FileCookieJar
	# that has useful load and save methods

if cookieJar is not None:
# we successfully imported
# one of the two cookie handling modules

	if os.path.isfile(COOKIEFILE):
		# if we have a cookie file already saved
		# then load the cookies into the Cookie Jar
		cookieJar.load(COOKIEFILE)

	# Now we need to get our Cookie Jar
	# installed in the opener;
	# for fetching URLs
	if cookielib is not None:
		# if we use cookielib
		# then we get the HTTPCookieProcessor
		# and install the opener in urllib2
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookieJar))
		urllib2.install_opener(opener)
		
	else:
		# if we use ClientCookie
		# then we get the HTTPCookieProcessor
		# and install the opener in ClientCookie
		opener = ClientCookie.build_opener(ClientCookie.HTTPCookieProcessor(cookieJar))
		ClientCookie.install_opener(opener)

# XML node paths as returned by the Freesound search
SAMPLE_ATTRIBUTES = {
	"author" : "/freesound/sample/user/name",
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

#=========================================================================

class Sample:
	"""
	Represents a Freesound sample.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, sid):
		"""
		Creates a new Freesound sample instance.
		
		Parameters:
			id -- id of the new sample.
		"""
		self.sid = sid
		
	#_____________________________________________________________________
		
	def Fetch(self):
		"""
		Fetch thyself from the Freesound service.
		"""
		req = Request("http://freesound.iua.upf.edu/samplesViewSingleXML.php?id=%s" % self.sid)
		try:
			handle = urlopen(req)
		except:
			# TODO: handle URL problems
			pass
		data = handle.read()
		dom = minidom.parseString(data)
		for attribute, xpath in SAMPLE_ATTRIBUTES.items():
			try:
				setattr(self, attribute, Evaluate(xpath, dom)[0].firstChild.nodeValue)
			except:
				setattr(self, attribute, None)
				
	#_____________________________________________________________________

#=========================================================================

class Freesound:
	"""
	Implements the searches on Freesound.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, username=None, password=None):
		"""
		Creates a new instance of a Freesound search object.
		
		Parameters:
			username -- Freesound account username.
			password -- Freesound account password.
		"""
		self.loggedIn = False
		if username and password:
			self.Login(username, password)
			
	#_____________________________________________________________________
			
	def Login(self, username, password):
		"""
		Attempts to login into the Freesound service.
		
		Parameters:
			username -- Freesound account username.
			password -- Freesound account password.
		"""
		# TODO: remove this print
		#print "username: %s, password: %s" % (username, password)
		
		if username == "" or password == "":
			self.loggedIn = False
			return
		
		# attempt to login
		data = {"username": username,
			"password": password,
			"login": "1",
			"redirect": "../tests/login.php"}
		req = Request("http://freesound.iua.upf.edu/forum/login.php", 
				urllib.urlencode(data))
		try:
			handle = urlopen(req)
		except:
			# TODO: handle URL problems
			self.loggedIn = False
			return
		data = handle.read()
		
		# check to see if login was successful
		if data != "login":
			self.loggedIn = False
			return
		
		self.loggedIn = True
		
	#_____________________________________________________________________

	def Search(self, query):
		"""
		Searches the Freesound database trying to match the given query.
		
		Parameters:
			query -- query to look for in the Freesound database.
					It's a dictionary with the following format:
					{
					search : "string to match",
					searchDescriptions : "1 or 0",
					searchTags : "1 or 0",
					searchFilenames : "1 or 0",
					searchUsernames : "1 or 0"
					}
			
			*the fields labeled "1 or 0" define whether those fields
			should be included in the search.
			
		Returns:
			the matching sample(s) list.
		"""
		req = Request("http://freesound.iua.upf.edu/searchTextXML.php", 
				urllib.urlencode(query))
		try:
			handle = urlopen(req)
		except:
			# TODO: handle URL problems
			print "Search: URL Error"
			pass
		data = handle.read()
		dom = minidom.parseString(data)
		
		if dom.documentElement.nodeName != "freesound":
			raise "Search failed"
		
		return [Sample(sample.getAttribute("id")) for sample in
				dom.getElementsByTagName('sample')]
	
	#_____________________________________________________________________

#=========================================================================