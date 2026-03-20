# Firewatch Testing Guide

Complete end-to-end testing checklist for real-world verification.

## Prerequisites Setup

### 1. Gmail App Password (for SMTP)

**Create Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your Google account
3. Select app: "Mail"
4. Select device: "Other (Custom name)" → type "Firewatch"
5. Click "Generate"
6. Copy the 16-character password (no spaces)

**Save these credentials:**
- SMTP Host: `smtp.gmail.com`
- SMTP Port: `587`
- SMTP User: `your-gmail@gmail.com`
- SMTP Password: `xxxx xxxx xxxx xxxx` (16-char app password)

### 2. Environment Variables

Create `.env` file in `/Users/cjwillin/Development/firetower/firewatch/.env`:

```bash
# Required for email alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-16-char-app-password

# Optional API key (set to test auth)
API_KEY=test-key-12345

# Poll interval (minutes between checks)
POLL_INTERVAL_MINUTES=5
```

**For Fly.io production:**
```bash
fly secrets set SMTP_HOST=smtp.gmail.com
fly secrets set SMTP_PORT=587
fly secrets set SMTP_USER=your-gmail@gmail.com
fly secrets set SMTP_PASSWORD=your-16-char-app-password
fly secrets set API_KEY=production-key-xyz
fly secrets set POLL_INTERVAL_MINUTES=5
```

### 3. Populate Real Campgrounds

Run the import script to load real campground data:

```bash
cd /Users/cjwillin/Development/firetower/firewatch
python import_campgrounds.py
```

This populates the database with real Recreation.gov campgrounds for searching.

### 4. Start Local Server

```bash
cd /Users/cjwillin/Development/firetower/firewatch
uvicorn main:app --reload --port 8000
```

Server will be at: http://localhost:8000

---

## Testing Checklist

### Phase 1: Infrastructure ✓

- [ ] **Local server starts**
  - Run: `uvicorn main:app --reload --port 8000`
  - Visit: http://localhost:8000
  - Expected: Firewatch UI loads with sidebar

- [ ] **Database initialized**
  - Check: `ls firewatch.db` (file exists)
  - Expected: SQLite database file present

- [ ] **Health endpoint**
  - Visit: http://localhost:8000/api/health
  - Expected: JSON with `status: "healthy"`, database stats, scheduler info

- [ ] **API docs**
  - Visit: http://localhost:8000/docs
  - Expected: FastAPI Swagger UI with all endpoints

---

### Phase 2: Campground Search 🔍

- [ ] **Search works**
  - Type "Yosemite" in search box
  - Expected: Autocomplete dropdown with results
  - Verify: Campground names, locations shown
  - Verify: Initials displayed (no broken images)

- [ ] **Search result selection**
  - Click a campground from results
  - Expected: Details form expands
  - Verify: Campground name and location displayed
  - Verify: Site selection loading message appears

- [ ] **Site list loads**
  - Wait for sites to load
  - Expected: Checkboxes with site numbers
  - Verify: "Select All" and "Clear" buttons work
  - Test: Check/uncheck individual sites

- [ ] **Empty search**
  - Type "zzzzzzzzz" (nonsense)
  - Expected: "No campgrounds found" message

---

### Phase 3: Date Selection 📅

- [ ] **Date inputs work**
  - Select check-in date (future date)
  - Expected: Check-out minimum updates to day after check-in
  - Verify: Cannot select past dates

- [ ] **Site type dropdown**
  - Open site type dropdown
  - Expected: Any, Standard, Electric, Full Hookup, Group options
  - Test: Select different types

- [ ] **Date validation**
  - Try to create watch with check-out before check-in
  - Expected: Validation error

---

### Phase 4: Watch Creation 🎯

- [ ] **Create watch (manual test)**
  1. Search for "Kirk Creek"
  2. Select check-in: 7 days from now
  3. Select check-out: 10 days from now
  4. Site type: Any
  5. Click "Create Watch"
  6. Enter your email when prompted
  7. Expected: "Watch created!" alert
  8. Verify: Watch card appears in grid

