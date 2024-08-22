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
try:
    from PySide6.QtCore import Qt, QSize, QPoint, QThread, QTranslator, QCoreApplication, QLocale
    from PySide6.QtWidgets import QLineEdit, QInputDialog
    from PySide6.QtGui import QIcon
except:
    from PyQt5.QtCore import Qt, QSize, QPoint, QThread, QTranslator, QCoreApplication, QLocale
    from PyQt5.QtWidgets import QLineEdit, QInputDialog
    from PyQt5.QtGui import QIcon


from persepolis.constants import OS
from persepolis.gui.video_finder_progress_ui import VideoFinderProgressWindow_Ui
from persepolis.scripts.shutdown import shutDown
import subprocess
import platform

os_type = platform.system()


class ShutDownThread(QThread):
    def __init__(self, parent, category, password=None):
        QThread.__init__(self)
        self.category = category
        self.password = password
        self.main_window = parent

    def run(self):
        shutDown(self.main_window, category=self.category, password=self.password)


class VideoFinderProgressWindow(VideoFinderProgressWindow_Ui):
    def __init__(self, parent, gid_list, persepolis_setting):
        super().__init__(persepolis_setting)
        self.persepolis_setting = persepolis_setting
        self.main_window = parent

        # first item in the gid_list is related to video's link and second item is related to audio's link.
        self.gid_list = gid_list

        # this variable can be changed by checkDownloadInfo method in mainwindow.py
        # self.gid defines that which gid is downloaded.
        self.gid = gid_list[0]

        # this variable used as category name in ShutDownThread
        self.video_finder_plus_gid = 'video_finder_' + str(gid_list[0])

        # connect signals and sluts
        self.resume_pushButton.clicked.connect(self.resumePushButtonPressed)
        self.stop_pushButton.clicked.connect(self.stopPushButtonPressed)
        self.pause_pushButton.clicked.connect(self.pausePushButtonPressed)
        self.download_progressBar.setValue(0)
        self.limit_pushButton.clicked.connect(self.limitPushButtonPressed)

        self.limit_frame.setEnabled(False)
        self.limit_checkBox.toggled.connect(self.limitCheckBoxToggled)

        self.after_frame.setEnabled(False)
        self.after_checkBox.toggled.connect(self.afterCheckBoxToggled)

        self.after_pushButton.clicked.connect(self.afterPushButtonPressed)

        # add support for other languages
        locale = str(self.persepolis_setting.value('settings/locale'))
        QLocale.setDefault(QLocale(locale))
        self.translator = QTranslator()
        if self.translator.load(':/translations/locales/ui_' + locale, 'ts'):
            QCoreApplication.installTranslator(self.translator)

        # check if limit speed is activated by user or not
        add_link_dictionary = self.main_window.persepolis_db.searchGidInAddLinkTable(gid_list[0])

        limit = str(add_link_dictionary['limit_value'])
        if limit != '0':
            limit_number = limit[:-1]
            limit_unit = limit[-1]
            self.limit_spinBox.setValue(float(limit_number))
            if limit_unit == 'K':
                self.after_comboBox.setCurrentIndex(0)
            else:
                self.after_comboBox.setCurrentIndex(1)
            self.limit_checkBox.setChecked(True)

        self.after_comboBox.currentIndexChanged.connect(self.afterComboBoxChanged)

        self.limit_comboBox.currentIndexChanged.connect(self.limitComboBoxChanged)

        self.limit_spinBox.valueChanged.connect(self.limitComboBoxChanged)

        # set window size and position
        size = self.persepolis_setting.value(
            'ProgressWindow/size', QSize(595, 274))
        position = self.persepolis_setting.value(
            'ProgressWindow/position', QPoint(300, 300))
        self.resize(size)
        self.move(position)

    # close window with ESC key
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):

        # save window size and position
        self.persepolis_setting.setValue('ProgressWindow/size', self.size())
        self.persepolis_setting.setValue('ProgressWindow/position', self.pos())
        self.persepolis_setting.sync()

        self.hide()

    def resumePushButtonPressed(self, button):
        if self.status == "paused":
            # search gid in download_sessions_list
            for download_session_dict in self.main_window.download_sessions_list:
                if download_session_dict['gid'] == self.gid:
                    # unpause download
                    download_session_dict['download_session'].downloadUnpause()
                    break

    def pausePushButtonPressed(self, button):

        if self.status == "downloading":
            # search gid in download_sessions_list
            for download_session_dict in self.main_window.download_sessions_list:
                if download_session_dict['gid'] == self.gid:
                    # unpause download
                    download_session_dict['download_session'].downloadPause()
                    break

    def stopPushButtonPressed(self, button):

        # cancel shut down progress
        dictionary = {'category': self.video_finder_plus_gid,
                      'shutdown': 'canceled'}

        self.main_window.temp_db.updateQueueTable(dictionary)

        if self.status == "downloading":
            # search gid in download_sessions_list
            for download_session_dict in self.main_window.download_sessions_list:
                if download_session_dict['gid'] == self.gid:
                    # unpause download
                    download_session_dict['download_session'].downloadStop()
                    break

    def limitCheckBoxToggled(self, checkBoxes):

        # user checked limit_checkBox
        if self.limit_checkBox.isChecked() is True:
            self.limit_frame.setEnabled(True)
            self.limit_pushButton.setEnabled(True)

        # user unchecked limit_checkBox
        else:
            self.limit_frame.setEnabled(False)

            # check download status is "scheduled" or not!
            for i in [0, 1]:
                gid = self.gid_list[i]
                dictionary = self.main_window.persepolis_db.searchGidInDownloadTable(gid)
                status = dictionary['status']

                if status != 'scheduled':

                    for download_session_dict in self.main_window.download_sessions_list:
                        if download_session_dict['gid'] == self.gid:
                            # cancel the limitation of download speed
                            download_session_dict['download_session'].limitSpeed(10)
                            break

                else:
                    # update limit value in data_base
                    add_link_dictionary = {'gid': gid, 'limit_value': '0'}
                    self.main_window.persepolis_db.updateAddLinkTable([add_link_dictionary])

    def limitComboBoxChanged(self, connect):

        self.limit_pushButton.setEnabled(True)

    def afterComboBoxChanged(self, connect):

        self.after_pushButton.setEnabled(True)

    def afterCheckBoxToggled(self, checkBoxes):

        if self.after_checkBox.isChecked():

            self.after_frame.setEnabled(True)
        else:

            # so user canceled shutdown after download
            # write cancel value in data_base for this gid
            dictionary = {'category': self.video_finder_plus_gid,
                          'shutdown': 'canceled'}

            self.main_window.temp_db.updateQueueTable(dictionary)

    def afterPushButtonPressed(self, button):

        self.after_pushButton.setEnabled(False)

        # For Linux and Mac OSX and FreeBSD and OpenBSD
        if os_type != OS.WINDOWS:

            # get root password
            passwd, ok = QInputDialog.getText(
                self, 'PassWord', 'Please enter root password:', QLineEdit.Password)

            if ok:

                # check password is true or not!
                pipe = subprocess.Popen(['sudo', '-S', 'echo', 'hello'],
                                        stdout=subprocess.DEVNULL,
                                        stdin=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL,
                                        shell=False)

                pipe.communicate(passwd.encode())

                answer = pipe.wait()

                # Wrong password
                while answer != 0:

                    passwd, ok = QInputDialog.getText(
                        self, 'PassWord', 'Wrong Password!\nPlease try again.', QLineEdit.Password)

                    if ok:

                        pipe = subprocess.Popen(['sudo', '-S', 'echo', 'hello'],
                                                stdout=subprocess.DEVNULL,
                                                stdin=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL,
                                                shell=False)

                        pipe.communicate(passwd.encode())

                        answer = pipe.wait()

                    else:
                        ok = False
                        break

                if ok is not False:

                    # if user selects shutdown option after download progress,
                    # value of 'shutdown' will changed in temp_db for this progress
                    # and "wait" word will be written for this value.
                    # (see ShutDownThread and shutdown.py for more information)
                    # shutDown method will check that value in a loop .
                    # when "wait" changes to "shutdown" then shutdown.py script
                    # will shut down the system.

                    shutdown_enable = ShutDownThread(self.main_window, self.video_finder_plus_gid, passwd)
                    self.main_window.threadPool.append(shutdown_enable)
                    self.main_window.threadPool[-1].start()

                else:
                    self.after_checkBox.setChecked(False)
            else:
                self.after_checkBox.setChecked(False)

        else:
            # for Windows
            for gid in self.gid_list:
                shutdown_enable = ShutDownThread(self.main_window, self.video_finder_plus_gid)
                self.main_window.threadPool.append(shutdown_enable)
                self.main_window.threadPool[-1].start()

    def limitPushButtonPressed(self, button):

        self.limit_pushButton.setEnabled(False)

        if self.limit_comboBox.currentText() == "KiB/s":

            limit_value = str(self.limit_spinBox.value()) + str("K")
        else:
            limit_value = str(self.limit_spinBox.value()) + str("M")

        # if download was started before , send the limit_speed request to aria2 .
        # else save the request in data_base
        for i in [0, 1]:

            gid = self.gid_list[i]
            dictionary = self.main_window.persepolis_db.searchGidInDownloadTable(gid)
            status = dictionary['status']

            if status != 'scheduled':
                for download_session_dict in self.main_window.download_sessions_list:
                    if download_session_dict['gid'] == self.gid:
                        # limit  download speed
                        download_session_dict['download_session'].limitSpeed(limit_value)
                        break
            else:
                # update limit value in data_base
                add_link_dictionary = {'gid': gid, 'limit_value': limit_value}
                self.main_window.persepolis_db.updateAddLinkTable([add_link_dictionary])

    def changeIcon(self, icons):
        icons = ':/' + str(icons) + '/'

        self.resume_pushButton.setIcon(QIcon(icons + 'play'))
        self.pause_pushButton.setIcon(QIcon(icons + 'pause'))
        self.stop_pushButton.setIcon(QIcon(icons + 'stop'))
