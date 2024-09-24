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

import yt_dlp
import time
import threading
from persepolis.constants import VERSION
from persepolis.scripts import logger
from persepolis.scripts.useful_tools import humanReadableSize, convertTime
from urllib.parse import urlparse, unquote
from pathlib import Path
import os
import multiprocessing


# This class gets yt-dlp log messages.
# see yt-dlp man page for more information.
class Ytdp_Logger():
    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            logger.sendToLog(msg, type="DEBUG")
        else:
            self.info(msg)

    # Normally, It's not necessary!
    def info(self, msg):
        pass

    def warning(self, msg):
        logger.sendToLog(msg, type="WARNING")

    def error(self, msg):
        logger.sendToLog(msg, type="ERROR")


# This class downloads m3u8 format files.
class Ytdp_Download():
    def __init__(self, add_link_dictionary, main_window, gid):
        self.downloaded_size = 0
        self.finished_threads = 0
        self.eta = "0"
        self.resume = False
        self.main_window = main_window
        self.download_speed_str = "0"
        self.gid = gid
        self.link = add_link_dictionary['link']
        self.name = add_link_dictionary['out']
        self.download_path = add_link_dictionary['download_path']
        self.ip = add_link_dictionary['ip']
        self.port = add_link_dictionary['port']
        self.proxy_user = add_link_dictionary['proxy_user']
        self.proxy_passwd = add_link_dictionary['proxy_passwd']
        self.proxy_type = add_link_dictionary['proxy_type']
        self.download_user = add_link_dictionary['download_user']
        self.download_passwd = add_link_dictionary['download_passwd']
        self.header = add_link_dictionary['header']
        self.user_agent = add_link_dictionary['user_agent']
        self.load_cookies = add_link_dictionary['load_cookies']
        self.referer = add_link_dictionary['referer']
        self.start_time = add_link_dictionary['start_time']
        self.end_time = add_link_dictionary['end_time']
        self.number_of_parts = 0
        self.process = None
        self.file_name = None
        self.file_size = None
        self.timeout = int(main_window.persepolis_setting.value('settings/timeout'))
        self.retry = int(main_window.persepolis_setting.value('settings/max-tries'))
        self.retry_wait = int(main_window.persepolis_setting.value('settings/retry-wait'))
        self.python_request_chunk_size = int(main_window.persepolis_setting.value('settings/chunk-size'))
        self.lock = False
        self.sleep_for_speed_limiting = 0
        self.not_converted_download_speed = 0
        self.download_percent = 0
        self.error_message = ''
        self.close_status = False
        # check certificate
        if str(main_window.persepolis_setting.value('settings/dont-check-certificate')) == 'yes':
            self.dont_check_certificate = True
        else:
            self.dont_check_certificate = False

        # number_of_threads can't be more that 64
        self.number_of_threads = int(add_link_dictionary['connections'])
        self.fragments = '0/0'

        self.thread_list = []
        # download_status can be in waiting, downloading, stop, error, eaused
        self.download_status = 'waiting'
        # update data_base
        dict_ = {'gid': self.gid,
                 'download_status': self.download_status}
        self.main_window.persepolis_db.updateVideoFinderTable2(dict_)

    # get file name if available
    # if file name is not available, then set a file name
    def getFileName(self):
        # set default file name
        parsed_linkd = urlparse(self.link)
        self.file_name = Path(parsed_linkd.path).name

        # URL might contain percent-encoded characters
        # for example farsi characters in link
        if self.file_name.find('%'):
            self.file_name = unquote(self.file_name)

        # check if user set file name or not
        if self.name:
            self.file_name = self.name

    # create yt-dlp session
    def createSession(self):
        self.getFileName()
        self.file_path = os.path.join(self.download_path, self.file_name)
        # youtube options must be added to youtube_dl_options_dict in dictionary format
        self.youtube_dl_options_dict = {'dump_single_json': True,
                                        'logger': Ytdp_Logger(),
                                        'quiet': True,
                                        'noplaylist': True,
                                        'no_warnings': True,
                                        'no-check-certificates': self.dont_check_certificate,
                                        'retries': self.retry,
                                        'socket_timeout': self.timeout,
                                        'outtmpl': self.file_path,
                                        'continue_dl': True
                                        }

        # cookies
        self.youtube_dl_options_dict['cookies'] = str(self.load_cookies)

        # referer
        if self.referer:
            self.youtube_dl_options_dict['referer'] = self.referer

        # user_agent
        if self.user_agent:
            self.youtube_dl_options_dict['user-agent'] = self.user_agent
        else:
            # set PersepolisDM user agent
            self.youtube_dl_options_dict['user-agent'] = 'PersepolisDM/' + str(VERSION.version_str)

        # load_cookies
        if self.load_cookies:
            # We need to convert raw cookies to http cookie file to use with youtube-dl.
            self.youtube_dl_options_dict['cookies'] = self.load_cookies

        # Proxy
        if self.ip:

            # ip + port
            ip_port = '{}:{}'.format(self.ip, str(self.port))

            if self.proxy_user:
                proxy_argument = '{}://{}:{}@{}'.format(self.proxy_type, self.proxy_user, self.proxy_passwd, ip_port)

            else:
                proxy_argument = '{}://{}'.format(self.proxy_type, ip_port)

            self.youtube_dl_options_dict['proxy'] = str(proxy_argument)

        if self.download_user:

            self.youtube_dl_options_dict['username'] = str(self.download_user)
            self.youtube_dl_options_dict['password'] = str(self.download_passwd)

        self.youtube_dl_options_dict['progress_hooks'] = [self.getStatus]
        # crete yt_dlp session
        self.ytdl_session = yt_dlp.YoutubeDL(self.youtube_dl_options_dict)

    # This method returns data and time in string format
    # for example >> 2017/09/09 , 13:12:26
    def nowDate(self):
        date = time.strftime("%Y/%m/%d , %H:%M:%S")
        return date

    def sigmaTime(self, time):
        hour, minute = time.split(":")
        return (int(hour) * 60 + int(minute))

    # nowTime returns now time in HH:MM format!
    def nowTime(self):
        now_time = time.strftime("%H:%M")
        return self.sigmaTime(now_time)

    # this method creates sleep time,if user sets "start time" for download.
    def startTime(self):
        # write some messages
        logger.sendToLog("Download starts at " + self.start_time + ' - GID: ' + self.gid, "INFO")

        # start_time that specified by user
        sigma_start = self.sigmaTime(self.start_time)

        # get current time
        sigma_now = self.nowTime()

        # this loop is continuing until download time arrival!
        while sigma_start != sigma_now and self.download_status == 'scheduled':
            time.sleep(2.1)
            sigma_now = self.nowTime()

    # This method will stop the download when the end_time is reached.
    def endTime(self):
        logger.sendToLog("End time is activated: " + self.end_time + ' - GID: ' + self.gid, "INFO")
        sigma_end = self.sigmaTime(self.end_time)

        # get current time
        sigma_now = self.nowTime()

        # while current time is not equal to end_time, continue the loop
        while sigma_end != sigma_now and (self.download_status == 'downloading' or self.download_status == 'paused'):

            # get current time
            sigma_now = self.nowTime()
            time.sleep(2.1)

        # Time is up!
        if (self.download_status == 'downloading' or self.download_status == 'paused'):
            logger.sendToLog("Time is up! - GID:" + self.gid, "INFO")

            # stop download
            self.downloadStop()

            # job is done so change end_time value to None in data_base
            self.main_window.persepolis_db.setDefaultGidInAddlinkTable(self.gid, end_time=True)

    # this method runs endTime in a thread.
    def runEndTimeThread(self):
        end_time_thread = threading.Thread(
            target=self.endTime)
        end_time_thread.setDaemon(True)
        end_time_thread.start()
        self.thread_list.append(end_time_thread)

    def getStatus(self, data):
        if 'filename' in data.keys():
            download_path_pluse_name = data['filename']
            self.file_name = Path(download_path_pluse_name).name

        if 'eta' in data.keys():
            if data['eta']:
                self.eta = convertTime(float(data['eta']))

        if 'speed' in data.keys():
            if data['speed']:
                download_speed, speed_unit = humanReadableSize(float(data['speed']), 'speed')
                self.download_speed_str = (str(download_speed)
                                           + " " + speed_unit + "/s")

        if 'downloaded_bytes' in data.keys():
            if data['downloaded_bytes']:
                self.downloaded_size = float(data['downloaded_bytes'])

        if 'total_bytes_estimate' in data.keys():
            if data['total_bytes_estimate']:
                self.file_size = float(data['total_bytes_estimate'])

            try:
                # Calculate download percent
                self.download_percent = int((self.downloaded_size / self.file_size) * 100)
            except:
                pass

        if ('fragment_index' in data.keys()) and ('fragment_count' in data.keys()):
            try:
                self.fragments = str(data['fragment_index']) + '/' + str(data['fragment_count'])
            except:
                self.fragments = 0

        if 'status' in data.keys():
            # download complete
            if data['status'] == 'finished':
                self.download_status = 'complete'
                self.downloaded_size = self.file_size
                self.fragments = 0
                self.download_percent = 100

            elif data['status'] == 'downloading':
                self.download_status = 'downloading'

        download_info_dict = {'gid': self.gid,
                              'download_status': self.download_status,
                              'file_name': self.file_name,
                              'eta': self.eta,
                              'download_speed_str': self.download_speed_str,
                              'downloaded_size': self.downloaded_size,
                              'file_size': self.file_size,
                              'download_percent': self.download_percent,
                              'fragments': self.fragments}
        # update data_base
        self.main_window.persepolis_db.updateVideoFinderTable2(download_info_dict)

    def tellStatus(self):
        # read from data_base
        download_info_dict = self.main_window.persepolis_db.searchGidInVideoFinderTable2(self.gid)

        if download_info_dict is None:
            download_info_dict = {'gid': self.gid,
                                  'download_status': self.download_status,
                                  'file_name': self.file_name,
                                  'eta': self.eta,
                                  'download_speed_str': self.download_speed_str,
                                  'downloaded_size': self.downloaded_size,
                                  'file_size': self.file_size,
                                  'download_percent': self.download_percent,
                                  'fragments': self.fragments,
                                  'error_message': self.error_message}

        else:
            self.file_size = download_info_dict['file_size']
            self.file_name = download_info_dict['file_name']
            self.file_path = os.path.join(self.download_path, self.file_name)
            self.download_status = download_info_dict['download_status']
            self.eta = download_info_dict['eta']
            self.download_speed_str = download_info_dict['download_speed_str']
            self.downloaded_size = download_info_dict['downloaded_size']
            self.download_percent = download_info_dict['download_percent']
            self.fragments = download_info_dict['fragments']
            self.error_message = download_info_dict['error_message']

        downloaded_size, downloaded_size_unit = humanReadableSize(download_info_dict['downloaded_size'])
        if self.file_size:
            file_size, file_size_unit = humanReadableSize(self.file_size)
        else:
            file_size = ''
            file_size_unit = ''

        # return information in dictionary format
        download_info = {
            'gid': self.gid,
            'file_name': self.file_name,
            'status': self.download_status,
            'size': str(file_size) + ' ' + file_size_unit,
            'downloaded_size': str(downloaded_size) + ' ' + downloaded_size_unit,
            'percent': str(self.download_percent) + '%',
            'connections': self.fragments,
            'rate': self.download_speed_str,
            'estimate_time_left': self.eta,
            'link': self.link,
            'error': self.error_message
        }
        return download_info

    # this method checks and manages download progress.
    def checkDownloadProgress(self):
        logger.sendToLog("Download starts! - GID:" + self.gid, "INFO")

        # Run this loop until the download is finished.
        while (self.download_status == 'downloading'):
            time.sleep(1)

        # If the downloaded size is the same as the file size, then the download has been completed successfully.
        if self.download_status == 'complete':
            logger.sendToLog('Download complete. - GID: ' + self.gid)

        # If the download is not complete and the user has not stopped the download, then the download has encountered an error.
        elif self.download_status != 'stopped':
            self.download_status = 'error'
            logger.sendToLog('Download Error - GID: ' + self.gid, 'ERROR')

        elif self.download_status == 'stopped':

            logger.sendToLog('Download stopped. - GID: ' + self.gid)

    def download(self):
        try:
            self.ytdl_session.download([self.link])
        except Exception as e:
            self.error_message = str(e)
            self.download_status = 'error'
            # update data_base
            dict_ = {'gid': self.gid,
                     'download_status': self.download_status,
                     'error_message': self.error_message}
            self.main_window.persepolis_db.updateVideoFinderTable2(dict_)

    def start(self):
        self.createSession()
        # update status and last_try_date in data_base
        if self.start_time:
            self.download_status = "scheduled"
        else:
            self.download_status = "waiting"

        # update data_base
        dict_ = {'gid': self.gid,
                 'download_status': self.download_status}
        self.main_window.persepolis_db.updateVideoFinderTable2(dict_)
        # get last_try_date
        now_date = self.nowDate()

        # update data_base
        dict_ = {'gid': self.gid, 'status': self.download_status, 'last_try_date': now_date}
        self.main_window.persepolis_db.updateDownloadTable([dict_])

        # call startTime if start_time is available
        # startTime creates sleep loop if user set start_time
        # see startTime method for more information.
        if self.start_time:
            self.startTime()

            # now startTime work is done! update data_base
            # if download stopped by user don't update data_base
            if self.download_status == "scheduled":
                # set start_time value to None in data_base!
                self.main_window.persepolis_db.setDefaultGidInAddlinkTable(self.gid, start_time=True)

        if self.download_status != 'stopped':
            self.download_status = 'downloading'
            # update data_base
            dict_ = {'gid': self.gid,
                     'download_status': self.download_status}
            self.main_window.persepolis_db.updateVideoFinderTable2(dict_)

            # if user set end_time
            if self.end_time:
                self.runEndTimeThread()

            self.process = multiprocessing.Process(target=self.download)
            self.process.start()
            self.checkDownloadProgress()
            self.close()
        else:
            # if start_time_status is "stopped" it means download Canceled by user
            logger.sendToLog("Download Canceled", "INFO")

    def close(self):
        # if download complete, so delete control file
        if self.download_status == 'complete':
            # update download_path in addlink_db_table
            add_link_dictionary = self.main_window.persepolis_db.searchGidInAddLinkTable(self.gid)

            add_link_dictionary['download_path'] = self.file_path
            self.main_window.persepolis_db.updateAddLinkTable([add_link_dictionary])

        # ask threads for exiting.
        for thread in self.thread_list:
            thread.join()

        logger.sendToLog("ytdlp_downloader is closed!")
        self.close_status = True

    def downloadPause(self):
        pass

    def downloadUnpause(self):
        pass

    def downloadStop(self):
        if self.process:
            self.process.terminate()
            self.download_status = 'stopped'
            # update data_base
            dict_ = {'gid': self.gid,
                     'download_status': self.download_status}
            self.main_window.persepolis_db.updateVideoFinderTable2(dict_)

    # This method limits download speed
    def limitSpeed(self, limit_value):
        pass
