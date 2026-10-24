# Civic Eye – Citizen (user) files

## Files and where they go
| File | Goes in | What it does |
|---|---|---|
| index.html | templates/ | The citizen website (HTML structure) |
| style.css | static/ | Design: colours, layout, mobile view |
| script.js | static/ | Behaviour: camera, GPS, address lookup, form check, sending the report, Track page |
| app.py | main project folder | Backend: saves the photo and location, gives a complaint ID, lets the citizen track by ID |

These files only work inside the full `civic_eye_flask` project (they need Flask running).

## Steps for the citizen
1. Open the website (http://127.0.0.1:5000 on your laptop, or your online link).
2. Report page: tap the photo box to choose a photo, or click "Open camera" and "Capture photo". Allow camera permission when asked.
3. Click "Use my location" and allow location permission. The address fills in. You can also type it.
4. Click "Send report to BMC".
5. Note the complaint ID shown on the screen (for example CE-1001).
6. Later, open the Track page, enter the ID and press Search to see the department and status.

## Citizen routes in app.py
- GET / : the website
- POST /api/reports : send a photo and location
- GET /api/reports?id=CE-1001 : track one report (name and phone are never returned)
- GET /api/stats : the counters shown on the home page
