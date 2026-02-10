"""
Berlinovo auto-application handler.

This module provides automatic contact request (Kontaktanfrage) submission for
Berlinovo apartment listings at berlinovo.de by locating the contact form on
the listing page and submitting applicant data.
"""
import logging
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from src.appliers.base import ApplyResult, ApplyStatus, BaseApplier
from src.core.constants import REQUEST_TIMEOUT_SECONDS, Colors
from src.core.listing import Listing
from src.services.notifier import escape_markdown_v2

logger = logging.getLogger(__name__)


class BerlinovoApplier(BaseApplier):
    """
    Auto-application handler for Berlinovo (Berlin state-owned housing).

    Submits the "Kontaktanfrage" (contact request) form on listing detail pages
    with applicant data (Anrede, Name, E-Mail, Telefonnummer, Anmerkungen).
    """

    URL_PATTERNS = [
        "https://www.berlinovo.de/",
        "https://berlinovo.de/",
    ]

    # Form field name substrings to match (lowercase) for mapping config to form
    FIELD_HINTS = {
        "anrede": ["anrede", "salutation", "gender"],
        "name": ["name", "nachname", "surname", "lastname"],
        "vorname": ["vorname", "vorname", "firstname", "first_name"],
        "email": ["email", "e-mail", "mail"],
        "telefon": ["telefon", "phone", "tel", "telefonnummer"],
        "anmerkungen": ["anmerkung", "message", "comment", "nachricht", "notes"],
    }

    @property
    def name(self) -> str:
        """Return the applier name."""
        return "Berlinovo"

    @property
    def url_patterns(self) -> List[str]:
        """Return URL patterns this applier handles."""
        return self.URL_PATTERNS

    def apply(self, listing: Listing) -> ApplyResult:
        """
        Submit a contact request for the given Berlinovo listing.

        Args:
            listing: The listing to apply for.

        Returns:
            ApplyResult containing the outcome and details of the application.
        """
        if not self.is_configured():
            logger.warning(
                "Berlinovo configuration missing in 'berlinovo' applier section. "
                "Skipping auto-application."
            )
            return ApplyResult(
                status=ApplyStatus.MISSING_CONFIG,
                message="Berlinovo applicant configuration is missing",
            )

        listing_url = listing.identifier
        logger.info(f"Attempting to auto-apply for Berlinovo listing: {listing_url}")

        try:
            form, soup = self._fetch_and_find_form(listing_url)

            if self._is_listing_unavailable(soup):
                logger.warning(f"Listing no longer available: {listing_url}")
                return ApplyResult(
                    status=ApplyStatus.LISTING_UNAVAILABLE,
                    message="Listing is no longer available on Berlinovo website",
                )

            if not form:
                return ApplyResult(
                    status=ApplyStatus.FORM_NOT_FOUND,
                    message=f"Could not find contact form on {listing_url}",
                )

            applicant_data = self._build_applicant_data()
            form_data = self._prepare_form_data(form)

            logger.info(self._format_data_for_log(applicant_data))

            submit_url = self._get_submit_url(form, listing_url)
            return self._submit_application(
                submit_url, form_data, applicant_data, listing_url
            )

        except requests.RequestException as e:
            logger.error(
                f"Network error applying to Berlinovo listing {listing_url}: {e}"
            )
            return ApplyResult(
                status=ApplyStatus.FAILED,
                message=f"Network error: {e}",
            )
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"Failed to apply to Berlinovo listing {listing_url}: {e}")
            return ApplyResult(
                status=ApplyStatus.FAILED,
                message=f"Unexpected error: {e}",
            )

    def _fetch_and_find_form(self, url: str) -> tuple[Optional[Tag], BeautifulSoup]:
        """
        Fetch the listing page and locate the contact request form.

        Looks for a form that contains typical contact fields (name, email, phone).

        Args:
            url: The listing URL to fetch.

        Returns:
            Tuple of (form element or None, BeautifulSoup object).
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        response = requests.get(
            url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        for form in soup.find_all("form"):
            if self._looks_like_contact_form(form):
                return form, soup

        logger.error(f"Could not find contact form on {url}")
        return None, soup

    def _looks_like_contact_form(self, form: Tag) -> bool:
        """
        Heuristic: form is likely the Kontaktanfrage if it has name + email (or phone).
        """
        text = form.get_text().lower()
        has_contact_label = (
            "kontaktanfrage" in text
            or "anfrage" in text
            or "kontakt" in text
        )
        inputs = form.find_all(["input", "select", "textarea"])
        names = [inp.get("name", "").lower() for inp in inputs if inp.get("name")]
        ids = [inp.get("id", "").lower() for inp in inputs if inp.get("id")]
        combined = " ".join(names + ids)
        has_name = any(h in combined for h in ["name", "vorname", "nachname"])
        has_email = "email" in combined or "e-mail" in combined or "mail" in combined
        has_phone = any(
            h in combined for h in ["telefon", "phone", "tel", "telefonnummer"]
        )
        return (has_name and (has_email or has_phone)) or (
            has_contact_label and (has_email or has_phone)
        )

    def _is_listing_unavailable(self, soup: BeautifulSoup) -> bool:
        """Check if the page indicates the listing is no longer available."""
        page_text = soup.get_text().lower()
        unavailable_indicators = [
            "nicht mehr verfügbar",
            "nicht verfügbar",
            "bereits vergeben",
            "no longer available",
        ]
        return any(indicator in page_text for indicator in unavailable_indicators)

    def _build_applicant_data(self) -> Dict[str, Any]:
        """Build human-readable applicant data from config."""
        vorname = self.config.get("vorname", "")
        name = self.config.get("name", "")
        full_name = f"{vorname} {name}".strip() if (vorname or name) else (name or vorname)
        return {
            "Anrede": self.config.get("anrede", "Frau"),
            "Name": full_name or self.config.get("name"),
            "E-Mail": self.config.get("email"),
            "Telefon": self.config.get("telefon", ""),
            "Anmerkungen": self.config.get("anmerkungen", ""),
        }

    def _prepare_form_data(self, form: Tag) -> Dict[str, str]:
        """Prepare form data dict: hidden fields + mapped applicant fields."""
        data = self._extract_hidden_fields(form)
        mapper = _BerlinovoFormFieldMapper(form)

        # Map config to form fields
        value_by_hint = {
            "anrede": self.config.get("anrede", "Frau"),
            "name": self.config.get("name", ""),
            "vorname": self.config.get("vorname", ""),
            "email": self.config.get("email", ""),
            "telefon": self.config.get("telefon", ""),
            "anmerkungen": self.config.get("anmerkungen", ""),
        }

        for hint_key, value in value_by_hint.items():
            if value is None:
                value = ""
            field_name = mapper.find_field_name(self.FIELD_HINTS[hint_key])
            if field_name and (value or hint_key == "anrede"):
                data[field_name] = str(value).strip()

        # If form has a single "name" field, use "Vorname Name"
        if "name" in value_by_hint and "vorname" in value_by_hint:
            name_field = mapper.find_field_name(self.FIELD_HINTS["name"])
            vorname_field = mapper.find_field_name(self.FIELD_HINTS["vorname"])
            if name_field and not vorname_field:
                vorname = self.config.get("vorname", "")
                name = self.config.get("name", "")
                data[name_field] = f"{vorname} {name}".strip() or name or vorname

        # Honeypot / empty field often named to be left blank
        for inp in form.find_all("input", type="text"):
            name_attr = inp.get("name")
            if name_attr and re.search(r"leave|empty|blank|honeypot", name_attr, re.I):
                if name_attr not in data:
                    data[name_attr] = ""

        return data

    def _extract_hidden_fields(self, form: Tag) -> Dict[str, str]:
        """Extract all hidden input values from the form."""
        data = {}
        for inp in form.find_all("input", type="hidden"):
            name = inp.get("name")
            if name:
                data[name] = inp.get("value", "")
        return data

    def _get_submit_url(self, form: Tag, listing_url: str) -> str:
        """Resolve form action to absolute URL."""
        action = form.get("action")
        if not action:
            return listing_url
        if action.startswith("/"):
            base = listing_url.split("/", 3)[:3]
            base_str = "/".join(base) if len(base) == 3 else listing_url
            return urljoin(base_str + "/", action.lstrip("/"))
        return action if action.startswith("http") else urljoin(listing_url, action)

    def _submit_application(
        self,
        url: str,
        form_data: Dict[str, str],
        applicant_data: Dict[str, Any],
        listing_url: str,
    ) -> ApplyResult:
        """POST the form and interpret response."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Referer": listing_url,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(
            url,
            data=form_data,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        if self._is_submission_successful(response):
            logger.info(
                f"{Colors.GREEN}Successfully applied to Berlinovo listing {url}{Colors.RESET}"
            )
            return ApplyResult(
                status=ApplyStatus.SUCCESS,
                message="Contact request submitted successfully",
                applicant_data=applicant_data,
            )

        logger.warning(
            f"Berlinovo application might have failed. "
            f"Status: {response.status_code}, "
            f"Response preview: {response.text[:500]}..."
        )
        return ApplyResult(
            status=ApplyStatus.FAILED,
            message="Submission did not return expected success indicators",
            applicant_data=applicant_data,
        )

    def _is_submission_successful(self, response: requests.Response) -> bool:
        """Check response for success indicators."""
        text = (response.text or "").lower()
        url_lower = (response.url or "").lower()
        success_indicators = [
            "vielen dank" in text,
            "danke" in text and ("anfrage" in text or "nachricht" in text),
            "erfolgreich" in text,
            "versendet" in text,
            "success" in url_lower,
            "sent" in text,
        ]
        return any(success_indicators)

    def _format_data_for_log(self, applicant_data: Dict[str, Any]) -> str:
        """Format applicant data for console logging."""
        lines = ["Application Data:"]
        for key, value in applicant_data.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def format_success_message(
        self,
        listing_url: str,
        applicant_data: Dict[str, Any],
    ) -> str:
        """Format success message for Telegram (MarkdownV2)."""
        escaped_url = escape_markdown_v2(listing_url)
        lines = [
            "✅ *Automatically applied to Berlinovo listing*",
            "",
            f"🔗 [Listing]({escaped_url})",
            "",
            "📋 *Application Data:*",
        ]
        for key, value in applicant_data.items():
            escaped_key = escape_markdown_v2(key)
            escaped_value = escape_markdown_v2(value if value else "N/A")
            lines.append(f"  • *{escaped_key}:* {escaped_value}")
        return "\n".join(lines)


class _BerlinovoFormFieldMapper:
    """
    Finds form field names by matching hint substrings against name/id/label.

    Berlinovo (Drupal) may use names like field_anrede[0][value] or
    contact_message[name]. This mapper finds the first input/select/textarea
    whose name or id contains any of the given hints.
    """

    def __init__(self, form: Tag) -> None:
        self.form = form

    def find_field_name(self, hints: List[str]) -> Optional[str]:
        """
        Return the first field name that matches any of the given hints.

        Args:
            hints: Lowercase substrings to match (e.g. ["email", "e-mail", "mail"]).

        Returns:
            The field's name attribute, or None if no match.
        """
        for tag in self.form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            name_lower = name.lower()
            id_attr = (tag.get("id") or "").lower()
            # Skip submit and hidden when looking for data fields
            if tag.name == "input":
                type_attr = (tag.get("type") or "text").lower()
                if type_attr in ("submit", "button", "image"):
                    continue
            for hint in hints:
                if hint in name_lower or hint in id_attr:
                    return name
        return None
