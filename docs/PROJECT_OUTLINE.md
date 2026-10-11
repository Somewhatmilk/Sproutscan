# SproutScan — Project Outline & Details

**Purpose.** A farm-management web app that helps farmers — including elderly
farmers who didn't grow up with software — track crop statistics using cameras
and data. The core questions it answers, in plain language:

- What did I plant, where, and when?
- What stage is each crop at?
- Is this crop OK, or does it need a check?
- What did I spend, what did I harvest, what is it worth?

## Pages / UI outline

| Page | Route | Purpose |
|---|---|---|
| Login | `/` | Sign in (password + optional TOTP) |
| Dashboard | `/dashboard` | Farm list + latest crop status at a glance |
| Farms list | `/farms_list` | All plantations, add/delete, GPS + area |
| Farm overview | `/farm_overview` | Zones, cameras, crop-stage timeline |
| View plantation | `/view_plantation` | Detail view of one plantation |
| Update plantation | `/update_plantation` | Edit name/zone/crop metadata |
| Create report | `/createReport` | Record yield/cost/profit quantities |
| Retrieve reports | `/retrieveReports` | Browse past reports |
| Crop stage add | `/cropstage_add` | Add crop-stage observation |
| Crop stage view | `/cropstage` | Timeline of crop stages + AI confidence |
| Pest logs | `/pest_logs_list` `/pest_logs_entries` | Pest/incident logging |
| Users / security audit | `/users`, `/security_audit` | Admin + audit trail |
| Profile | `/profile` | Personal settings |
| Deleted farms | `/deleted_farms` | Soft-delete restore |

## Data model (SQLite)

- `plantations` — farm/plantation records (GPS, area, soft-delete)
- `farm_zones` — camera zones with status
- `crops` — crop records per zone
- `crop_stages` — stage observations with AI confidence
- `pest_log_folders` / `pest_log_entries` — pest/incident records
- `reports` — yield / cost / profit quantities
- `users` / `ai_profiles` — auth + per-farm AI config

## Camera + AI flow

1. Camera zone captures an image of the crop.
2. Backend computes a confidence score (0–100) with a status:
   - `>= 90` → "Normal"
   - `< 90` → "Needs to be checked"
3. The result is written to a detailed log and rendered on the dashboard.
4. The UI shows the status with a color and a bounding box.

This logic lives in `static/js/crop-utils.js` (`cropStatus`) and is unit-tested
in Node so the rule can't drift between frontend and backend.

## Tests

| Suite | Command | Status |
|---|---|---|
| JS helpers (8 tests) | `node --test tests/crop-utils.test.js` | passing |
| Flask smoke (3 tests) | `.venv/Scripts/python.exe -m pytest tests/test_app.py -q` | passing |

## Future addons (planned, not built)

- Export reports to CSV/PDF for bookkeeping
- Mobile-friendly layout for in-field phone use
- Offline-first: cache latest status for low-signal farms
- Simplified "big text" mode for elderly users
