#!/usr/bin/python
#
# DanAmodio
#
# Profiles web enabled services 
#


import sys
import yaml
import argparse
import base64
import xml.etree.ElementTree as ET
import httplib2
import socket

# did globals for easy rule language. kinda gross, but this is single thread.
args = None
url = None 
resp = None
respdata = None
didFind = False

def inBody(test):
    return True if respdata.find(test)>-1 else False

def inUrl(test):
    return True if resp['content-location'].find(test)>-1 else False

def found(signature):
    global didFind
    didFind = True
    print "[!] " + url + " : " + signature

# https://en.wikipedia.org/wiki/%3F:#Python
def evalRules():
    found("Wordpress") if inBody("wp-content/") or inBody("wp-includes") else 0 
    found("Drupal") if inBody("drupal.min.js") or inBody("Drupal.settings") or inBody("http://drupal.org") or inBody("/node") else 0 
    found("Coldfusion") if inBody(".cfm") or inBody(".cfc") else 0
    found("Accellion SFT") if inBody("Secured by Accellion") else 0
    found("F5 BIG-IP") if (inBody("licensed from F5 Networks") and inUrl("my.policy")) or (inBody("BIG-IP logout page") and inUrl("my.logout.php")) else 0
    found("Confluence") if inBody("login to Confluence") or inBody("Log in to Confluence") or inBody("com-atlassian-confluence") else 0
    found("Lotus Domino") if inBody("homepage.nsf/homePage.gif?OpenImageResource") or (inBody("Notes Client") and inBody("Lotus")) else 0
    found("Citrix ShareFile Storage Server") if inBody("ShareFile Storage Server") else 0
    found("IIS7 Welcome Page") if inBody("welcome.png") and inBody("IIS7") else 0
    found("Citrix") if inBody("Citrix Systems") and inBody("vpn/") else 0
    found("Outlook Web App") if inBody("Outlook Web App") and inBody("CookieAuth.dll") else 0
    found("MobileIron") if inBody("MobileIron") else 0
    found("VMware Horizon") if inBody("VMware Horizon") and inBody("connect to your desktop and applications") else 0
    found("Cisco VPN") if inBody("CSCOE") and inBody("SSL VPN Service") else 0
    found("Windows SBS") if inBody("Welcome to Windows Small Business Server") else 0
    found("Mediawiki") if inBody("wiki/Main_Page") or inBody("wiki/Special:") or inBody("wiki/File:") or inBody("poweredby_mediawiki") else 0
    found("Thycotic Secret Server") if inBody("Thycotic Secret Server") else 0
    found("Directory Listing") if inBody("Index of") or inBody("Parent Directory") else 0

def parse():
    #loadRules(args)
    print "[*] Starting Web Intel scanner -- by Dan Amodio"
    print "[*] This script attempts to identify common CMS and web applications with a single request."
    print "[*]"
    if args.dns:
        print '[*] Using DNS mode. Script will search for user provided hostnames in output.'
        print '[!] WARNING: If you did not manually specify hostnames in your scan input, this might fail.'
    
    if(args.nmap):
        parseNmap()
    elif(args.listfile):
        parseList()
    elif(args.url):
        global url
        url = args.url
        probeUrl()
    elif(args.nessus):
        parseNessus()

# TODO - Seem to get dups from this nessus parsing. Need to uniq the results.
def parseNessus():
    print "[!] WARNING: This script doesn't fully support Nessus files yet."
    tree = ET.parse( args.nessus)
    root = tree.getroot().find('Report')
    
    for host in root.findall('ReportHost'):
        fqdn = ""
        ipaddr = ""
        for tag in host.find('HostProperties').findall('tag'):
            if tag.get('name') == 'host-fqdn':
                fqdn = tag.text
            if tag.get('name') == 'host-ip':
                ipaddr = tag.text
        for item in host.findall('ReportItem'):
            if item.get('pluginName') == 'Service Detection':
                if item.get('svc_name') == 'www':
                    port = item.get('port')
                    thehost = None
                    if args.dns:
                        #print fqdn, item.get('port')
                        thehost = fqdn
                    else:
                        #print ipaddr, item.get('port')
                        thehost = ipaddr
                    if port == '80':
                        probe("http",thehost,port)
                    elif port == '443':
                        probe("https",thehost,port)
                    else:
                        probe("http",thehost,port) # WE HOPE!

