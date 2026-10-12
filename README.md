# SproutScan

A farm-management web app for keeping crop records in one place.

SproutScan tracks zones, crop progress, incidents, costs, yields, profits, and quantities. Camera-linked zones can also show a confidence status so a farmer knows what needs a closer look. The aim is simple: open the dashboard and understand what was planted, what it cost, and what it is producing without digging through a manual.

**Author:** Jonathan Choe ([Somewhatmilk](https://github.com/Somewhatmilk)) made a large contribution to the entire web application built here, including the security cleanup, testable UI logic, automated tests, and documentation. The first codebase began as a school team project during the 2025/26 web-development semester. This repository is the actively refined and secured continuation of that work.

## Showcase

These images come from the app's own media folder and show the farm dashboard's camera-zone views.

![Farm 1](static/images/farm1.jpg) ![Farm 2](static/images/farm2.jpg)

![Farm 3](static/images/farm3.jpg) ![Farm 4](static/images/farm4.jpg)

![Farm 5](static/images/farm5.jpg) ![Farms view](static/images/viewfarms.png)

## What it does

- Tracks plantations and crop-stage progress by farm zone
- Logs pest sightings and other crop incidents
- Records yield, cost, profit, and quantity reports
- Connects camera zones to an `Normal` / `Needs to be checked` confidence status
- Supports login with optional TOTP two-factor authentication

## Why it exists

The useful question is usually a plain one: what did I plant, what did it cost, and what is it worth now? SproutScan keeps those answers close to the surface with clear labels, short paths through the app, and no unnecessary jargon.

## Tech stack

- **Backend:** Python, Flask, WTForms, and Werkzeug
- **Data:** SQLite
- **Frontend:** Jinja2 templates, vanilla JavaScript, and CSS
- **AI/logs:** Camera-zone confidence logs rendered in the UI
- **Tests:** Node.js built-in test runner and pytest

## Tests

The JavaScript suite runs without an install:

```bash
node --test tests/crop-utils.test.js
```

The Flask smoke tests require the Python dependencies:

```bash
.venv/Scripts/python.exe -m pytest tests/test_app.py -q
```

## Documentation

- [`docs/PROJECT_OUTLINE.md`](docs/PROJECT_OUTLINE.md) covers the pages, data model, camera/AI flow, and planned additions.

## Quick start

```bash
# 1. Create a Python environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r req.txt

# 2. Configure local values
cp .env.example .env

# 3. Start the app
python app.py
```

Open `http://127.0.0.1:5000` in a browser.
