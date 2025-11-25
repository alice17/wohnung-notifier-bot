"""
Module for WBM-specific functionality, specifically for auto-applying to listings.
"""
import logging
from typing import Dict, Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.notifier import TelegramNotifier, escape_markdown_v2

logger = logging.getLogger(__name__)


def _format_applicant_data_for_log(applicant_data: Dict[str, Any]) -> str:
    """
    Formats applicant data for console logging.

    Args:
        applicant_data: Dictionary containing the applicant information.

    Returns:
        A formatted string for logging.
    """
    lines = ["Application Data:"]
    for key, value in applicant_data.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _format_applicant_data_for_telegram(
    listing_url: str,
    applicant_data: Dict[str, Any]
) -> str:
    """
    Formats applicant data for Telegram notification with MarkdownV2.

    Args:
        listing_url: The URL of the listing applied to.
        applicant_data: Dictionary containing the applicant information.

    Returns:
        A formatted string for Telegram MarkdownV2.
    """
    escaped_url = escape_markdown_v2(listing_url)
    lines = [
        "✅ *Automatically applied to WBM listing*",
        "",
        f"🔗 [Listing]({escaped_url})",
        "",
        "📋 *Application Data:*"
    ]
    for key, value in applicant_data.items():
        escaped_key = escape_markdown_v2(key)
        escaped_value = escape_markdown_v2(value if value else "N/A")
        lines.append(f"  • *{escaped_key}:* {escaped_value}")
    return "\n".join(lines)


def apply_wbm(listing_url: str, wbm_config: Dict[str, Any], notifier: TelegramNotifier) -> None:
    """
    Applies to a WBM listing automatically.

    Args:
        listing_url: The URL of the WBM listing.
        wbm_config: The WBM applicant configuration dictionary.
        notifier: The notifier instance to send updates.
    """
    if not wbm_config:
        logger.warning("WBM configuration missing in 'wbm_applicant' section. Skipping auto-application.")
        return

    logger.info(f"Attempting to auto-apply for WBM listing: {listing_url}")
    try:
        # 1. Get the page
        response = requests.get(listing_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 2. Find the form
        # Often Powermail forms are multipart, or look for specific identifiers
        form = None
        forms = soup.find_all('form')
        for f in forms:
            if 'tx_powermail_pi1' in str(f):
                form = f
                break
        
        if not form:
            logger.error(f"Could not find application form on {listing_url}")
            return

        # 3. Prepare data
        data = {}
        
        # Extract all hidden inputs (tokens etc.)
        for input_tag in form.find_all('input', type='hidden'):
            if input_tag.get('name'):
                data[input_tag.get('name')] = input_tag.get('value', '')

        # Helper to find field name by partial match
        def get_field_name(partial_name: str) -> Optional[str]:
            for input_tag in form.find_all(['input', 'select', 'textarea']):
                name = input_tag.get('name', '')
                if f"[{partial_name}]" in name:
                    return name
            return None

        # Map config to form fields
        fields_to_fill = {
            'name': wbm_config.get('name'),
            'vorname': wbm_config.get('vorname'),
            'strasse': wbm_config.get('strasse', ''),
            'plz': wbm_config.get('plz', ''),
            'ort': wbm_config.get('ort', ''),
            'e_mail': wbm_config.get('email'),
            'telefon': wbm_config.get('telefon', '')
        }

        # Prepare applicant data for logging (human-readable keys)
        applicant_data = {
            'Anrede': wbm_config.get('anrede', 'Frau'),
            'Name': wbm_config.get('name'),
            'Vorname': wbm_config.get('vorname'),
            'Strasse': wbm_config.get('strasse', ''),
            'PLZ': wbm_config.get('plz', ''),
            'Ort': wbm_config.get('ort', ''),
            'E-Mail': wbm_config.get('email'),
            'Telefon': wbm_config.get('telefon', ''),
            'WBS vorhanden': 'Ja' if str(wbm_config.get('wbs', 'nein')).lower() in ['ja', 'yes', 'true', '1'] else 'Nein'
        }

        # Log applicant data to console
        logger.info(_format_applicant_data_for_log(applicant_data))

        for field, value in fields_to_fill.items():
            field_name = get_field_name(field)
            if field_name and value:
                data[field_name] = value
        
        # Handle Anrede (Select)
        anrede_name = get_field_name('anrede')
        if anrede_name:
            data[anrede_name] = wbm_config.get('anrede', 'Frau')

        # Handle WBS (Radio)
        wbs_name = get_field_name('wbsvorhanden')
        has_wbs = str(wbm_config.get('wbs', 'nein')).lower() in ['ja', 'yes', 'true', '1']
        if wbs_name:
            # Typically 1 for Yes, 0 for No in these forms
            data[wbs_name] = '1' if has_wbs else '0'

        # Handle Privacy Checkbox
        # The privacy checkbox usually has [] in the name, but there's also a hidden input without []
        # We need to find the actual checkbox to get the correct name
        privacy_cb = None
        for input_tag in form.find_all('input', type='checkbox'):
            name = input_tag.get('name', '')
            if 'datenschutzhinweis' in name:
                privacy_cb = input_tag
                break
        
        if privacy_cb:
            data[privacy_cb.get('name')] = privacy_cb.get('value', '1')

        # 4. Submit
        action = form.get('action')
        if not action:
            action = listing_url
        
        if action.startswith('/'):
            action = urljoin(listing_url, action)

        post_resp = requests.post(action, data=data)
        post_resp.raise_for_status()
        
        # Check success (heuristic)
        success_indicators = [
            "Vielen Dank" in post_resp.text,
            "versendet" in post_resp.text,
            "success" in post_resp.url,
            "vielen-dank" in post_resp.url
        ]
        if any(success_indicators):
            logger.info(f"Successfully applied to {listing_url}")
            telegram_message = _format_applicant_data_for_telegram(listing_url, applicant_data)
            notifier.send_message(telegram_message)
        else:
            logger.warning(f"Application might have failed for {listing_url}. Response might indicate error.")
            logger.warning(f"Status Code: {post_resp.status_code}")
            logger.warning(f"Response Text: {post_resp.text[:1000]}...")
                
    except Exception as e:
        logger.error(f"Failed to apply to WBM listing {listing_url}: {e}")

