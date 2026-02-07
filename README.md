# SFLA Tracker (Airtable Version)

SFLA usability tracker for THC UAM operations.

## Architecture
- **Backend:** Airtable Base `appBJW3FvPw5c659F`
- **Frontend:** Static HTML + Leaflet.js on GitHub Pages
- **Data Source:** KMZ files on OneDrive (synced by Po)

## URLs
- **Map UI:** (GitHub Pages URL after deployment)
- **Airtable Base:** https://airtable.com/appBJW3FvPw5c659F

## Workflow
- **Daily:** Pilots view map, click markers, update status
- **Monthly:** Export from Airtable for reporting
- **Bi-monthly:** Po syncs KMZ changes to Airtable

## Local Development
Just open `index.html` in a browser.

## Deployment
```bash
git add -A
git commit -m "Update"
git push
```
