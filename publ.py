import argparse
import logging
import requests
import os
import SimpleHTTPServer
import SocketServer
import sys
import urlparse
import webbrowser

from bs4 import BeautifulSoup
from configparser import ConfigParser, DuplicateSectionError

if sys.version < '3':
    from urlparse import parse_qs
    from urllib import urlencode
else:
    from urllib.parse import urlencode, parse_qs

SERVER_PORT = 5252
APPNAME = "publ"

if sys.platform == "darwin":
    from AppKit import NSSearchPathForDirectoriesInDomains
    appdata = os.path.join(NSSearchPathForDirectoriesInDomains(14, 1, True)[0], APPNAME)
elif sys.platform == 'win32':
    appdata = os.path.join(os.environ['APPDATA'], APPNAME)
else:
    appdata = os.path.expanduser(os.path.join("~", "." + APPNAME))

try:
    os.stat(appdata)
except:
    os.mkdir(appdata)

logger = logging.getLogger(__name__)
returned_data = ""


class OAuthHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        global returned_data
        parsed_params = urlparse.urlparse(self.path)
        data = parsed_params.query
        if data[-1] == "/":
            data = data[:-1]
        self.send_response(200)
        self.end_headers()
        self.wfile.write("<html><h1>Please close this browser and return to publ</h1></html>")
        returned_data = data

    def log_request(self, code='-', size='-'):
        pass


def configure(args):
    site = args.site
    url = urlparse.urlparse(site)
    if not url.scheme:
        site = "http://" + site
    print "Configuring your site: " + site
    print "... Searching for your endpoints"

    soup = BeautifulSoup(requests.get(site).text, "html.parser")
    micropub_endpoint = soup.find('link', {'rel': 'micropub'})['href']
    auth_endpoint = soup.find('link', {'rel': 'authorization_endpoint'})['href']
    token_endpoint = soup.find('link', {'rel': 'token_endpoint'})['href']

    print "\t[micropub] " + micropub_endpoint
    print "\t[auth] " + auth_endpoint
    print "\t[token] " + token_endpoint

    auth_params = {
        'me': site,
        'client_id': 'http://publ.harryreeder.co.uk/',
        'redirect_uri': 'http://localhost:%d/' % (SERVER_PORT,),
        'scope': 'post'
    }
    auth_url = auth_endpoint + "?" + urlencode(auth_params)

    print "Attempting to open web browser at: " + auth_url
    webbrowser.open(auth_url)

    httpd = SocketServer.TCPServer(("", SERVER_PORT), OAuthHandler)
    while not returned_data:
        httpd.handle_request()

    data = parse_qs(returned_data)
    config = ConfigParser()

    # Read any existing config
    try:
        with open(os.path.join(appdata, "publ.ini"), 'r+b') as configfile:
            config.read_file(configfile)
    except IOError:
        pass

    try:
        config.add_section(data['me'][0])
    except DuplicateSectionError:
        # We're not actually going to do anything except let the user know we're about to overwrite the data
        print "This site already exists in the config, updating the information"

    config.set(data['me'][0], 'code', data['code'][0])
    config.set(data['me'][0], 'micropub', micropub_endpoint)
    config.set(data['me'][0], 'auth', auth_endpoint)
    config.set(data['me'][0], 'token', token_endpoint)


    default_site = ""
    while default_site.lower() not in ['y', 'n']:
        default_site = raw_input("Make %s the default site for publ? [Y/n] " % data['me'][0])
        if not default_site:
            default_site = "y"

    if default_site.lower() == "y":
        # Add the publ section if
        try:
            config.add_section('publ')
        except DuplicateSectionError:
            pass
        config.set('publ', 'default_site', data['me'][0])

    with open(os.path.join(appdata, "publ.ini"), 'w+b') as configfile:
        config.write(configfile)

    print "Done!"
    return


def publish(args):
    print "publish to " + args.site
    print " ".join(args.content)
    return


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='Commands', description='publ Micropub Client')

    publ_parser = subparsers.add_parser('post')
    publ_parser.add_argument("-s", "--site", dest="site", help="Site to publish to")
    publ_parser.add_argument('content', nargs=argparse.REMAINDER)
    publ_parser.set_defaults(func=publish)

    conf_parser = subparsers.add_parser('config')
    conf_parser.add_argument('site')
    conf_parser.add_argument('-a', '--address',
                             dest="ip", help="IP Address (or FQDN) to be used for the OAuth redirect")
    conf_parser.add_argument('-p', '--port',
                             dest="port", help="Port number to listen on for OAuth redirect (Default: 5252)")
    conf_parser.set_defaults(func=configure)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