- [ ] **Watch card display**
  - Verify: Campground initials shown
  - Verify: Status badge (Monitoring)
  - Verify: Date range with night count
  - Verify: Mini calendar with 14 days
  - Verify: Site info (which sites watched)
  - Verify: Delete button present

- [ ] **Multiple watches**
  - Create 2-3 watches for different campgrounds
  - Expected: All display in grid layout
  - Verify: Each has unique gradient color

---

### Phase 5: Email Alerts ✉️

**Test email delivery:**

- [ ] **SMTP configuration**
  - Verify `.env` has correct Gmail credentials
  - Test: Create watch with your email
  - Check: Scheduler logs for email attempts

- [ ] **Manual alert trigger**
  ```bash
  # In Python console or test script:
  from alerts import send_email
  import os

  result = send_email(
      to="your-email@gmail.com",
      subject="Firewatch Test",
      body="This is a test email from Firewatch.",
      smtp_host=os.getenv("SMTP_HOST"),
      smtp_port=int(os.getenv("SMTP_PORT")),
      smtp_user=os.getenv("SMTP_USER"),
      smtp_password=os.getenv("SMTP_PASSWORD")
  )

  print(f"Email sent: {result}")
  ```
  - Expected: Email arrives in inbox
  - Verify: Subject, body, formatting

- [ ] **Real availability alert**
  - Create watch for popular campground with likely availability
  - Wait for scheduler to run (5 minutes)
  - Expected: Email when sites found
  - Verify: Email contains:
    - Campground name
    - Dates
    - Available sites list
    - Booking URL link

---

### Phase 6: Recreation.gov API Integration 🏕️

- [ ] **API connectivity**
  - Create watch for any campground
  - Check logs: `tail -f logs/firewatch.log` (if logging to file)
  - Or terminal output for Recreation.gov API calls
  - Expected: No 429 rate limits, no timeouts

- [ ] **Availability parsing**
  - Watch logs when scheduler runs
  - Expected: "Checking availability for..." messages
  - Verify: Sites counted correctly
  - Verify: Available vs sold out detected

- [ ] **Error handling**
  - Create watch for invalid campground ID (if possible)
  - Expected: Graceful failure, error logged
  - Verify: Watch doesn't crash scheduler

---

### Phase 7: Scheduler 🤖

- [ ] **Scheduler starts**
  - Check startup logs
  - Expected: "Scheduler started successfully"
  - Expected: "Poll interval: 5 minutes"

- [ ] **Scheduled checks run**
  - Wait 5 minutes after creating watch
  - Check logs for "Running scheduled availability checks"
  - Expected: Each active watch checked
  - Verify: Timestamps updated

- [ ] **Alerted status**
  - When watch finds availability and sends email
  - Expected: Status badge changes to "Sites Found"
  - Expected: Watch marked as alerted in database

---

### Phase 8: API Endpoints 🔌

Test via http://localhost:8000/docs (Swagger UI)

- [ ] **GET /api/watches**
  - Expected: List of all watches
  - Verify: JSON structure matches schema

- [ ] **POST /api/watches**
  - Required fields: campground_id, campground_name, checkin_date, checkout_date, alert_email
  - Optional: site_type, site_numbers
  - Expected: 201 Created
  - Verify: Returns watch ID

- [ ] **DELETE /api/watches/{id}**
  - Get watch ID from list
  - Delete it
  - Expected: 204 No Content
  - Verify: Watch removed from UI

- [ ] **GET /api/campgrounds/search?q=Yosemite**
  - Expected: List of matching campgrounds
  - Verify: FTS search works

- [ ] **GET /api/campgrounds/{id}/sites**
  - Use campground ID from search
  - Expected: List of sites with site_id, site_name, site_type
  - Verify: Real data from Recreation.gov

- [ ] **GET /api/health**
  - Expected: Status, database stats, scheduler info

---

### Phase 9: Production (Fly.io) 🚀

- [ ] **Secrets configured**
  ```bash
  fly secrets list
  ```
  - Expected: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, API_KEY visible

