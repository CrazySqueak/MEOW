import subprocess
import time
import os

from config import getcampaths, get_filename_format, getcams

import asyncio
import tornado
import hashlib

def get_most_recent(cam):
    root = getcampaths(cam)[1]
    latest = sorted(os.listdir(root),reverse=True)
    if not latest: return None  # None found
    return os.path.join(root, latest[0])

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("web/index.html")

# API Functions
class LiveInfoHandler(tornado.web.RequestHandler):
    async def get(self):
        feeds = {}
        for cam in getcams():
            recent = get_most_recent(cam)
            if recent: feeds[cam] = {"src": f"/live/{cam}.ts", "hash": hash(recent)}
        self.write(feeds)

class RecentListHandler(tornado.web.RequestHandler):
    def get(self, cam):
        RECENT_ROOT = getcampaths(cam)[2]
        FILENAME_FMT = get_filename_format(cam)
        recent = []
        h = 0
        for fn in sorted(os.listdir(RECENT_ROOT), reverse=True):
            data = {
                "id": fn,
                "src": f"/v/{cam}/recent/" + fn,
                "thumb": f"/v/{cam}/thumbGIF/" + os.path.splitext(fn)[0] + ".gif",
                "title": time.strftime("%a %d %b, %H:%M", time.strptime(os.path.splitext(os.path.basename(fn))[0], FILENAME_FMT))
                }
            
            recent.append(data)
            h += hash(fn)
        self.write({"value": recent, "hash": h})

# Media functions
class FastMediaHandler(tornado.web.StaticFileHandler):
    # These two functions' existence speeds things up significantly and i have no clue how
    async def _flush(self, *args, **kwargs):
        # Call parent
        rval = await super().flush(*args, **kwargs)
        await asyncio.sleep(0)  # Let's not block the entire fucking application, tornado
        return rval  # Return value

    def compute_etag(self):
        hasher = hashlib.sha1()
        for part in self._write_buffer:
            hasher.update(part)
        return '"%s"' % hasher.hexdigest()

STREAMING_BUFFER_SIZE = 20*188
class LiveHandler(tornado.web.RequestHandler):
    async def get(self, cam):
        file = get_most_recent(cam)
        with open(file, "rb") as f:
            # Start from the latest point if we're only just starting stream
            try:
                f.seek(-STREAMING_BUFFER_SIZE, os.SEEK_END)
            except OSError:
                f.seek(0, os.SEEK_END)
            cur_pos = f.tell()
        while True:
            # Attempt to find any more bytes (if there are any)
            with open(file, "rb") as f:
                f.seek(cur_pos)
                while (data := f.read(STREAMING_BUFFER_SIZE)):  # Read the new data
                    self.write(data)
                    cur_pos += len(data)
                    await self.flush()
            await asyncio.sleep(0.5)  # We're done here

def make_app():
    routes = [
        (r"/", MainHandler),
        (r"/live/(.*).ts", LiveHandler),

        (r"/api/recent/(.*).json", RecentListHandler),
        (r"/api/live.json", LiveInfoHandler),
        
        (r"/resources/(.*)", FastMediaHandler, {"path": "web/resources"}),
    ]

    for cam in getcams():
        RECENT_ROOT, ARCHIVE_ROOT, SURVEY_ROOT = getcampaths(cam)[2:5]
        routes += [
            (rf"/v/{cam}/recent/(.*)", FastMediaHandler, {"path": RECENT_ROOT}),
            (rf"/v/{cam}/thumbGIF/(.*)", FastMediaHandler, {"path": SURVEY_ROOT}),
            (rf"/v/{cam}/old/(.*)", FastMediaHandler, {"path": ARCHIVE_ROOT}),
        ]
    
    return tornado.web.Application(routes)

async def main():
    app = make_app()
    app.listen(80)
    print("Server listening on port 80...")
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
