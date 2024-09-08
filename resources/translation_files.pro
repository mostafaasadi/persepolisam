TEMPLATE = app
TARGET = ts
INCLUDEPATH += persepolis


# Input
SOURCES +=  ../persepolis/gui/about_ui.py \
            ../persepolis/gui/addlink_ui.py \
            ../persepolis/gui/after_download_ui.py \
            ../persepolis/gui/log_window_ui.py \
            ../persepolis/gui/mainwindow_ui.py \
            ../persepolis/gui/progress_ui.py \
            ../persepolis/gui/setting_ui.py \
            ../persepolis/gui/text_queue_ui.py \
            ../persepolis/gui/video_finder_progress_ui.py\
	    ../persepolis/scripts/after_download.py \
        ../persepolis/scripts/mainwindow.py \
	    ../persepolis/scripts/progress.py \
        ../persepolis/scripts/setting.py \
			../persepolis/scripts/video_finder_addlink.py
TRANSLATIONS += locales/ui.ts

