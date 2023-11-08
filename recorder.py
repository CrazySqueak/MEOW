import subprocess
import time
import threading
import os
import queue
import itertools
from multiprocessing.pool import ThreadPool
import _thread
import sys

from config import getcampaths, get_filename_format, get_archive_params
if len(sys.argv) < 2:
    print("Usage: recorder.py <camID>")
    sys.exit(1)
CAMID = sys.argv[1]

OUTFILES_ROOT, LATEST_ROOT, RECENT_ROOT, ARCHIVE_ROOT, SURVEY_ROOT = getcampaths(CAMID) 
FILENAME_FMT = get_filename_format(CAMID)
ARCHIVE_PARAMS = get_archive_params(CAMID)

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
console = Console()
progress = Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
    
    console=console)

# Get ffmpeg executable
from shutil import which
EXECUTABLE = which("ffmpeg")
if not EXECUTABLE:
    raise FileNotFoundError("Unable to locate FFmpeg executable! Please ensure that it is installed and on your $PATH!")
print("Using FFMPEG:", EXECUTABLE)

# Work out what platform we're on
import platform
SYSTEM = platform.system()
if SYSTEM == "Linux":
    print("Current System: Linux")
    DRIVER = "v4l2"
    LIST_CMD = "v4l2-ctl --list-devices"
elif SYSTEM == "Windows":
    print("Current System: Windows")
    DRIVER = "dshow"
    LIST_CMD = "ffmpeg -list_devices true -f dshow -i dummy"
else:
    print("Current System: Unrecognised.")
    print("No support is implemented for ", SYSTEM)

# Init video device
DEVICES = ["/dev/video0"]
if not DEVICES:
    print("No device selected.")
    print("Printing list of devices:")
    os.system(LIST_CMD)
    print("Please configure your devices in the program configuration and then restart the program.")
    assert False
print("Selected Devices:", ", ".join(DEVICES))
FFMPEG_DEVICE_ARGS = [x for device in DEVICES for x in ("-i", device)]  # FLATMAP WOO!!

MAX_RECENT = ARCHIVE_PARAMS[0]
MAX_FULLFILE_LEN = ARCHIVE_PARAMS[1]

