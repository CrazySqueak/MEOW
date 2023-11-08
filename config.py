import json, os

with open("conf.json", "r") as f:
    config = json.load(f)

def getcams():
    return list(config.keys())

def getcampaths(cam):
    root = os.path.abspath(config[cam]["root"])

    latest = os.path.join(root, "latest")
    recent = os.path.join(root, "recent")
    archive = os.path.join(root, "archive")
    survey = os.path.join(root, "survey")
    for p in (root, latest, recent, archive, survey):
        if not os.path.exists(p): os.mkdir(p)
    return root, latest, recent, archive, survey

def get_filename_format(cam):
    return config[cam].get("filenameFormat", "%Y%m%dT%H%M%S")

def get_archive_params(cam):
    cconf = config[cam]
    return (
        cconf.get("maxRecentRecordings", 24),
        cconf.get("recordingLength", 3600),
        cconf.get("surveyFPS", 4),
        cconf.get("surveySpeed", 60),
        cconf.get("maxSurveyCount", 100),
        cconf.get("archivedRecordingResolution", 360),
        )
