import os, time

OUTFILES_ROOT = os.path.abspath("./recordings")
if not os.path.exists(OUTFILES_ROOT): os.mkdir(OUTFILES_ROOT)

# Latest: where containerless (MPEG-TS) files are kept
LATEST_ROOT = os.path.join(OUTFILES_ROOT, "latest")
if not os.path.exists(LATEST_ROOT): os.mkdir(LATEST_ROOT)

# Recent: where muxed mp4 files are kept
RECENT_ROOT = os.path.join(OUTFILES_ROOT, "recent")
if not os.path.exists(RECENT_ROOT): os.mkdir(RECENT_ROOT)

# Archive: where archived (reduced quality) files are kept
ARCHIVE_ROOT = os.path.join(OUTFILES_ROOT, "archived")
if not os.path.exists(ARCHIVE_ROOT): os.mkdir(ARCHIVE_ROOT)

# Survey: Where survey gifs are kept
SURVEY_ROOT = os.path.join(OUTFILES_ROOT, "survey")
if not os.path.exists(SURVEY_ROOT): os.mkdir(SURVEY_ROOT)

FILENAME_FMT = "%Y%m%dT%H%M%S"
