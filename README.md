Here is a README.md file for the project you've built. You can save this as `README.md` in your project's folder.

-----

# 🏠 Berlin Apartment Notifier

A Python script that monitors `inberlinwohnen.de` for new apartment listings, filters them based on your criteria, and sends instant notifications via Telegram.

-----

## ✨ Key Features

-   **Intelligent Scraping:** Instead of watching the whole page, the script parses individual apartment listings, tracking them by their unique URL.
-   **Configurable Filters:** Only get notified about apartments that fit your needs. Filter by price, size (SQM), number of rooms, and WBS requirement.
-   **Telegram Notifications:** Get instant alerts delivered to your phone, giving you a head-start on your application.
-   **Resilient:** Stores known listings in a local file (`known_listings_by_url.json`) to pick up where it left off after a restart.
-   **Containerized:** Includes a `Containerfile` for easy deployment with Docker or Podman.

-----

## ⚙️ How It Works

1.  **Load Settings:** The script reads your configuration from `settings.json`.
2.  **Fetch & Parse:** It downloads the HTML from the target URL and uses `BeautifulSoup` to find all individual apartment listings.
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

You must create a `settings.json` file in the same directory as the script. This is where you'll put your Telegram credentials and define your apartment filters.

**Copy the template below and save it as `settings.json`:**

```json
{
  "telegram": {
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID_HERE"
  },
  "scraper": {
    "poll_interval_seconds": 120,
    "target_url": "https://www.inberlinwohnen.de/wohnungsfinder"
  },
  "filters": {
    "enabled": true,
    "properties": {
      "price_total": {
        "min": null,
        "max": 1500
      },
      "sqm": {
        "min": 50,
        "max": 100
      },
      "rooms": {
        "min": 2,
        "max": null
      },
      "wbs": {
        "allowed_values": [
          "nicht erforderlich",
          "N/A"
        ]
      }
    }
  }
}
```

#### a) Getting Telegram Credentials

1.  **Get your `bot_token`:**
    -   Open Telegram and start a chat with **`@BotFather`**.
    -   Send the `/newbot` command and follow the prompts.
    -   `BotFather` will give you a long **API Token**. This is your `bot_token`.

2.  **Get your `chat_id`:**
    -   After creating your bot, find it in your Telegram search and send it a `/start` message.
    -   Next, start a chat with a bot like **`@RawDataBot`**.
    -   It will reply with JSON. Find the `chat` object and copy the `id` number. This is your `chat_id`.

#### b) Configuring Filters

-   `enabled`: Set to `true` to enable filtering, `false` to get notified for *all* new listings.
-   `min` / `max`: Set the desired range for price, square meters, and rooms. Use `null` if you don't want to set a lower or upper limit.
-   `wbs`: The `allowed_values` list specifies which WBS statuses are acceptable. The script will filter out any listing whose WBS status is not in this list.

-----

## ▶️ How to Run

1.  Make sure your `settings.json` file is configured correctly.
2.  Navigate to your project directory in your terminal.
3.  Activate your virtual environment: `source venv/bin/activate`
4.  Run the script:
    ```bash
    python3 inberlinwohnen.py
    ```

The script will start, and you'll see log output in your terminal.

```
INFO - Starting monitor with chat ID: 123456789
INFO - Enhanced Monitoring (using URLs) for inberlinwohnen.de started...
INFO - No known listings file found or readable. Fetching baseline.
INFO - Initial baseline set with 15 listings.
INFO - Sleeping for 120 seconds...
```

-----

## 🐳 Running with Docker / Podman

A `Containerfile` is included for easy containerized deployment.

1.  **Build the image:**
    ```bash
    podman build -t wohnung-scraper .
    ```

2.  **Run the container:**
    Make sure your `settings.json` is complete before running.
    ```bash
    podman run -d --name wohnung-bot -v ./known_listings_by_url.json:/app/known_listings_by_url.json:z -v ./settings.json:/app/settings.json wohnung-scraper
    ```
    -   `-d`: Run in detached mode (in the background).
    -   The first `-v` mounts the known listings file into the container so it persists across restarts.
    -   The second `-v` mounts your settings file.

-----

## ⚖️ Disclaimer

-   **Polling Frequency:** Be respectful. Do not set the `poll_interval_seconds` too low. A 60-300 second (1-5 minute) interval is effective and won't spam the website's servers.
-   **Website Changes:** This script relies on the website's HTML structure. If `inberlinwohnen.de` changes its layout, the script may break and will need to be updated.

-----

## 📝 TODO

-   **Add More Websites:** Implement a provider pattern to easily add support for other real estate websites (e.g., `degewo`, `vonovia`).
-   **Support More Notifiers:** Add other notification channels like Email, Slack, or Pushbullet.
-   **Add a Test Suite:** Introduce `pytest` to write unit and integration tests for better reliability.
-   **Improve Error Handling:** Make the scraper more resilient to temporary network issues or minor HTML changes.
