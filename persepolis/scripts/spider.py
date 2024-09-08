# -*- coding: utf-8 -*-

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from persepolis.scripts.useful_tools import humanReadableSize
from requests.cookies import cookiejar_from_dict
from persepolis.constants import VERSION
from http.cookies import SimpleCookie
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote


# for more information about "requests" library , please see
# http://docs.python-requests.org/en/master/


def getFileNameFromLink(link):
    parsed_linkd = urlparse(link)
    file_name = Path(parsed_linkd.path).name

    # URL might contain percent-encoded characters
    # for example farsi characters in link
    if file_name.find('%'):
        file_name = unquote(file_name)

    return file_name

# spider function finds name of file and file size from header


def spider(add_link_dictionary):

    # get user's download request from add_link_dictionary
    link = add_link_dictionary['link']
    ip = add_link_dictionary['ip']
    port = add_link_dictionary['port']
    proxy_user = add_link_dictionary['proxy_user']
    proxy_passwd = add_link_dictionary['proxy_passwd']
    proxy_type = add_link_dictionary['proxy_type']
    download_user = add_link_dictionary['download_user']
    download_passwd = add_link_dictionary['download_passwd']
    header = add_link_dictionary['header']
    out = add_link_dictionary['out']
    user_agent = add_link_dictionary['user_agent']
    raw_cookies = add_link_dictionary['load_cookies']
    referer = add_link_dictionary['referer']

    # define a requests session
    requests_session = requests.Session()
    # check if user set proxy
    if ip:
        ip_port = '://' + str(ip) + ":" + str(port)
        if proxy_user:
            ip_port = ('://' + proxy_user + ':'
                       + proxy_passwd + '@' + ip_port)
        if proxy_type == 'socks5':
            ip_port = 'socks5' + ip_port
        else:
            ip_port = 'http' + ip_port

        proxies = {'http': ip_port,
                   'https': ip_port}

        # set proxy to the session
        requests_session.proxies.update(proxies)

    if download_user:
        # set download user pass to the session
        requests_session.auth = (download_user, download_passwd)

    # set cookies
    if raw_cookies:
        cookie = SimpleCookie()
        cookie.load(raw_cookies)

        cookies = {key: morsel.value for key, morsel in cookie.items()}
        requests_session.cookies = cookiejar_from_dict(cookies)

    # set referer
    if referer:
        requests_session.headers.update({'referer': referer})  # setting referer to the session

    # set user_agent
    if user_agent:
        requests_session.headers.update({'user-agent': user_agent})  # setting user_agent to the session
    else:
        user_agent = 'PersepolisDM/' + str(VERSION.version_str)

        # setting user_agent to the session
        requests_session.headers.update(
            {'user-agent': user_agent})

    # find headers
    try:
        response = requests_session.head(link, timeout=2.50, allow_redirects=True)
        header = response.headers
    except:
        header = {}

    filename = None
    file_size = None
    # check if filename is available in header
    if 'Content-Disposition' in header.keys():
        content_disposition = header['Content-Disposition']

        if content_disposition.find('filename') != -1:

            # so file name is available in header
            filename_splited = content_disposition.split('filename=')
            filename_splited = filename_splited[-1]

            # getting file name in desired format
            filename = filename_splited.strip()

    if not (filename):
        filename = getFileNameFromLink(link)

    # if user set file name before in add_link_dictionary['out'],
    # then set "out" for filename
    if out:
        filename = out

    # check if file_size is available
    if 'Content-Length' in header.keys():
        try:
            file_size = int(header['Content-Length'])

            # converting file_size to KiB or MiB or GiB
            file_size, unit = humanReadableSize(file_size)

            file_size_with_unit = str(file_size) + ' ' + unit
        except Exception:
            file_size_with_unit = 'None'
    else:
        file_size_with_unit = 'None'

    requests_session.close()
    # return results
    return filename, file_size_with_unit


# this function finds and returns file name for links.
def queueSpider(add_link_dictionary):
    filename = addLinkSpider(add_link_dictionary)[0]

    return filename


def addLinkSpider(add_link_dictionary):
    # get user's download information from add_link_dictionary
    for i in ['link', 'ip', 'port', 'proxy_user', 'proxy_passwd', 'download_user', 'download_passwd',
              'header', 'out', 'user_agent', 'proxy_type', 'load_cookies', 'referer']:
        if not (i in add_link_dictionary):
            add_link_dictionary[i] = None

    return spider(add_link_dictionary)
