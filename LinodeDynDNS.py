#!/usr/bin/python3.2
#
# Easy Python3 Dynamic DNS
# By Jed Smith <jed@jedsmith.org> 4/29/2009
# This code and associated documentation is released into the public domain.
#
# This script **REQUIRES** Python 3.0 or above.  Python 2.6 may work.
# To see what version you are using, run this:
#
#   python --version
#
# To use:
#
#   0. You'll probably have to edit the shebang above.
#
#   1. In the Linode DNS manager, edit your zone (must be master) and create
#      an A record for your home computer.  You can name it whatever you like;
#      I call mine 'home'.  Fill in 0.0.0.0 for the IP.
#
#   2. Save it.
#
#   3. Edit the three configuration options below, following the directions for
#      each.  As this is a quick hack, it assumes everything goes right.
#
#   4. Configure uwsgi or similar to use this script. Password protect access
#      to this script and have the username be the FQDN of the host.
#
#   5. Configure clients (e.g. DD-WRT, Tomato, etc.) with a custom dynamic
#      DNS updater that fetches this web page.
#
# Set the domain name below.  The API key MUST have write access to this 
# resource ID. Do not include the hostname here.
#
DOMAIN = "yourdomain.com"
#
# List of hosts that may be updated using this script
#
VALIDHOSTS = [ "home", "host2" ]
#
# Your Linode API key.  You can generate this by going to your profile in the
# Linode manager.  It should be fairly long.
#
KEY = "yourapikey"
#
# If for some reason the API URI changes, or you wish to send requests to a
# different URI for debugging reasons, edit this.  {0} will be replaced with the
# API key set above, and & will be added automatically for parameters.
#
API = "https://api.linode.com/api/?api_key={0}&resultFormat=JSON"
#
# Comment or remove this line to indicate that you edited the options above.
#
exit("Did you edit the options?  vi this file open.")
#
# That's it!
#
# Now run dyndns.py manually, or add it to cron, or whatever.  You can even have
# multiple copies of the script doing different zones.
#
# For automated processing, this script will always print EXACTLY one line, and
# will also communicate via a return code.  The return codes are:
#
#    0 - No need to update, A record matches my public IP
#    1 - Updated record
#    2 - Some kind of error or exception occurred
#
# The script will also output one line that starts with either OK or FAIL.  If
# an update was necessary, OK will have extra information after it.
#
# If you want to see responses for troubleshooting, set this:
#
DEBUG = False


#####################
# STOP EDITING HERE #

try:
	from json import load
	from urllib.parse import urlencode
	from urllib.request import urlretrieve
except Exception as excp:
	exit("Couldn't import the standard library. Are you running Python 3?")

def execute(action, parameters):
	# Execute a query and return a Python dictionary.
	uri = "{0}&action={1}".format(API.format(KEY), action)
	if parameters and len(parameters) > 0:
		uri = "{0}&{1}".format(uri, urlencode(parameters))
	if DEBUG:
		print("-->", uri)
	file, headers = urlretrieve(uri)
	if DEBUG:
		print("<--", file)
		print(headers, end="")
		print(open(file).read())
		print()
	json = load(open(file), encoding="utf-8")
	if len(json["ERRORARRAY"]) > 0:
		err = json["ERRORARRAY"][0]
		raise Exception("Error {0}: {1}".format(int(err["ERRORCODE"]),
			err["ERRORMESSAGE"]))
	return json["DATA"]

def updateip(fqdn, newIp):
	try:
		# Determine DomainId
		domains = execute("domain.list", {})
		for domain in domains:
			if fqdn.endswith(domain["DOMAIN"]):
				matchedDomain = domain
				break
		if matchedDomain is None:
			raise Exception("Domain not found")
		domainId = matchedDomain["DOMAINID"]
		domainName = matchedDomain["DOMAIN"]
		if DEBUG:
			print("Found matching domain:")
			print("  DomainId = {0}".format(domainId))
			print("  Name = {0}".format(domainName))
		
		# Determine resource id (subdomain)
		resources = execute("domain.resource.list",
			{"DomainId": domainId})
		for resource in resources:
			if resource["NAME"] + "." + domainName == fqdn:
				matchedResource = resource
				break
		if resource is None:
			raise Exception("Resource not found")
		resourceId = matchedResource["RESOURCEID"]
		oldIp = matchedResource["TARGET"]
		if DEBUG:
			print("Found matching resource:")
			print("  ResourceId = {0}".format(resourceId))
			print("  Target = {0}".format(oldIp))

		if oldIp == newIp:
			return("OK {0} -> {1} (unchanged)".format(oldIp, newIp))
		
		# Update public ip
		execute("domain.resource.update", {
			"ResourceID": resourceId,
			"DomainID": domainId,
			"Target": newIp})
		return("OK {0} -> {1}".format(oldIp, newIp))
	except Exception as excp:
		return("FAIL {0}: {1}".format(type(excp).__name__, excp))

def application(environ, start_response):
	status = '200 OK'
	output = ""
	
	response_headers = [('Content-type', 'text/plain')]
	start_response(status, response_headers)

	# Get data from fields
	fqdn     = environ["REMOTE_USER"]
	ip       = environ["REMOTE_ADDR"]
	hostnameValid = 0

	for validhost in VALIDHOSTS:
		if fqdn == (validhost + "." + DOMAIN):
			hostnameValid = 1
	
	if hostnameValid == 1:
		output = updateip(fqdn, ip)
	else:
		output = fqdn + " is not allowed"

	return output.encode('utf-8')
