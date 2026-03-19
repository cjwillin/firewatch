# 🔥 Firewatch

**Campsite availability monitor for Recreation.gov**

Firewatch monitors Recreation.gov campgrounds and sends email/push alerts when your desired campsites become available. Set up watches for specific dates and sites, or use templates to auto-generate watches for date ranges.

---

## Features

- **Watch Management**: Monitor specific campgrounds, dates, and site types
- **Smart Templates**: Auto-generate watches for weekends or custom date ranges
- **Email Alerts**: Get notified when sites become available (SMTP with 3-retry logic)
- **Push Notifications**: Optional Pushover integration
- **Duration Tracking**: See how long availability has been open
- **Background Scheduler**: Automatic checks every 5-15 minutes
- **API Deduplication**: Efficient Recreation.gov API usage (groups by campground+month)
- **Web UI**: Clean Tailwind CSS interface for managing watches
- **Health Monitoring**: `/api/health` endpoint for uptime checks

---

## Quick Start

### 1. Install Dependencies

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Python 3.11+ required** (tested with 3.11, not compatible with 3.14+)

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Required for email alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Optional but recommended
API_KEY=your-secret-key-here
POLL_INTERVAL_MINUTES=5
```

**Gmail App Password**: Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 3. Initialize Database

```bash
alembic upgrade head
```

This creates `firewatch.db` with WAL mode enabled.

### 4. Run the App

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Usage

### Creating a Watch

1. Click **"+ New Watch"**
2. Enter campground details:
   - **Campground ID**: From Recreation.gov URL (e.g., `232447` from `https://www.recreation.gov/camping/campgrounds/232447`)
   - **Campground Name**: Display name
   - **Check-in / Check-out**: Date range to monitor
   - **Site Type**: Standard, Electric, Full Hookup, Group, or Any
   - **Alert Email**: Where to send availability alerts
3. Click **"Create Watch"**

The scheduler will check availability every 5-15 minutes (configurable via `POLL_INTERVAL_MINUTES`).

### Using Templates

Templates auto-generate watches for date ranges:

1. Click **"Templates"** tab → **"+ New Template"**
2. Configure:
   - **Date Range**: Start and end dates (max 1 year)
   - **Days of Week**: Select which days to monitor (e.g., Fri+Sat for weekends)
   - **Site Type**: Same as watches
3. Click **"Create Template"**
4. Click **"Expand"** to generate watches

**Example**: Monitor all Friday/Saturday check-ins from June-August for Yosemite:
- Date Range: 2025-06-01 to 2025-08-31
- Days: Friday (5), Saturday (6)
- Result: ~24 watches created (8 Fridays + 8 Saturdays, 2-night stays)

### Manual Checks

Click **"Check Now"** on any watch to trigger an immediate availability check (bypasses scheduler).

### Resetting Alerts

After receiving an alert, the watch is marked `alerted=true` to prevent duplicate emails. Click **"Reset Alert"** to re-enable alerts for the same availability.

---

## API Reference

### Authentication

Include `X-API-Key` header for POST/PUT/DELETE requests:

```bash
curl -H "X-API-Key: your-key" -X POST http://localhost:8000/api/watches
```

GET requests (health checks, logs) are exempt.

### Endpoints

**Watches**
- `GET /api/watches` - List all watches
- `POST /api/watches` - Create watch
- `GET /api/watches/{id}` - Get watch
- `PUT /api/watches/{id}` - Update watch (pause/resume)
- `DELETE /api/watches/{id}` - Delete watch
- `POST /api/watches/{id}/reset-alert` - Reset alerted flag
- `POST /api/watches/{id}/check-now` - Manual availability check

**Templates**
- `GET /api/templates` - List templates
- `POST /api/templates` - Create template
- `GET /api/templates/{id}` - Get template
- `PUT /api/templates/{id}` - Update template
- `DELETE /api/templates/{id}` - Soft-delete template
- `POST /api/templates/{id}/expand` - Generate watches from template

**Admin**
- `GET /api/health` - Health check and scheduler status
- `GET /api/logs?limit=50&hours=24` - Recent alert logs

**Interactive Docs**: http://localhost:8000/docs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  USER                                                        │
│    ↓                                                         │
│  WEB UI (static/index.html + app.js)                       │
│    ↓                                                         │
│  FASTAPI (main.py)                                          │
│    ├─ routers/watches.py     - Watch CRUD + check-now      │
│    ├─ routers/templates.py   - Template CRUD + expansion   │
│    └─ routers/admin.py        - Health + logs               │
│    ↓                                                         │
│  DATABASE (SQLite + WAL)                                    │
│    ├─ watches                 - Active watches              │
│    ├─ watch_templates         - Date range templates        │
│    ├─ alert_log               - Alert history               │
│    └─ availability_window     - Duration tracking           │
│                                                              │
│  BACKGROUND SCHEDULER (APScheduler 3.10.4)                  │
│    ├─ check_all_watches()    - Runs every 5-15 min         │
│    │   → API deduplication per campground+month            │
│    │   → Sends email alerts (3-retry, 30s delay)           │
│    │   → Updates duration tracking                          │
│    └─ cleanup_old_availability_windows() - Daily cleanup    │
│                                                              │
│  RECREATION.GOV API                                         │
│    └─ Rate limited: 1 req/sec                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **API Deduplication**: Groups watches by `(campground_id, month)` to make ONE API call per group instead of N calls
- **Email Retry Logic**: 3 attempts with 30s delays for transient SMTP errors
- **Pushover is Optional**: Email success determines `alerted=true`, Pushover failure is non-blocking
- **Thread Safety**: Creates new `SessionLocal` per scheduler job (F-003)
- **Coalesce**: Scheduler jobs use `coalesce=True` (skip if previous run still executing)
- **1000 Watch Limit**: Prevents abuse and DB bloat
- **Duration Tracking**: `AvailabilityWindow` table tracks when sites first became available

