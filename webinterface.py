import subprocess
import time
import os

from globalsettings import OUTFILES_ROOT, RECENT_ROOT, ARCHIVE_ROOT, SURVEY_ROOT, LATEST_ROOT, FILENAME_FMT

import asyncio
import tornado
import hashlib

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("web/index.html")

BUFFER_SIZE = 20*188
class LiveHandler(tornado.web.RequestHandler):
    def get_most_recent(self):
        return os.path.join(LATEST_ROOT, sorted(os.listdir(LATEST_ROOT),reverse=True)[0])
        
    async def get(self):
        mostrecent = self.get_most_recent()
        with open(mostrecent, "rb") as f:
            # Start from the latest point if we're only just starting stream
            try:
                f.seek(-BUFFER_SIZE, os.SEEK_END)
            except OSError:
                f.seek(0, os.SEEK_END)
            cur_pos = f.tell()
        while True:
            while self.get_most_recent() == mostrecent:
                # Attempt to find any more bytes (if there are any)
                try:
                    with open(mostrecent, "rb") as f:
                        f.seek(cur_pos)
                        while (data := f.read(BUFFER_SIZE)):  # Read the new data
                            self.write(data)
                            cur_pos += len(data)
                            await self.flush()
                except (OSError, FileNotFoundError) as e:
                    if "Stream is closed" in str(e): raise
                    print("OS Error while streaming:", e)
                    await asyncio.sleep(1)
                    continue
                await asyncio.sleep(0.5)  # We're done here
            
            # Newer file created. Close connection.
            return

class RecentListHandler(tornado.web.RequestHandler):
    def get(self):
        recent = []
        h = 0
        for fn in sorted(os.listdir(RECENT_ROOT), reverse=True):
            data = {
                "id": fn,
                "src": "/v/recent/" + fn,
                "thumb": "/v/thumbGIF/" + os.path.splitext(fn)[0] + ".gif",
                "title": time.strftime("%a %d %b, %H:%M", time.strptime(os.path.splitext(os.path.basename(fn))[0], FILENAME_FMT))
                }
            
            recent.append(data)
            h += hash(fn)
        self.write({"value": recent, "hash": h})


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

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/live.ts", LiveHandler),

        (r"/api/recent.json", RecentListHandler),
        
        (r"/resources/(.*)", FastMediaHandler, {"path": "web/resources"}),
        (r"/v/recent/(.*)", FastMediaHandler, {"path": RECENT_ROOT}),
        (r"/v/thumbGIF/(.*)", FastMediaHandler, {"path": SURVEY_ROOT}),
        (r"/v/old/(.*)", FastMediaHandler, {"path": ARCHIVE_ROOT}),
    ])

async def main():
    app = make_app()
    app.listen(80)
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
