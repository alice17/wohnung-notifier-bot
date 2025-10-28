import requests
import time
import os
import json # Using json to store known listings
from bs4 import BeautifulSoup
import re # For cleaning text
import hashlib # If we need a fallback identifier
import logging
import sys
import datetime

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s - [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Use the attribute selector for the container holding the listings
LISTINGS_CONTAINER_SELECTOR = "div[wire\:loading\.remove]"
# Selector for individual listing items within the container (still need this to find them)
LISTING_ITEM_SELECTOR = "div[id^='apartment-']"
# --- END CONFIGURATION ---

# File to store the URLs of known listings
KNOWN_LISTINGS_FILE = "known_listings_by_url.json" # Renamed file

def load_settings():
    """Loads settings from settings.json."""
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
            # Basic validation
            if 'telegram' not in settings or 'scraper' not in settings:
                raise ValueError("settings.json is missing 'telegram' or 'scraper' sections.")
            return settings
    except FileNotFoundError:
        logger.error("FATAL: settings.json not found. Please create it.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error("FATAL: settings.json is not valid JSON.")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"FATAL: {e}")
        sys.exit(1)


def send_telegram_message(message, bot_token, chat_id):
    """Sends a message to your Telegram chat."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        logger.info(f"Telegram response: {response.json().get('ok', False)}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

def load_known_listings():
    """Loads the set of known listing URLs from the file.""" # Changed docstring
    if not os.path.exists(KNOWN_LISTINGS_FILE):
        return set()
    try:
        with open(KNOWN_LISTINGS_FILE, 'r') as f:
            data = json.load(f)
            # Ensure it's a set of strings (URLs)
            return set(data.get("listing_urls", [])) # Changed key
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading {KNOWN_LISTINGS_FILE}: {e}. Starting fresh.")
        return set()

def save_known_listings(listing_urls): # Changed parameter name
    """Saves the current set of listing URLs to the file.""" # Changed docstring
    try:
        with open(KNOWN_LISTINGS_FILE, 'w') as f:
            # Store as a list for JSON compatibility
            json.dump({"listing_urls": sorted(list(listing_urls))}, f, indent=2) # Changed key
    except IOError as e:
        logger.error(f"Error writing to {KNOWN_LISTINGS_FILE}: {e}")

def clean_text(text):
    """Remove extra whitespace and common units."""
    if not text:
        return "N/A"
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('€', '').replace('m²', '').strip()
    if text.endswith('.') or text.endswith(','):
        text = text[:-1].strip()
    return text if text else "N/A"

def generate_fallback_id(details):
    """Generates a hash based on key details if URL is missing."""
    key_info = f"{details.get('address', 'na')}-{details.get('sqm', 'na')}-{details.get('price_cold', 'na')}-{details.get('rooms', 'na')}"
    return hashlib.sha256(key_info.encode('utf-8')).hexdigest()[:16] # Short hash

def parse_listing_details(listing_soup):
    """Parses details from an individual listing's BeautifulSoup object."""
    details = {
        "address": "N/A",
        "sqm": "N/A",
        "price_cold": "N/A", # Kaltmiete
        "price_total": "N/A", # Gesamtmiete 
        "rooms": "N/A",
        "wbs": "N/A",
        "link": "N/A", 
        "identifier": None
    }

    # --- Try parsing the structured <dl> list (preferred) ---
    details_div = listing_soup.find('div', class_='list__details')
    if details_div:
        # Find the details link first
        link_tag = details_div.find('a', string=re.compile(r'Alle Details'))
        if link_tag and link_tag.get('href'):
            details['link'] = link_tag['href']
            details['identifier'] = details['link']

        dts = details_div.find_all('dt')
        for dt in dts:
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling('dd')
            if dd:
                dd_text = dd.get_text(separator=' ', strip=True)
                if "Adresse:" in dt_text:
                    address_button = dd.find('button')
                    details['address'] = address_button.get_text(strip=True) if address_button else clean_text(dd_text)
                elif "Wohnfläche:" in dt_text:
                    details['sqm'] = clean_text(dd_text)
                elif "Kaltmiete:" in dt_text:
                    details['price_cold'] = clean_text(dd_text)
                elif "Gesamtmiete:" in dt_text: 
                    details['price_total'] = clean_text(dd_text) 
                elif "Zimmeranzahl:" in dt_text:
                    details['rooms'] = clean_text(dd_text)
                elif "WBS:" in dt_text: 
                    # Clean the WBS text slightly (remove extra spaces)
                    wbs_status = clean_text(dd_text)
                    details['wbs'] = wbs_status if wbs_status != 'N/A' else 'Unknown' # Use 'Unknown' if empty after cleaning

    # --- Fallback: Try parsing the aria-label (less reliable for total price) ---

    # If we still don't have a URL identifier, create a fallback hash
    if not details['identifier']:
        # Include total price in fallback hash generation
        key_info = f"{details.get('address', 'na')}-{details.get('sqm', 'na')}-{details.get('price_cold', 'na')}-{details.get('price_total', 'na')}-{details.get('rooms', 'na')}-{details.get('wbs', 'na')}"
        details['identifier'] = hashlib.sha256(key_info.encode('utf-8')).hexdigest()[:16]
        logger.warning(f"No deeplink found for a listing. Using fallback ID: {details['identifier']}")

    return details

def convert_to_numeric(value_str):
    """Converts a string (e.g., '1.234,56') to a float."""
    if not isinstance(value_str, str) or value_str == 'N/A':
        return None
    try:
        # Replace thousand separators (.) and use comma (,) as decimal separator
        cleaned_str = value_str.replace('.', '').replace(',', '.')
        return float(cleaned_str)
    except (ValueError, TypeError):
        return None

def is_listing_filtered(details, filters):
    """Checks if a listing should be filtered out based on criteria in settings."""
    if not filters.get("enabled", False):
        return False # Filtering is disabled

    props = filters.get("properties", {})
    
    # --- Check Price (Total) ---
    price_total_rules = props.get("price_total", {})
    price_val = convert_to_numeric(details.get("price_total"))
    if price_val is not None:
        if price_total_rules.get("min") is not None and price_val < price_total_rules["min"]:
            logger.debug(f"FILTERED (Price): {details['price_total']}€ < Min price {price_total_rules['min']}€.")
            return True
        if price_total_rules.get("max") is not None and price_val > price_total_rules["max"]:
            logger.debug(f"FILTERED (Price): {details['price_total']}€ > Max price {price_total_rules['max']}€.")
            return True
            
    # --- Check Square Meters ---
    sqm_rules = props.get("sqm", {})
    sqm_val = convert_to_numeric(details.get("sqm"))
    if sqm_val is not None:
        if sqm_rules.get("min") is not None and sqm_val < sqm_rules["min"]:
            logger.debug(f"FILTERED (SQM): {details['sqm']}m² < Min size {sqm_rules['min']}m².")
            return True
        if sqm_rules.get("max") is not None and sqm_val > sqm_rules["max"]:
            logger.debug(f"FILTERED (SQM): {details['sqm']}m² > Max size {sqm_rules['max']}m².")
            return True

    # --- Check Rooms ---
    rooms_rules = props.get("rooms", {})
    rooms_val = convert_to_numeric(details.get("rooms"))
    if rooms_val is not None:
        if rooms_rules.get("min") is not None and rooms_val < rooms_rules["min"]:
            logger.debug(f"FILTERED (Rooms): {details['rooms']} < Min rooms {rooms_rules['min']}.")
            return True
        if rooms_rules.get("max") is not None and rooms_val > rooms_rules["max"]:
            logger.debug(f"FILTERED (Rooms): {details['rooms']} > Max rooms {rooms_rules['max']}.")
            return True

    # --- Check WBS ---
    wbs_rules = props.get("wbs", {})
    wbs_allowed = wbs_rules.get("allowed_values", [])
    if wbs_allowed: # Only check if the list is not empty
        wbs_val = details.get("wbs", "N/A").strip().lower()
        if wbs_val not in [v.lower() for v in wbs_allowed]:
            logger.debug(f"FILTERED (WBS): '{details['wbs']}' not in allowed list.")
            return True
            
    return False # Not filtered

def get_current_listings_data(target_url): 
    """Fetches website and returns dict of identifier -> details_dict."""
    listings_data = {}
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        with requests.get(target_url, headers=headers, timeout=20) as response:
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            listings_container = soup.select_one(LISTINGS_CONTAINER_SELECTOR)
            if not listings_container:
                logger.error(f"Could not find listing container '{LISTINGS_CONTAINER_SELECTOR}'")
                return {}

            listing_items = listings_container.select(LISTING_ITEM_SELECTOR)
            if not listing_items:
                if "Keine Wohnungen gefunden" in listings_container.get_text():
                    logger.info("No listings currently available on the page.")
                else:
                    logger.warning(f"Container found, but no items matching '{LISTING_ITEM_SELECTOR}'.")
                return {}

            for item_soup in listing_items:
                details = parse_listing_details(item_soup)
                if details['identifier']: # Only add if we have an identifier
                    listings_data[details['identifier']] = details # Map identifier to its details
                else:
                    logger.warning("Skipping a listing because no identifier (URL or fallback) could be determined.")

            return listings_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching website {target_url}: {e}")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred during parsing: {e}")
        return {}


def monitor(settings):
    """Main monitoring loop."""
    bot_token = settings['telegram']['bot_token']
    chat_id = settings['telegram']['chat_id']
    target_url = settings['scraper']['target_url']
    poll_interval = settings['scraper']['poll_interval_seconds']
    filters = settings.get('filters', {})


    logger.info("Enhanced Monitoring (using URLs) for inberlinwohnen.de started...")
    known_listing_ids = load_known_listings() # Now stores URLs or fallback IDs

    if not known_listing_ids:
         logger.info("No known listings file found or readable. Fetching baseline.")
         initial_listings_data = get_current_listings_data(target_url)
         if initial_listings_data:
             known_listing_ids = set(initial_listings_data.keys())
             save_known_listings(known_listing_ids)
             logger.info(f"Initial baseline set with {len(known_listing_ids)} listings.")
             send_telegram_message(f"✅ Monitoring started for {target_url}. Found {len(known_listing_ids)} initial listings.", bot_token, chat_id)
         else:
            logger.warning("Failed to get initial listings. Will retry.")

    while True:
        now = datetime.datetime.now()
        if 0 <= now.hour < 7:
            logger.info("Service is suspended between midnight and 7 AM. Sleeping for 5 minute.")
            time.sleep(300)
            continue
            
        try:
            logger.debug(f"Checking {target_url} for new listings...")
            current_listings_data = get_current_listings_data(target_url) # Dict: identifier -> details_dict
            current_listing_ids = set(current_listings_data.keys())

            if not current_listing_ids and known_listing_ids:
                logger.info("Current check returned no listings.")

            # Find NEW listings (in current but not in known)
            new_listing_ids = current_listing_ids - known_listing_ids

            if new_listing_ids:
                logger.info(f"Found {len(new_listing_ids)} new listing(s)!")
                for new_id in new_listing_ids:
                    details = current_listings_data[new_id]

                    # --- Apply filters ---
                    if is_listing_filtered(details, filters):
                        continue # Skip to the next new listing

                    # --- Escape underscores and square brackets in the link for Markdown ---
                    escaped_link = details['link'].replace('_', r'\_').replace('[', r'\[').replace(']', r'\]') if details[
                                                                              'link'] != 'N/A' else 'Link not found, ID: ' + new_id

                    # --- Format the message ---
                    message = (
                        f"🏠 *New Apartment Listing!*\n\n"
                        f"📍 *Address:* {details['address']}\n"
                        f"📜 *WBS:* {details['wbs']}\n"
                        f"💰 *Price (Cold):* {details['price_cold']} €\n"
                        f"💶 *Price (Total):* {details['price_total']} €\n"  
                        f"📏 *Size:* {details['sqm']} m²\n"
                        f"🚪 *Rooms:* {details['rooms']}\n\n"
                        f"🔗 *Details:* {escaped_link}" 
                    )
                    send_telegram_message(message, bot_token, chat_id)
                    time.sleep(1)

                # Update the known listings
                known_listing_ids.update(new_listing_ids)
                save_known_listings(known_listing_ids)

            elif current_listing_ids != known_listing_ids:
                # Some listings were removed
                removed_count = len(known_listing_ids - current_listing_ids)
                logger.info(f"{removed_count} listing(s) were removed.")
                known_listing_ids = current_listing_ids
                save_known_listings(known_listing_ids)
            else:
                logger.info("No changes detected.") 

            logger.info(f"Sleeping for {poll_interval} seconds...")
            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            send_telegram_message(f"⚠️ *Bot Error:* An unexpected error occurred: {e}", bot_token, chat_id)
            logger.info("Waiting 60 seconds before retrying...")
            time.sleep(60)

def main():
    """Load settings and start monitoring."""
    settings = load_settings()
    
    # Validate that we have the required telegram values
    bot_token = settings.get('telegram', {}).get('bot_token')
    chat_id = settings.get('telegram', {}).get('chat_id')

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in bot_token:
        logger.error("Bot token is missing or not configured in settings.json.")
        sys.exit(1)
    
    if not chat_id or "YOUR_TELEGRAM_CHAT_ID_HERE" in chat_id:
        logger.error("Chat ID is missing or not configured in settings.json.")
        sys.exit(1)
    
    logger.info(f"Starting monitor with chat ID: {chat_id}")
    monitor(settings)

if __name__ == "__main__":
    main()