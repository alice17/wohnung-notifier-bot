"""
WBM (Wohnungsbaugesellschaft Berlin-Mitte) auto-application handler.

This module provides automatic application submission for WBM apartment listings
by parsing their Powermail forms and submitting applicant data.
"""
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from src.appliers.base import ApplyResult, ApplyStatus, BaseApplier
from src.core.constants import REQUEST_TIMEOUT_SECONDS, Colors
from src.core.listing import Listing
from src.services.notifier import escape_markdown_v2

logger = logging.getLogger(__name__)

WBS_TRUTHY_VALUES = ('ja', 'yes', 'true', '1')


class WBMApplier(BaseApplier):
    """
    Auto-application handler for WBM (Wohnungsbaugesellschaft Berlin-Mitte).
    
    Handles automatic form submission for apartment listings on wbm.de
    by parsing Powermail forms and filling in applicant information.
    """

    URL_PATTERNS = [
        "https://www.wbm.de/",
        "https://wbm.de/",
    ]

    @property
    def name(self) -> str:
        """Return the applier name."""
        return "WBM"

    @property
    def url_patterns(self) -> List[str]:
        """Return URL patterns this applier handles."""
        return self.URL_PATTERNS

    def apply(self, listing: Listing) -> ApplyResult:
        """
        Submit an application for the given WBM listing.
        
        Args:
            listing: The listing to apply for.
            
        Returns:
            ApplyResult containing the outcome and details of the application.
        """
        if not self.is_configured():
            logger.warning(
                "WBM configuration missing in 'wbm_applicant' section. "
                "Skipping auto-application."
            )
            return ApplyResult(
                status=ApplyStatus.MISSING_CONFIG,
                message="WBM applicant configuration is missing"
            )

        listing_url = listing.identifier
        logger.info(f"Attempting to auto-apply for WBM listing: {listing_url}")

        try:
            form, soup = self._fetch_and_find_form(listing_url)
            
            # Check if the listing is no longer available
            if self._is_listing_unavailable(soup):
                logger.warning(f"Listing no longer available: {listing_url}")
                return ApplyResult(
                    status=ApplyStatus.LISTING_UNAVAILABLE,
                    message="Listing is no longer available on WBM website"
                )
            
            if not form:
                return ApplyResult(
                    status=ApplyStatus.FORM_NOT_FOUND,
                    message=f"Could not find application form on {listing_url}"
                )

            applicant_data = self._build_applicant_data()
            form_data = self._prepare_form_data(form, applicant_data)
            
            logger.info(self._format_data_for_log(applicant_data))

            submit_url = self._get_submit_url(form, listing_url)
            return self._submit_application(submit_url, form_data, applicant_data)

        except requests.RequestException as e:
            logger.error(f"Network error applying to WBM listing {listing_url}: {e}")
            return ApplyResult(
                status=ApplyStatus.FAILED,
                message=f"Network error: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to apply to WBM listing {listing_url}: {e}")
            return ApplyResult(
                status=ApplyStatus.FAILED,
                message=f"Unexpected error: {e}"
            )

    def _fetch_and_find_form(self, url: str) -> tuple[Optional[Tag], BeautifulSoup]:
        """
        Fetch the page and locate the Powermail application form.
        
        Args:
            url: The listing URL to fetch.
            
        Returns:
            Tuple of (form element or None, BeautifulSoup object).
        """
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        for form in soup.find_all('form'):
            if 'tx_powermail_pi1' in str(form):
                return form, soup

        logger.error(f"Could not find application form on {url}")
        return None, soup

    def _is_listing_unavailable(self, soup: BeautifulSoup) -> bool:
        """
        Check if the listing page indicates the listing is no longer available.
        
        WBM shows "Leider haben wir derzeit keine verfügbaren Angebote" when
        the listing has been removed or is no longer active.
        
        Args:
            soup: The BeautifulSoup object of the page.
            
        Returns:
            True if the listing is unavailable, False otherwise.
        """
        unavailable_indicators = [
            "keine verfügbaren Angebote",
            "leider haben wir derzeit keine",
            "no available offers",
        ]
        page_text = soup.get_text().lower()
        return any(indicator.lower() in page_text for indicator in unavailable_indicators)

    def _build_applicant_data(self) -> Dict[str, Any]:
        """
        Build human-readable applicant data dictionary from config.
        
        Returns:
            Dictionary with German field labels as keys.
        """
        has_wbs = str(self.config.get('wbs', 'nein')).lower() in WBS_TRUTHY_VALUES
        
        return {
            'Anrede': self.config.get('anrede', 'Frau'),
            'Name': self.config.get('name'),
            'Vorname': self.config.get('vorname'),
            'Strasse': self.config.get('strasse', ''),
            'PLZ': self.config.get('plz', ''),
            'Ort': self.config.get('ort', ''),
            'E-Mail': self.config.get('email'),
            'Telefon': self.config.get('telefon', ''),
            'WBS vorhanden': 'Ja' if has_wbs else 'Nein'
        }

    def _prepare_form_data(
        self,
        form: Tag,
        applicant_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare the form data dictionary for submission.
        
        Args:
            form: The BeautifulSoup form element.
            applicant_data: Human-readable applicant data.
            
        Returns:
            Dictionary mapping form field names to values.
        """
        data = self._extract_hidden_fields(form)
        
        field_mapper = FormFieldMapper(form)
        
        # Map config values to form fields
        # Map config values to form fields
        field_mappings = {
            'name': self.config.get('name'),
            'vorname': self.config.get('vorname'),
            'strasse': self.config.get('strasse', ''),
            'plz': self.config.get('plz', ''),
            'ort': self.config.get('ort', ''),
            'e_mail': self.config.get('email'),
            'telefon': self.config.get('telefon', '')
        }

        for field_key, value in field_mappings.items():
            field_name = field_mapper.find_field_name(field_key)
            if field_name and value:
                data[field_name] = value

        # Handle Anrede (Select dropdown)
        anrede_name = field_mapper.find_field_name('anrede')
        if anrede_name:
            data[anrede_name] = self.config.get('anrede', 'Frau')

        # Handle WBS (Radio button)
        wbs_name = field_mapper.find_field_name('wbsvorhanden')
        has_wbs = str(self.config.get('wbs', 'nein')).lower() in WBS_TRUTHY_VALUES
        if wbs_name:
            data[wbs_name] = '1' if has_wbs else '0'

        # Handle Privacy Checkbox
        privacy_field = self._find_privacy_checkbox(form)
        if privacy_field:
            data[privacy_field.get('name')] = privacy_field.get('value', '1')

        return data

    def _extract_hidden_fields(self, form: Tag) -> Dict[str, str]:
        """
        Extract all hidden input fields from the form.
        
        Args:
            form: The BeautifulSoup form element.
            
        Returns:
            Dictionary of hidden field names and values.
        """
        data = {}
        for input_tag in form.find_all('input', type='hidden'):
            name = input_tag.get('name')
            if name:
                data[name] = input_tag.get('value', '')
        return data

    def _find_privacy_checkbox(self, form: Tag) -> Optional[Tag]:
        """
        Find the privacy/data protection checkbox in the form.
        
        Args:
            form: The BeautifulSoup form element.
            
        Returns:
            The checkbox input element or None.
        """
        for input_tag in form.find_all('input', type='checkbox'):
            name = input_tag.get('name', '')
            if 'datenschutzhinweis' in name:
                return input_tag
        return None

    def _get_submit_url(self, form: Tag, listing_url: str) -> str:
        """
        Determine the form submission URL.
        
        Args:
            form: The BeautifulSoup form element.
            listing_url: The original listing URL (fallback).
            
        Returns:
            The absolute URL for form submission.
        """
        action = form.get('action')
        if not action:
            return listing_url
        
        if action.startswith('/'):
            return urljoin(listing_url, action)
        
        return action

    def _submit_application(
        self,
        url: str,
        form_data: Dict[str, str],
        applicant_data: Dict[str, Any]
    ) -> ApplyResult:
        """
        Submit the application form and check for success.
        
        Args:
            url: The submission URL.
            form_data: The prepared form data.
            applicant_data: Human-readable applicant data for logging.
            
        Returns:
            ApplyResult indicating success or failure.
        """
        response = requests.post(url, data=form_data, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        if self._is_submission_successful(response):
            logger.info(f"{Colors.GREEN}Successfully applied to {url}{Colors.RESET}")
            return ApplyResult(
                status=ApplyStatus.SUCCESS,
                message="Application submitted successfully",
                applicant_data=applicant_data
            )
        
        logger.warning(
            f"Application might have failed. "
            f"Status: {response.status_code}, "
            f"Response preview: {response.text[:500]}..."
        )
        return ApplyResult(
            status=ApplyStatus.FAILED,
            message="Application submission did not return expected success indicators",
            applicant_data=applicant_data
        )

    def _is_submission_successful(self, response: requests.Response) -> bool:
        """
        Check if the form submission was successful based on response.
        
        Args:
            response: The HTTP response from form submission.
            
        Returns:
            True if success indicators are found, False otherwise.
        """
        success_indicators = [
            "Vielen Dank" in response.text,
            "versendet" in response.text,
            "success" in response.url,
            "vielen-dank" in response.url
        ]
        return any(success_indicators)

    def _format_data_for_log(self, applicant_data: Dict[str, Any]) -> str:
        """
        Format applicant data for console logging.
        
        Args:
            applicant_data: Dictionary containing the applicant information.
            
        Returns:
            A formatted string for logging.
        """
        lines = ["Application Data:"]
        for key, value in applicant_data.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def format_success_message(
        self,
        listing_url: str,
        applicant_data: Dict[str, Any]
    ) -> str:
        """
        Format a success message for Telegram notification.
        
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


class FormFieldMapper:
    """
    Helper class to find form field names by partial matching.
    
    WBM Powermail forms use dynamic field names with patterns like
    tx_powermail_pi1[field][name] - this class helps locate them.
    """

    def __init__(self, form: Tag):
        """
        Initialize with a form element.
        
        Args:
            form: The BeautifulSoup form element to search.
        """
        self.form = form

    def find_field_name(self, partial_name: str) -> Optional[str]:
        """
        Find a form field name containing the partial name.
        
        Args:
            partial_name: The partial field name to search for.
            
        Returns:
            The full field name if found, None otherwise.
        """
        for input_tag in self.form.find_all(['input', 'select', 'textarea']):
            name = input_tag.get('name', '')
            if f"[{partial_name}]" in name:
                return name
        return None