def mux_video(src):
    muxed_file = os.path.join(RECENT_ROOT, os.path.splitext(os.path.basename(src))[0]) + ".mp4"
    if not os.path.exists(src): return

    tid = progress.add_task(description=f"Muxing {os.path.basename(src)}...", total=None)
    try:
        ffmpeg = subprocess.run([EXECUTABLE,
                                   "-y",
                                   "-i", src,
                                   "-c:v", "copy",
                                   "-c:a", "copy",
                                   muxed_file],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        assert ffmpeg.returncode == 0
    except:
        progress.remove_task(tid)
        console.log(f"[red]FFMPEG crashed! Unable to mux {src}!", highlight=False)
        os.remove(muxed_file)
        return

    os.remove(src)  # Delete old video
    progress.remove_task(tid)
    console.log("Muxed:", os.path.basename(muxed_file), highlight=False)
    
def archive_video(src):
    archive_file = os.path.join(ARCHIVE_ROOT, os.path.splitext(os.path.basename(src))[0]) + ".mp4"
    if not os.path.exists(src): return

    tid = progress.add_task(description=f"Archiving {os.path.basename(src)}...", total=None)
    try:
        ffmpeg = subprocess.run([EXECUTABLE,
                                   "-y",
                                   "-i", src,
                                   "-vf", "scale=-2:360",
                                   "-c:a", "copy",
                                   archive_file],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        assert ffmpeg.returncode == 0
    except:
        progress.remove_task(tid)
        console.log(f"[red]FFMPEG crashed! Unable to archive {src}!", highlight=False)
        os.remove(archive_file)
        return

    os.remove(src)  # Delete old video
    progress.remove_task(tid)
    console.log("Archived:", os.path.basename(archive_file), highlight=False)


def get_survey_name(src):
    return os.path.join(SURVEY_ROOT, os.path.splitext(os.path.basename(src))[0]) + ".gif"
SURVEY_FPS = ARCHIVE_PARAMS[2]
SURVEY_SPEED = ARCHIVE_PARAMS[3]
MAX_SURVEY_GIFS = ARCHIVE_PARAMS[4]
def gengif(src):
    gif_file = get_survey_name(src)
    if os.path.exists(gif_file): return 

    tid = progress.add_task(description=f"Generating survey gif for {os.path.basename(src)}...", total=None)
    try:
        ffmpeg = subprocess.run([EXECUTABLE,
                                   "-n",
                                   "-i", src,
                                 "-vf", f"setpts=PTS/{SURVEY_SPEED},fps={SURVEY_FPS},scale=-2:360:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                                 "-loop", "0",
                                 gif_file
                                 ],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        assert ffmpeg.returncode == 0
    except:
        progress.remove_task(tid)
        console.log(f"[red]FFMPEG crashed! Unable to create survey gif for {src}!", highlight=False)
        os.remove(gif_file)
        return
    
    progress.remove_task(tid)
    console.log("Created Survey Gif:", os.path.basename(gif_file), highlight=False)

def update_video_state():
    # Muxing: Latest -> Recent
    targets = []
    for fn in sorted(os.listdir(LATEST_ROOT), reverse=True):
        console.log("Scheduling", fn, "to be muxed.", highlight=False)
        targets.append(os.path.join(LATEST_ROOT, fn))
    video_processor.map(mux_video, targets)

    # Archiving: Recent -> Archive
    if len(os.listdir(RECENT_ROOT)) > MAX_RECENT:
        # Too many recent files
        num_excess = len(os.listdir(RECENT_ROOT)) - MAX_RECENT
        oldest_files = sorted(os.listdir(RECENT_ROOT))[:num_excess]  # WOO!! ISO 8601 GO BRRR

        targets = []
        for fn in oldest_files:
            console.log("Scheduling", fn, "to be archived.", highlight=False)
            targets.append(os.path.join(RECENT_ROOT, fn))
        video_processor.map(archive_video, targets)

    # Generate Survey Gifs: Recent c> Survey
    targets = []
    for fn in sorted(os.listdir(RECENT_ROOT), reverse=True):
        # Generate survey gifs
        if not os.path.exists(get_survey_name(fn)):
            console.log("Scheduling survey gif generation for", fn, ".", highlight=False)
            targets.append(os.path.join(RECENT_ROOT, fn))
    video_processor.map(gengif, targets)

    # Limit Number of Survey Gifs: Survey -> (deleted)
    if len(os.listdir(SURVEY_ROOT)) > MAX_SURVEY_GIFS:
        # Too many survey gifs
        #console.log("Too many survey gifs.")
        num_excess = len(os.listdir(SURVEY_ROOT)) - MAX_SURVEY_GIFS
        #console.log("Deleting the oldest", num_excess, highlight=False)
        oldest_files = sorted(os.listdir(SURVEY_ROOT))[:num_excess]  # WOO!! ISO 8601 GO BRRR
        for fn in oldest_files:
            console.log("Removed old survey gif:", fn, highlight=False)
            os.remove(os.path.join(SURVEY_ROOT, fn))

# Go!
progress.start()
with ThreadPool(1) as video_processor:
    while True:
        _thread.start_new_thread(update_video_state, ())  # Wheee
        
        # Write output
        current_file_name = time.strftime(FILENAME_FMT) + ".ts"
        current_file_name = os.path.join(LATEST_ROOT, current_file_name)

        tid = progress.add_task(description=f"Recording {os.path.basename(current_file_name)}...", total=None)
        try:
            ffmpeg = subprocess.Popen([EXECUTABLE,
                                             "-f", DRIVER,
                                       #"-framerate", "15",
                                             *FFMPEG_DEVICE_ARGS,

                                             "-y",

                                             "-t", str(MAX_FULLFILE_LEN),

                                             "-vf", "drawtext=text=%{localtime}:x=w-tw-10:y=h-th-10:fontcolor=Yellow:fontsize=24:fontfile=C:/Windows/Fonts/arialbd.ttf"
                                                    ",fps=10",
                                             
                                             "-c:v", "h264",
                                             "-c:a", "aac",
                                             "-f", "mpegts",
                                             current_file_name
                                             ],
                                            stderr=subprocess.DEVNULL)
            ffmpeg.wait()
        except KeyboardInterrupt:
            progress.remove_task(tid)
            console.log("[yellow]Recording interrupted by user.")
            console.log("Recording Finished:", os.path.basename(current_file_name), highlight=False)
            update_video_state()
            sys.exit()
        assert ffmpeg.returncode == 0
        progress.remove_task(tid)
        console.log("Recording Finished:", os.path.basename(current_file_name), highlight=False)
