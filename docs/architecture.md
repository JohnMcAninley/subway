# Where the clock should run

Notes from 2026-10-11 on how the clock should be put together once there is
more than one PC running it: which front end, where the logic lives, and how
it stays alive if John stops looking after it. Nothing here is decided. It
records what was weighed, so that the decision can be made quickly once the
hardware has been tested, and what follows from each answer.

## The decision that comes first: Qt or web

Everything else falls into place after this one.

There are two front ends today, both drawing the same `Board` from the same
Python core:

- **Qt** (`subway_clock/ui`): a window of its own, drawn with QML.
- **Web** (`subway_clock/web`): a page in a browser, served by a small Python
  server that runs the clock. It matches the Qt captures closely.

The lean is towards the web, with Qt kept until a browser is proven on the
real device.

For the web:

- The other things wanted all point at a page: settings from a phone (F3),
  fixing a gift from afar, a relay for a product, an ESP32 later.
- One renderer on everything: the device, a phone, a spare monitor.
- An update is a reload. Qt on a device needs F4's update and rollback built
  and trusted first.
- No Qt on the device: no PySide pin, and no LGPL package to ship (S4).

For Qt:

- It is lighter. Qt Quick straight to the framebuffer needs far less memory
  than a browser.
- It is self-contained: no browser to set up, boot into, or keep from showing
  an error page when the network drops.

### The test that decides it

On the Pi that turns up (H1), run the web page in a browser with no window
furniture and watch it for a while. None of this has been tried yet, and the
commands are a starting point:

1. Serve the clock: `python -m subway_clock.web --host 0.0.0.0`, on the Pi
   itself, or on the PC first to tell the browser's cost from the server's.
2. Open it full screen on the Pi: `chromium-browser --kiosk http://...:8000/`,
   or a lighter browser such as `cog` (WPE) if Chromium is too heavy.
3. Look at the things most work to draw: the `led` style (a scaled canvas
   under a mask of dots), the `classic` ticker scrolling, and the `new`
   style's last line rotating.
4. Note the memory left (`free -m`), the processor's load, how long it takes
   from power to trains, and what the screen shows if the network is down at
   boot.
5. Compare with the Qt app on the same Pi (F1).

Expectations, untested: a Pi Zero 2 W (512 MB) should manage a light kiosk
browser; a Pi 2 or 3 should; an original Model B or B+ is unlikely to run
either front end well.

- **If the page is smooth:** freeze the Qt front end, and the web becomes the
  product. Go on to "The plan if it is the web".
- **If it isn't:** Qt stays as the device's renderer on the Python core, and
  the web page serves phones and other screens through the local server, as
  it does now. No JavaScript core is needed.

Until then: no features for the QML alone.

## What is wanted of the result

- **Easy to keep up indefinitely.** A static page is easier to keep alive
  than a server.
- **An out.** Whether it is one friend's gift or a business with thousands of
  users, a device must keep working if John stops running anything. At worst
  its owner can point it straight at the MTA's feeds, or run the open source
  themselves.
- **The MTA's terms, if it is ever sold.** The feed terms say to host the
  data on a non-MTA server, and prohibit giving it to others directly from
  the MTA's (S2). One person's clock fetching for itself is one thing; a
  product whose every unit polls the MTA is what the clause is aimed at. So
  a product needs a relay, and a page that is purely static is not an option
  for one. None of this is legal advice.
- **Nothing personal to outside services.** Which stops a device watches
  hints at where its owner lives.

## The plan if it is the web

A static page that holds the logic, data from the MTA now and from a relay
later, and the open source as the relief valve.

- **The page** is plain files on a static host (GitHub Pages, Cloudflare
  Pages). The device is a browser in kiosk mode pointed at it.
- **The core runs in the page**, so it is ported to JavaScript: about 1,000
  lines (`clock.py`, `feeds.py`, `headline.py`, `stations.py`) and the
  settings menu (`ui/menu.py`), as plain modules with no build step, checked
  against the golden cases, which were written as the spec for another
  implementation. Node is needed to run them and isn't installed on the PC.
- **Settings live in the browser** (`localStorage`), and can also come from
  the address, so that a link such as `?stops=635S,R20S&style=new` is a
  whole clock.
- **The schedules need a job.** A browser can't read the MTA's schedule zips
  (see "What a browser may fetch"), and they are 5 MB and 19 MB. `gtfs.py`
  stays in Python as a build tool, run on a schedule (a GitHub Action),
  publishing the prepared tables as JSON beside the page. If the job stops,
  the page goes on with old tables and drifts as the schedules change. They
  measured 852 KB on 2026-10-15, 90 KB as GitHub Pages sends it compressed;
  the headsigns for every trip are 800 KB of that.
- **The feeds** come straight from the MTA, which a browser is allowed to
  read, until there is a relay.
- **To keep it alive:** a service worker keeps the page and the tables on the
  device after the first load, so that it starts with the host unreachable,
  or gone, for as long as the feeds answer. And as nobody refreshes a kiosk,
  the page checks for a new version now and then and reloads itself.
- **The out:** the feed address is a setting, so a device can be pointed at
  the relay or at the MTA. If the page's host goes, anyone can host the same
  files, or run the Python server at home, which stays in the repo.

Order of work:

1. The hardware test above.
2. Port the core and the menu to JavaScript, and switch the page to them,
   with the settings in the browser. This doesn't depend on the hardware, at
   the price of two cores for a while. **Done on 2026-10-14, ahead of the
   test**, so that the static page can be compared with Qt and the local
   server for a week or so, and carried on a phone to compare with the real
   clocks. It is `web/static/core` and `standalone.html`; the server's page
   is unchanged. The golden cases are run on it in a browser without a
   window rather than in Node. For now it reads the schedule zips through a
   CORS proxy, and in the page: about 25 MB downloaded and 180 MB unpacked
   on a first start, which takes seconds on a PC, kept in IndexedDB after.