def parseNmap():
    tree = ET.parse( args.nmap )
    root = tree.getroot()
    
    for host in root.findall('host'):
        addr = None
        if not args.dns:
            addr = host.find('address').get('addr')
        elif args.dns:
            for hostname in host.find('hostnames').findall('hostname'):
                if hostname.get('type') == 'user':
                    addr = hostname.get('name') 
        for port in host.find('ports').findall('port'):
            portid = port.get('portid')
            if port.find('state').get('state') == 'open':
                if port.find('service').get('name') == 'http':
                    probe("http",addr,portid) 
                if port.find('service').get('name') == 'https':
                    probe("https",addr,portid) 
        
def parseList():
    global url
    urls = args.listfile.readlines()
    for urln in urls:
        url = urln.rstrip()
        probeUrl()

def getHttpLib():
    return httplib2.Http(".cache", disable_ssl_certificate_validation=True, timeout=5)

def probe(protocol,host,port):
    global url
    url = protocol+"://"+host+":"+port
    probeUrl()

def probeUrl():
    global url, resp, respdata, didFind
    #print "[*] Probing " + url
    # automatically follows 3xx
    # disable SSL validation
    h = getHttpLib()
    try:
        resp, respdata = h.request(url)
        if resp.status == 200:
            #print "[!] Got 200. profiling..."
            #profile(url,resp,content)
            #evalRules(url,resp,content)
            if args.debug:
                print resp
                print respdata
            evalRules()
            if didFind == False:
                print "[*] " + url + " : No Signature Match"
            else:
                didFind = False
        else:
            print "[!] ERROR: Got response code " + str(resp.status) + " from " + url
    except httplib2.SSLHandshakeError as e:
        print "[!] ERROR: Could create SSL connection to " + url
    except socket.error as e:
        print "[!] ERROR: Could not open socket to " + url

# may add some of this functionality back in for deeper probing (dir buster style)
# also used old rules lang
"""
def profile(url,response,data):
    bogus = bogusSuccess(url)
    for rule in rules:
        found = 0
        for test in rules[rule]['body']:
            if data.find(test)>-1:
                found = found+1
        #if not args.nofollowup:
        # do a quick test before running path rules.
        if not bogus:
            for path in rules[rule]['path']:
                try:
                    resp, content = getHttpLib().request(url + path,redirections=0)
                    if resp.status == 200:
                        print "[!] FOUND: " + url + path
                        found = found + 1
                except (IOError,httplib2.RedirectLimit) as err:
                    #print "[!] ERROR:", str(err)
                    pass
        if found > 0:
            print "[!] PROFILE: " +rule+ " (" + str(found) + "/" + str(countRules(rule)) + ")"

def bogusSuccess(url):
    try:
        resp, content = getHttpLib().request(url + "/asdfsa/asf/sdfwe/rr344433/s/egd/xbvvvvv/",redirections=0)
        if resp.status == 200:
            # we almost certainly cannot trust this server's response codes
            print "[!] WARNING: This server is responding with bogus 200 status codes. Skipping some test cases."
            return True
    except httplib2.RedirectLimit as e:
        pass
    return False

"""

def main(argv):
    filename = ""
    parser = argparse.ArgumentParser(description='Shakedown webservices for known CMS and technology stacks. ')
    parser.add_argument('--nmap', type=file, help='nmap xml file.')
    parser.add_argument('--nessus', type=file, help='.nessus xml file.')
    parser.add_argument('--listfile', type=file, help='straight file list containing fully qualified urls.')
    parser.add_argument('--url', type=str, required=False, help='profile a url.')
    #parser.add_argument('--subnet', type=str, required=False, help='subnet to scan.')
    #parser.add_argument('--ports', type=str, default='80,8080,8081,8000,9000,443,8443', required=False, help='the ports to scan for web services. e.g. 80,8080,443') # just use NMAP
    parser.add_argument('--dns', default=False, action="store_true", help='Use dns. Pretty important if doing this over the internet due to how some shared hosting services route.')
    parser.add_argument('--debug', default=False, action="store_true", help="Print the response data.")
    #parser.add_argument('--rules',default='rules',type=file,required=False,help='the rules file')
    #parser.add_argument('--nofollowup', default=False, action="store_true", help='disable sending followup requests to a host, like /wp-login.php.') # I want to avoid doing this at all with this script.

    if len(argv) == 0:
        parser.print_help()
        sys.exit(0)
    try:
        global args
        args = parser.parse_args() 
        parse( )
    except IOError as err: 
        print type(err), str(err)
        parser.print_help()
        sys.exit(2)

if __name__ == "__main__":
    main(sys.argv[1:])