---

## Configuration

### Poll Interval

Default: 5 minutes. Adjust via `.env`:

```env
POLL_INTERVAL_MINUTES=10
```

**Recommendation**: 5-15 minutes for active monitoring, 30-60 minutes for background scans.

### Rate Limiting

Default: 10 POST/PUT/DELETE requests per minute per IP.

To adjust, edit `main.py`:

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])
```

### SMTP Settings

**Gmail**:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

**Other Providers**:
- **SendGrid**: `smtp.sendgrid.net:587` with API key as password
- **Mailgun**: `smtp.mailgun.org:587`
- **AWS SES**: Region-specific endpoint (e.g., `email-smtp.us-east-1.amazonaws.com:587`)

### Pushover (Optional)

1. Create app at [pushover.net](https://pushover.net)
2. Add to `.env`:
   ```env
   PUSHOVER_APP_TOKEN=your-app-token
   ```
3. Add user key when creating watches

---

## Deployment

### Production Checklist

- [ ] Set strong `API_KEY` in `.env`
- [ ] Configure SMTP with production credentials
- [ ] Set `POLL_INTERVAL_MINUTES` appropriately
- [ ] Enable CORS restrictions in `main.py` (`allow_origins=["https://yourdomain.com"]`)
- [ ] Use a process manager (systemd, supervisor, PM2)
- [ ] Set up log rotation for `uvicorn` logs
- [ ] Monitor `/api/health` endpoint for uptime
- [ ] Back up `firewatch.db` regularly

### Systemd Service

Create `/etc/systemd/system/firewatch.service`:

```ini
[Unit]
Description=Firewatch Campsite Monitor
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/firewatch
Environment="PATH=/opt/firewatch/venv/bin"
ExecStart=/opt/firewatch/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable firewatch
sudo systemctl start firewatch
sudo systemctl status firewatch
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t firewatch .
docker run -d -p 8000:8000 --env-file .env firewatch
```

---

## Troubleshooting

### Email Alerts Not Sending

1. **Check SMTP credentials**:
   ```bash
   python3 -c "import smtplib; s=smtplib.SMTP('smtp.gmail.com',587); s.starttls(); s.login('user','pass'); print('OK')"
   ```

2. **Gmail**: Use [App Password](https://support.google.com/accounts/answer/185833), not your regular password

3. **Check logs**:
   ```bash
   tail -f logs/firewatch.log
   ```

### Scheduler Not Running

Check `/api/health`:

```bash
curl http://localhost:8000/api/health
```

Look for `"scheduler": {"running": true}`.

If stopped, restart the app:

```bash
sudo systemctl restart firewatch
```

### Database Locked

If you see "database is locked" errors:

1. Check WAL mode is enabled:
   ```bash
   sqlite3 firewatch.db "PRAGMA journal_mode"
   # Should output: wal
   ```

2. If not, re-initialize:
   ```bash
   rm firewatch.db
   alembic upgrade head
   ```

### Recreation.gov API Errors

- **429 Rate Limit**: Scheduler automatically retries with exponential backoff
- **500 Server Error**: Retried 3x, then marked as error
- **Malformed JSON**: Check Recreation.gov API status

---

## Development

### Running Tests

```bash
pytest
```

Tests cover:
- Database models and migrations
- Pydantic schema validation
- Recreation.gov API client
- Scheduler logic and error handling
- API endpoints (CRUD, auth, rate limiting)

### Database Migrations

Create migration after model changes:

```bash
alembic revision --autogenerate -m "Add new field"
alembic upgrade head
```

### Adding Features

1. Update models in `models.py`
2. Create migration: `alembic revision --autogenerate`
3. Update schemas in `schemas.py`
4. Add routes in `routers/`
5. Update UI in `static/`
6. Write tests

---

## License

MIT License - see LICENSE file

---

## Credits

Built with:
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **APScheduler** - Background job scheduler
- **Tailwind CSS** - UI styling
- **Recreation.gov API** - Campsite availability data

---

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/firewatch/issues)
- **Docs**: [Full Documentation](docs/)
- **API Docs**: http://localhost:8000/docs

---

**Happy camping! 🏕️**