3. The schedule job, the service worker and the reload. **The job is done
   (2026-10-15)**: `.github/workflows/pages.yml` runs `build_site.py
   --schedules` every hour and publishes `schedules.json` beside the page,
   which reads it in place of the zips, falling back to a proxy if one is
   set. The service worker and the reload are left.
4. The relay, when there is a product.

### During development: a CORS proxy for the schedules

Until something of ours handles the schedules (the job above, or a worker),
the page being developed still has to get at them, and a browser won't read
the zips. A CORS proxy may be the way through for development: something
that fetches an address on the page's behalf and passes the answer on with
the header that lets the page read it.

- A local one is a few lines, and the Python server in `subway_clock/web`
  could do it itself: pass the zips on, or better, serve the tables
  `gtfs.py` has already prepared, which are what the page wants in the end
  and far smaller than 19 MB of zip to unpack in a browser.
- A public one (there are several) needs nothing set up, but it is someone
  else's server with its own limits, and it sees every request.
- For development only. A page that others use shouldn't depend on one: it
  is one more thing to disappear, and it is the MTA's data handed on through
  a third party.

The Qt front end, if it is frozen, can stay on the Python core as it is. The
Python core stays in any case: as the reference the golden cases are
generated from, as the schedule job, and as the local server.

## The relay, when there is one

A plain mirror of the MTA's feeds: the same eight files, in the MTA's own
format, at another address, with the header that lets a page read them.

- It does no work per client, and everyone gets the same files, which is
  what a CDN caches best. Its load doesn't grow with the number of clocks.
- The core doesn't change: only the address it fetches from. The addresses
  are already in a file of their own (`core/feeds.json`).
- It can also offer the feeds trimmed, by route or by stop, to save the 430
  KB a device downloads every 10 seconds.
- Fetching every feed every 10 seconds is about 3.7 GB a day coming in,
  however many clocks there are. It can stop while nobody is asking.

Caching for 10 seconds is reasonable, as the MTA republishes about that
often. The delays add up (the feed's age, the relay's fetch, the cache, the
client's poll) to about half a minute at worst, inside the minute after
which the terms want users told. How it goes:

1. The relay fetches the feeds every 10 seconds, or when asked and its copy
   is older than that.
2. Its answers say `Cache-Control: public, max-age=10`.
3. The CDN keeps each answer under its address, and for 10 seconds gives it
   to everyone who asks without troubling the relay.
4. Then the next request goes through, and it starts again.
   `stale-while-revalidate` gives out the old copy while one request renews
   it; `stale-if-error` goes on giving it out for a while if the relay is
   down.

To check before building on it: on Cloudflare, a plain server behind the CDN
isn't touched by cached answers, but a Worker runs in front of the cache, so
each request probably still counts as one. Workers can run Python (through
Pyodide), with limits on packages and on processor time per request that
parsing 430 KB of protobuf may not fit; untested. A Worker also has no loop
of its own, so it would fetch when asked. A small server that is always on
runs today's code as it is.

## What was weighed and set aside

- **A core in C++, with Qt on one side and WebAssembly on the other.**
  Moving PySide to C++ Qt is mechanical, since the two APIs run in parallel
  and the QML wouldn't change. But the core is a thousand lines of lists and
  strings with nothing heavy in it, and the web side would need Emscripten.
  Its one real argument is the ESP32, which couldn't parse the feeds anyway
  and would want a server to send it a finished `Board`.
- **A JavaScript core inside Qt.** There are no practical JavaScript
  bindings for Qt Quick. QML has an engine of its own, but one without
  `fetch` or `async`, and the core would have to be written down to it.
- **The logic on a server, and thin clients.** One core, in Python, and
  every client only draws. It was the favourite until the out was asked for:
  a device that must be able to go straight to the MTA has to be able to run
  the whole clock itself. It remains the only way for clients that can't run
  the core, such as an ESP32; their out is that the server is open source
  and runs on any PC or Pi at home. If it is ever built for many clients,
  the two shapes are a board per client (thin clients, little shared between
  them, work that grows with the clients) and data per stop (the same for
  everyone watching it, about a thousand small files, but the client
  assembles its own board). Either way an answer should depend only on its
  address and the time, with arrival times and not minutes, and with the
  whole rotation for the client to step through, so that it can be cached.
- **The Python core in the browser, through Pyodide.** It would keep one
  core and avoid the port, for a download of several megabytes and a lot of
  memory: probably too much for a small Pi. Worth a look only if the port
  goes badly.
- **Everything local on the device, with the relay as a mirror.** The Pi
  runs the Python core and serves its own page, which is what exists today,
  and it has the best out. It is what the plan falls back to if the browser
  test fails. Against it as the main plan: an update needs F4, where a page
  needs a reload.

## What a browser may fetch

Tested 2026-10-11. A page may send a request to another site, but may only
read the answer if that site allows it with an `Access-Control-Allow-Origin`
header. Only browsers enforce this; Python, curl or a server fetch what they
like.

- The realtime feeds and the alerts feed (`api-endpoint.mta.info`) send
  `Access-Control-Allow-Origin: *`: a page can read them.
- The schedule zips (`rrgtfsfeeds.s3.amazonaws.com`) send no such header: a
  page can't.

## For now

John's own clock and the gift can run entirely on their own Pi, fetching
from the MTA directly, as the clock does today. Nothing in the plan above
has to exist first.
