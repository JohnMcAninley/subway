# Reference notes on the real clocks

What we know about how the MTA's screens look and behave, and where it comes
from. `Clock` and the QML follow these; where we guessed, it says so.

## Sources

- **Adam Fisher-Cox, "Simplifying rider information in the New York City
  Subway"**: https://www.adamfishercox.com/portfolio/mta-platform-screens/
  He consulted on the newest design with the MTA Digital Services team. The
  page has the official designs (1920x480 countdown clock, 1080x1920 portrait
  screen), before and after videos of the rotation, and photos. Most of the
  `new` style comes from here.
- **Photos on Wikimedia Commons** of the LCD clocks (by Ytx21cn, Tdorante10
  and others) and the LED signs (by Adam Moss, Tdorante10, Billie Grace Ward,
  Jim.henderson and others).
- **MTA station list**: `http://web.mta.info/developers/data/nyct/subway/Stations.csv`
  for platform direction labels and boroughs.

## The three kinds of screen

The write-up names them:

- **Countdown clocks**: the horizontal screens hung over platforms. 1920x480.
- **Customer Information Screens**: portrait screens on walls or posts.
  1080x1920.
- **Subway entrance screens**: a strip of arrivals along the bottom of the
  advertising screens at street entrances. Not built here.

Since the redesign, all three use the same arrival data and update within
seconds of each other.

## Classic style (the older LCD countdown clocks)

- Two lines over a strip. Each line: `1.` bullet, terminal, `2 min`.
- The strip has the time and temperature in a box at the left, then a message
  such as "Please stand back from the platform edge".
- **Rotation**: line 1 is the next train. Line 2 goes through trains 2 to 5,
  one every 5 seconds, whatever their routes. (Timed from the write-up's
  "before" video.) So `max_trains` is 5 and `rotation_seconds` is 5.
- **Arriving train**: the line turns black with yellow text and shows `0 min`
  (photo at Union Sq in the write-up).
- On island platforms an arrow before the number points to the train's side.
  We don't show these: the feeds don't say which side.
- **Alerts** took over the whole screen: yellow text scrolling slowly on
  black, repeated twice, hiding the arrivals. The write-up calls this out as a
  problem. We scroll alerts in the strip instead, which is our own choice.

## New style (2025 redesign)

- Two lines fill the screen; no strip. Each line: a grey number on black,
  then a dark card with a large bullet, a bold headline over a smaller
  detail line, and bold minutes over a small grey `MIN`.
- **Headline**: "To better match the train announcements, we list the
  direction (i.e. 'Downtown & Brooklyn') instead of the terminal station."
  "Once in the destination borough, the terminal station appears in large
  text. In smaller text below, the complementary information (borough or
  terminal) appears." It varies by train on the same platform: at 49 St an R
  is "Downtown & Brooklyn" and a W is "Downtown".
  The MTA's table of these isn't public. `core/headline.py` works them out
  from boroughs; see below for where that is known to be wrong.
- **Rotation**: "stop displaying trains after the last unique route is
  shown", so the next few trains come round more often. In the "after" video
  the trains are W, N, R, W, R and line 2 alternates between trains 2 and 3,
  about 5.5 seconds each.
- **Rotation animation**: the outgoing line dims while its number rolls
  upwards, then the new one comes in, about a quarter of a second each way.
- **Arriving train**: the card inverts to a pale background with dark text
  (photos of 0-minute trains).
- **Alerts**, in two tiers:
  - changed or delayed service: a white card with a yellow bar at its left
    takes the place of line 2, with two lines of regular-weight text and
    bullets inline;
  - service not running: the same card takes over the whole screen, with a
    bold title ("No uptown [A][C] here") over the advice.
  We do the first and not the second: the alerts feed doesn't mark which
  alerts mean no service.
- Track-side arrows sit before the bullet on island platforms. Not shown, as
  above.

### Portrait screens

- Header: MTA logo at the left, the time with dimmer seconds at the right.
- Arrival cards in the top half at eye level, the same as the clock's lines
  without numbers; alerts in the bottom half.
- A screen covering both directions has been photographed two ways: one list
  sorted by time with track-side arrows (the official design), and split
  under a heading per direction with two trains each (Franklin Av). We do the
  second.
- Alerts are under "Happening now" or "Upcoming alerts". Each has a small
  bullet with a badge, a bold title ("Delays", "Planned work", "Stops
  Skipped"), a line such as "Updated 15 mins ago", and the text beside it.
  We show the text with "Happening now" or "Planned work" as the title.
- When two screens are paired, the right one shows the next train's stops as
  a strip map. Not built.

### Where our headlines differ from the real ones

- At 75 Av a Manhattan-bound F reads "Manhattan" over "Coney Island via Court
  Square"; we say "Manhattan & Brooklyn" over "Coney Island-Stillwell Av".
- At Franklin Av a 2 to Wakefield reads "Manhattan"; we say "Manhattan & The
  Bronx". Yet at Broadway in Astoria an N reads "Manhattan & Brooklyn", as we
  have it.
- The real screens shorten terminals ("Bay Ridge – 95 St", "Whitehall St",
  "Coney Island") and add notes we can't derive: an airplane and "JFK" for
  trains serving the airport, and "via Court Square" for the F's weekday
  route since the F and M swapped in December 2025.

## LED style (numbered lines)

- A matrix of dots that can each be red, green or amber. A platform sign has
  2 lines, about 16 rows of dots each and roughly 192 dots across;
  mezzanine signs have 4 lines.
- Each line: `1.` bullet, terminal, `2min` (no space). Letters are about 11
  dots tall with strokes 2 dots wide.
- Text is green. The bullet is a filled disc (a diamond for express) with
  the route unlit inside it: red for 1, 2 and 3, green for 4, 5 and 6.
- **Arriving train**: `0min` and the whole line changes colour, to amber at
  Times Sq and to red at Nevins St. We use amber.
- Line 2 rotates as on the classic clocks (photos show it numbered `3.`).
- Long terminals are abbreviated ("Flatbush Av-Bklyn Col"); we cut them
  short instead.
- No messages. An idle sign shows the date and time.