- [ ] **Production URL works**
  - Visit: https://firewatch.fly.dev/
  - Expected: UI loads
  - Verify: No console errors

- [ ] **Create watch on production**
  - Use real email
  - Expected: Watch created
  - Verify: Appears in watch list

- [ ] **Production alerts work**
  - Wait for scheduler cycle
  - Expected: Email received from production
  - Verify: Links work, formatting correct

- [ ] **Logs accessible**
  ```bash
  fly logs
  ```
  - Expected: See scheduler activity
  - Verify: No errors

---

### Phase 10: Edge Cases 🐛

- [ ] **No email provided**
  - Try to create watch without email
  - Expected: Validation error

- [ ] **Invalid date range**
  - Check-out before check-in
  - Expected: Validation error

- [ ] **No sites selected (optional field)**
  - Create watch without selecting sites
  - Expected: Works, watches all sites

- [ ] **SMTP failure**
  - Temporarily set wrong SMTP password
  - Trigger alert
  - Expected: Error logged, watch continues

- [ ] **Recreation.gov timeout**
  - (Natural occurrence - wait for it)
  - Expected: Retry logic kicks in, eventually succeeds or logs error

- [ ] **Database lock**
  - Multiple scheduler runs simultaneously
  - Expected: SQLite handles concurrency gracefully

---

### Phase 11: UI/UX Polish ✨

- [ ] **Responsive layout**
  - Resize browser window
  - Expected: Sidebar and cards adapt
  - Mobile: Test on phone or DevTools mobile view

- [ ] **Loading states**
  - Site selection shows "Loading sites..."
  - Expected: Spinner or message visible

- [ ] **Empty state**
  - Delete all watches
  - Expected: "No watches yet" message with helpful text

- [ ] **Status badges**
  - Monitoring: Green badge
  - Sites Found: Orange badge
  - Verify: Colors match design system (#059669, #ea580c)

- [ ] **Mini calendars**
  - Verify: 14 days shown
  - Verify: Dates in watch range colored correctly
  - Verify: Days outside range grayed out

- [ ] **Typography**
  - Inspect fonts in DevTools
  - Expected: Instrument Sans everywhere
  - Verify: Tabular numerals on dates/stats

---

## Common Issues & Fixes

### Email not sending
- **Check:** Gmail App Password created (not regular password)
- **Check:** `.env` file has correct credentials
- **Check:** SMTP_PORT is `587` (not 465)
- **Test:** Run manual email test (Phase 5)

### Campgrounds not found
- **Check:** Database populated: `python import_campgrounds.py`
- **Check:** `campgrounds` table has rows
- **Test:** Search API directly: `/api/campgrounds/search?q=test`

### Scheduler not running
- **Check:** Startup logs for "Scheduler started successfully"
- **Check:** No errors in logs
- **Test:** Create watch, wait 5 minutes, check logs

### Recreation.gov 429 errors
- **Cause:** Too many requests (rate limited)
- **Fix:** Increase `POLL_INTERVAL_MINUTES` to 10 or 15
- **Note:** Scheduler respects 1 req/sec internally

### API key errors
- **Cause:** API_KEY env var set, but not provided in request
- **Fix:** Either unset API_KEY (dev mode) or include `X-API-Key` header
- **Note:** GET requests exempt from auth

---

## Success Criteria

✅ **Minimum viable:**
1. Can create watch via UI
2. Scheduler checks availability
3. Email arrives when sites found

✅ **Full feature set:**
1. All UI features work (search, site selection, date pickers)
2. Email alerts delivered reliably
3. Recreation.gov API integration solid (no crashes)
4. Multiple watches tracked concurrently
5. Production deployment stable

✅ **Production ready:**
1. All Phase 1-10 items checked
2. Tested with real email
3. Tested with real campgrounds
4. Tested on production URL
5. No critical bugs found

---

## Next Steps After Testing

1. **Monitor production logs** for first 24 hours
2. **Set up real watches** for popular campgrounds
3. **Document any bugs** found during testing
4. **Tune poll interval** based on Recreation.gov rate limits
5. **Add campground images** (scrape `preview_image_url` from API)
