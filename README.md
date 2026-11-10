# Crunchyroll RSS

An unofficial RSS 2.0 feed generator for Crunchyroll's public release calendar.
It publishes one all-releases feed and seven weekday feeds through GitHub Pages.

## Feeds

After GitHub Pages is enabled and the first workflow run succeeds:

- All releases: `https://YOUR-USERNAME.github.io/Crunchyroll-RSS/index.xml`
- Weekday feeds: `https://YOUR-USERNAME.github.io/Crunchyroll-RSS/feeds/tuesday.xml`
  (replace `tuesday` with monday, wednesday, thursday, friday, saturday, or sunday)

## Install / deploy

1. Create a **public** GitHub repository named `Crunchyroll-RSS`.
2. Upload the contents of this project to the repository's `main` branch.
3. Open **Settings → Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Open **Actions → Update Crunchyroll RSS → Run workflow**.
6. After it succeeds, open the Pages URL and subscribe to `index.xml` in your RSS reader.

The workflow also runs automatically every six hours and on pushes to `main`.
GitHub's scheduled workflows can start later than their exact cron time.

## Configuration

Edit `config.json`:

- `timezone`: timezone used for weekday grouping and displayed release times.
- `days_to_scan`: rolling number of calendar dates queried.
- `locale`: Crunchyroll page locale.
- `feed_title` / `feed_description`: RSS channel metadata.

The workflow defaults to `America/New_York` (Eastern Time). Change `FEED_TIMEZONE`
in `.github/workflows/update-and-deploy.yml` if needed.

## How it works / limitations

The project uses the community-maintained `PD-Codes/crunchyroll-api` Python
library to read the public `/simulcastcalendar` page. It calls the calendar
scraper with `premium_only=False`, so it does not intentionally restrict the
feed to Premium-only releases. It does not need your Crunchyroll login or password.

Crunchyroll does not provide a supported public RSS feed or a documented
all-future-releases API. The upstream calendar parser is best-effort HTML
scraping, so changes to Crunchyroll's page can temporarily break collection.
The calendar may only expose releases close to their release date; this is not
a guarantee of a complete season-ahead schedule. The feed contains what the
public calendar returns, not every title in the Crunchyroll catalog.

This project only publishes episode metadata and links. It does not access,
download, or stream video.

## Run locally

```bash
python -m pip install -r requirements.txt
python src/build_feed.py
```

Generated XML files are written to `docs/`.

## Attribution

Unofficial community project. Not affiliated with or endorsed by Crunchyroll.
The calendar extraction depends on
[PD-Codes/crunchyroll-api](https://github.com/PD-Codes/crunchyroll-api).
