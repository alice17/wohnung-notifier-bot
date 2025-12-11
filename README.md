# 🏠 Berlin Apartment Notifier

![Tests](https://github.com/alice17/wohnung-notifier-bot/actions/workflows/test.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/alice17/a61e9c704ca8a2e3d5a33aa58a89e625/raw/coverage-badge.json)
![Berlin](https://img.shields.io/badge/🏠-Berlin-black)

A Python script that monitors multiple German real estate websites (including `inberlinwohnen.de`, `immowelt.de`, `kleinanzeigen.de`, `ohne-makler.net`, `deutsche-wohnen.com`, and `vonovia.de`) for new apartment listings, filters them based on your criteria, and sends instant notifications via Telegram.

-----

## ✨ Key Features

-   **Multi-Website Support:** Natively scrapes listings from `inberlinwohnen.de`, `immowelt.de`, `kleinanzeigen.de`, `ohne-makler.net`, `deutsche-wohnen.com`, and `vonovia.de`. Note that `inberlinwohnen.de` is a portal that aggregates listings from Berlin's state-owned housing companies: Gewobag, HOWOGE, WBM, Gesobau, and Stadt und Land.
-   **Intelligent Scraping:** Instead of watching the whole page, the script parses individual apartment listings, tracking them by their unique URL.
-   **Configurable Filters:** Only get notified about apartments that fit your needs. Filter by price, size (SQM), number of rooms, WBS requirement, and Berlin boroughs.
-   **Telegram Notifications:** Get instant alerts delivered to your phone, giving you a head-start on your application.
-   **Resilient:** Stores known listings in a SQLite database (`listings.db`) for reliable persistence across restarts.
-   **Efficient Storage:** Database-backed storage with proper indexing for fast lookups and better performance with large datasets.
-   **Auto-Apply:** Automatically submit applications to supported housing providers (WBM, Gewobag, HOWOGE) when new matching listings are found.
-   **Containerized:** Includes a `Containerfile` for easy deployment with Docker or Podman.

-----

## ⚙️ How It Works

1.  **Load Settings:** The script reads your configuration from `settings.json`, including which scrapers to enable.
2.  **Fetch & Parse:** It runs all enabled scrapers, which download the HTML from their respective target sites and use `BeautifulSoup` to find all individual apartment listings.
3.  **Extract Details:** For each listing, it extracts key details like address, price, size, rooms, and the direct link.
4.  **Compare:** It compares the URLs of the currently visible listings against a stored list of URLs it has already seen.
5.  **Filter:** If a new, unseen listing is found, it's checked against the filters you defined in `settings.json`.
6.  **Alert:** If the new listing is not filtered out, a formatted notification is sent to your Telegram chat.
7.  **Repeat:** The script sleeps for a configurable interval and starts the process over.

-----

## 🚀 Setup Guide

### 1. Prerequisites

-   Python 3.9 or newer.
-   A Telegram account.

### 2. Installation

1.  **Clone or Download:**
    Get the script files in a folder on your computer or server.

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python Libraries:**
    Install the required libraries from `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configuration (`settings.json`)

You must create a `settings.json` file from the `settings.json.example`. This is where you'll put your Telegram credentials, enable scrapers, and define your apartment filters.

#### a) Getting Telegram Credentials

1.  **Get your `bot_token`:**
    -   Open Telegram and start a chat with **`@BotFather`**.
    -   Send the `/newbot` command and follow the prompts.
    -   `BotFather` will give you a long **API Token**. This is your `bot_token`.

2.  **Get your `chat_id`:**
    -   After creating your bot, find it in your Telegram search and send it a `/start` message.
    -   Next, start a chat with a bot like **`@RawDataBot`**.
    -   It will reply with JSON. Find the `chat` object and copy the `id` number. This is your `chat_id`.

#### b) Configuring Filters & Scrapers

-   `scrapers`: In this section, you can enable or disable scrapers by setting `"enabled": true` or `"enabled": false`.
-   `filters`:
    -   `enabled`: Set to `true` to enable filtering, `false` to get notified for *all* new listings.
    -   `min` / `max`: Set the desired range for price, square meters, and rooms. Use `null` if you don't want to set a lower or upper limit.
    -   `wbs` / `boroughs`: The `allowed_values` list specifies which values are acceptable. The script will filter out any listing whose value is not in this list.

#### c) Configuring Auto-Apply (Optional)

The `appliers` section allows automatic application submission to supported housing providers when new matching listings are found.

**Supported Providers:**
-   **WBM** (`wbm`): Simple HTTP-based form submission
-   **Gewobag** (`gewobag`): Browser-based automation with reCAPTCHA solving
-   **HOWOGE** (`howoge`): Browser-based automation with 4-step form completion

**WBM Configuration:**
```json
"appliers": {
  "wbm": {
    "enabled": true,
    "anrede": "Frau",
    "name": "Mustermann",
    "vorname": "Erika",
    "strasse": "Musterstraße 1",
    "plz": "10115",
    "ort": "Berlin",
    "email": "erika.mustermann@example.com",
    "telefon": "0123456789",
    "wbs": "nein"
  }
}
```

**Gewobag Configuration:**
```json
"appliers": {
  "gewobag": {
    "enabled": true,
    "anrede": "Frau",
    "vorname": "Erika",
    "nachname": "Mustermann",
    "email": "erika.mustermann@example.com",
    "telefon": "0123456789",
    "mobilfunknummer": "0170123456789",
    "strasse": "Musterstraße",
    "hausnummer": "1",
    "plz": "10115",
    "ort": "Berlin",
    "adresszusatz": "",
    "anmerkungen": "",
    "anzahl_erwachsene": 1,
    "anzahl_kinder": 0,
    "wbs": "nein",
    "anfrage_fuer": "für mich selbst",
    "ueber_55": "nein",
    "wbs_datei": ""
  }
}
```

**Additional Fields for Senior Housing (Seniorenwohnung):**
-   `ueber_55`: Set to `"ja"` if applicant is 55+ years old (required for senior housing listings)
-   `wbs_datei`: Path to your WBS PDF file for upload (some listings require document upload)

**HOWOGE Configuration:**
```json
"appliers": {
  "howoge": {
    "enabled": true,
    "vorname": "Erika",
    "nachname": "Mustermann",
    "email": "erika.mustermann@example.com"
  }
}
```

**Note:** HOWOGE has a simple 4-step application process that automatically confirms WBS, income, and credit check requirements before submitting your contact details.

**Note for Gewobag and HOWOGE:** These appliers use Playwright for browser automation and require additional setup:
```bash
pip install playwright playwright-recaptcha
playwright install chromium
```

The applier handles dynamic form variations automatically - it detects whether the listing is a standard apartment or senior housing and fills the appropriate fields.

-----

## ▶️ How to Run

1.  Make sure your `settings.json` file is configured correctly.
2.  Navigate to your project directory in your terminal.
3.  Activate your virtual environment: `source venv/bin/activate`
4.  Run the script:
    ```bash
    python3 main.py
    ```

The script will start, and you'll see log output in your terminal.

```
INFO - Setting up the application with 2 sources...
INFO - Database initialized successfully
INFO - Loaded 0 listings from database
INFO - Scraper 'inberlinwohnen' successfully returned 10 listings.
INFO - Scraper 'immowelt' successfully returned 25 listings.
INFO - Initial baseline set with 35 listings.
INFO - Sleeping for 120 seconds...
```

-----

## 📦 Database Storage

The application uses SQLite to store known listings, providing better performance and reliability compared to JSON files.

### Overview

Starting from the latest version, the scraper uses a SQLite database (`listings.db`) as its primary storage backend. This modern storage solution offers significant advantages over the previous JSON-based approach, including indexed queries for faster lookups, transaction safety for data integrity, and efficient batch operations. The database automatically tracks metadata such as when each listing was first seen and last updated, making it easier to analyze listing patterns and manage the dataset. The database schema is designed specifically for apartment listings with proper indexing on frequently-queried columns, ensuring optimal performance even with thousands of listings. For detailed information about the database structure, operations, and advanced usage, refer to [DATABASE.md](DATABASE.md).

### Database Location

-   Default location: `listings.db` in the project root directory
-   The database is created automatically on first run
-   No manual setup required

### Database Features

-   **Automatic Schema Creation:** The database schema is created automatically on startup
-   **Indexed Queries:** Fast lookups using indexed identifier and source columns
-   **Transaction Safety:** All operations use database transactions for data integrity
-   **Backup Friendly:** Single file database makes backups simple


## 🐳 Running with Docker / Podman

A `Containerfile` is included for easy containerized deployment.

1.  **Build the image:**
    ```bash
    podman build -t wohnung-scraper .
    ```

2.  **Run the container:**
    Make sure your `settings.json` is complete before running.
    ```bash
    podman run -d --name wohnung-bot \
      -v ./listings.db:/app/listings.db:z \
      -v ./settings.json:/app/settings.json:z \
      wohnung-scraper
    ```
    -   `-d`: Run in detached mode (in the background).
    -   The first `-v` mounts the database file into the container so it persists across restarts.
    -   The second `-v` mounts your `settings.json` file (required - the container expects this file to be mounted as a volume).
    
    **Note:** `settings.json` must be mounted as a volume and is not included in the container image. This allows you to update your configuration without rebuilding the image.

-----

## ⚖️ Disclaimer

-   **Polling Frequency:** Be respectful. Do not set the `poll_interval_seconds` too low. A 120-300 second (2-5 minute) interval is effective and won't spam the websites' servers.
-   **Website Changes:** This script relies on the websites' HTML structure. If any of the supported websites changes its layout, the corresponding scraper may break and will need to be updated.
