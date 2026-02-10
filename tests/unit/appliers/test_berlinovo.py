"""
Unit tests for the BerlinovoApplier class.
"""
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.appliers.base import ApplyStatus
from src.appliers.berlinovo import BerlinovoApplier
from src.core.listing import Listing


class TestBerlinovoApplier(unittest.TestCase):
    """Test suite for BerlinovoApplier class."""

    def setUp(self):
        """Set up common test fixtures."""
        self.config = {
            "anrede": "Frau",
            "name": "Mustermann",
            "vorname": "Erika",
            "email": "erika.mustermann@example.com",
            "telefon": "03012345678",
            "anmerkungen": "Unverbindliche Besichtigung erwünscht",
        }
        self.applier = BerlinovoApplier(self.config)

    def test_name_property(self):
        """Tests that name returns 'Berlinovo'."""
        self.assertEqual(self.applier.name, "Berlinovo")

    def test_url_patterns_property(self):
        """Tests that url_patterns includes Berlinovo URLs."""
        patterns = self.applier.url_patterns
        self.assertIn("https://www.berlinovo.de/", patterns)
        self.assertIn("https://berlinovo.de/", patterns)

    def test_can_apply_matches_berlinovo_listing_url(self):
        """Tests can_apply returns True for Berlinovo listing URL."""
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/wohnungen/31032314183-zentral-grun-wohnen-auf-der-fischerinsel",
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_matches_berlinovo_de_wohnung_url(self):
        """Tests can_apply returns True for /de/wohnung/ style URL."""
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/de/wohnung/12345-test",
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_returns_false_for_other_urls(self):
        """Tests can_apply returns False for non-Berlinovo URLs."""
        listing = Listing(
            source="wbm",
            identifier="https://www.wbm.de/listing/123",
        )
        self.assertFalse(self.applier.can_apply(listing))

    def test_is_configured_returns_true_with_valid_config(self):
        """Tests is_configured returns True with valid config."""
        self.assertTrue(self.applier.is_configured())

    def test_is_configured_returns_false_without_config(self):
        """Tests is_configured returns False with empty config."""
        empty_applier = BerlinovoApplier({})
        self.assertFalse(empty_applier.is_configured())

    def test_apply_returns_missing_config_when_not_configured(self):
        """Tests apply returns MISSING_CONFIG when config is empty."""
        empty_applier = BerlinovoApplier({})
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/wohnungen/123-test",
        )
        result = empty_applier.apply(listing)
        self.assertEqual(result.status, ApplyStatus.MISSING_CONFIG)
        self.assertIn("missing", result.message.lower())

    def test_build_applicant_data_creates_correct_structure(self):
        """Tests _build_applicant_data creates proper data dictionary."""
        data = self.applier._build_applicant_data()
        self.assertEqual(data["Anrede"], "Frau")
        self.assertEqual(data["Name"], "Erika Mustermann")
        self.assertEqual(data["E-Mail"], "erika.mustermann@example.com")
        self.assertEqual(data["Telefon"], "03012345678")
        self.assertEqual(data["Anmerkungen"], "Unverbindliche Besichtigung erwünscht")

    def test_build_applicant_data_name_only(self):
        """Tests _build_applicant_data when only name is set."""
        config = {"name": "Schmidt", "email": "a@b.de"}
        applier = BerlinovoApplier(config)
        data = applier._build_applicant_data()
        self.assertEqual(data["Name"], "Schmidt")

    def test_build_applicant_data_default_anrede(self):
        """Tests _build_applicant_data defaults Anrede to Frau."""
        config = {"email": "a@b.de"}
        applier = BerlinovoApplier(config)
        data = applier._build_applicant_data()
        self.assertEqual(data["Anrede"], "Frau")

    def test_format_data_for_log(self):
        """Tests _format_data_for_log produces readable string."""
        applicant_data = {"Name": "Mustermann", "E-Mail": "test@example.com"}
        log_output = self.applier._format_data_for_log(applicant_data)
        self.assertIn("Application Data:", log_output)
        self.assertIn("Name:", log_output)
        self.assertIn("Mustermann", log_output)

    def test_format_success_message(self):
        """Tests format_success_message produces Telegram-safe message."""
        listing_url = "https://www.berlinovo.de/wohnungen/123"
        applicant_data = {"Name": "Mustermann", "E-Mail": "test@example.com"}
        message = self.applier.format_success_message(listing_url, applicant_data)
        self.assertIn("Berlinovo", message)
        self.assertIn("Listing", message)
        self.assertIn("123", message)

    def test_get_submit_url_uses_action_when_absolute(self):
        """Tests _get_submit_url returns action when it is absolute."""
        form = Mock()
        form.get.return_value = "https://www.berlinovo.de/form/submit"
        result = self.applier._get_submit_url(
            form, "https://www.berlinovo.de/wohnungen/123"
        )
        self.assertEqual(result, "https://www.berlinovo.de/form/submit")

    def test_get_submit_url_uses_listing_when_no_action(self):
        """Tests _get_submit_url returns listing URL when form has no action."""
        form = Mock()
        form.get.return_value = None
        listing_url = "https://www.berlinovo.de/wohnungen/123"
        result = self.applier._get_submit_url(form, listing_url)
        self.assertEqual(result, listing_url)

    def test_get_submit_url_resolves_relative_action(self):
        """Tests _get_submit_url resolves relative action."""
        form = Mock()
        form.get.return_value = "/de/contact/submit"
        result = self.applier._get_submit_url(
            form, "https://www.berlinovo.de/wohnungen/123"
        )
        self.assertIn("berlinovo", result)
        self.assertIn("submit", result)

    def test_is_submission_successful_detects_vielen_dank(self):
        """Tests _is_submission_successful returns True for 'Vielen Dank'."""
        response = Mock()
        response.text = "Vielen Dank für Ihre Anfrage."
        response.url = "https://www.berlinovo.de/wohnungen/123"
        self.assertTrue(self.applier._is_submission_successful(response))

    def test_is_submission_successful_detects_erfolgreich(self):
        """Tests _is_submission_successful returns True for 'erfolgreich'."""
        response = Mock()
        response.text = "Ihre Nachricht wurde erfolgreich versendet."
        response.url = "https://www.berlinovo.de/wohnungen/123"
        self.assertTrue(self.applier._is_submission_successful(response))

    def test_is_submission_successful_returns_false_without_indicators(self):
        """Tests _is_submission_successful returns False when no success text."""
        response = Mock()
        response.text = "Fehler: Ungültige Eingabe."
        response.url = "https://www.berlinovo.de/wohnungen/123"
        self.assertFalse(self.applier._is_submission_successful(response))

    def test_is_listing_unavailable_detects_unavailable(self):
        """Tests _is_listing_unavailable returns True for unavailable text."""
        html = "<html><body><p>Diese Wohnung ist nicht mehr verfügbar.</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        self.assertTrue(self.applier._is_listing_unavailable(soup))

    def test_is_listing_unavailable_returns_false_when_available(self):
        """Tests _is_listing_unavailable returns False for normal page."""
        html = "<html><body><h1>Wohnung 123</h1><p>Kontaktanfrage</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        self.assertFalse(self.applier._is_listing_unavailable(soup))

    @patch("src.appliers.berlinovo.requests.get")
    def test_fetch_and_find_form_returns_form_when_contact_form_present(self, mock_get):
        """Tests _fetch_and_find_form returns form when contact form exists."""
        html = """
        <html><body>
        <form>
            <input name="field_name" />
            <input name="field_email" />
            <input name="field_telefon" />
        </form>
        </body></html>
        """
        mock_get.return_value = Mock(content=html.encode("utf-8"), raise_for_status=Mock())
        form, soup = self.applier._fetch_and_find_form(
            "https://www.berlinovo.de/wohnungen/123"
        )
        self.assertIsNotNone(form)
        self.assertIsNotNone(soup)

    @patch("src.appliers.berlinovo.requests.get")
    def test_fetch_and_find_form_returns_none_when_no_contact_form(self, mock_get):
        """Tests _fetch_and_find_form returns None when no contact form."""
        html = "<html><body><form><input name='search' /></form></body></html>"
        mock_get.return_value = Mock(content=html.encode("utf-8"), raise_for_status=Mock())
        form, _ = self.applier._fetch_and_find_form(
            "https://www.berlinovo.de/wohnungen/123"
        )
        self.assertIsNone(form)

    @patch("src.appliers.berlinovo.requests.post")
    @patch("src.appliers.berlinovo.requests.get")
    def test_apply_returns_form_not_found_when_no_form(self, mock_get, mock_post):
        """Tests apply returns FORM_NOT_FOUND when page has no contact form."""
        html = "<html><body><p>No form here</p></body></html>"
        mock_get.return_value = Mock(content=html.encode("utf-8"), raise_for_status=Mock())
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/wohnungen/123",
        )
        result = self.applier.apply(listing)
        self.assertEqual(result.status, ApplyStatus.FORM_NOT_FOUND)
        mock_post.assert_not_called()

    @patch("src.appliers.berlinovo.BerlinovoApplier._is_listing_unavailable")
    @patch("src.appliers.berlinovo.requests.post")
    @patch("src.appliers.berlinovo.requests.get")
    def test_apply_returns_listing_unavailable_when_indicated(
        self, mock_get, mock_post, mock_unavailable
    ):
        """Tests apply returns LISTING_UNAVAILABLE when listing is unavailable."""
        mock_unavailable.return_value = True
        html = "<html><body><form><input name='field_name'/><input name='field_email'/></form></body></html>"
        mock_get.return_value = Mock(content=html.encode("utf-8"), raise_for_status=Mock())
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/wohnungen/123",
        )
        result = self.applier.apply(listing)
        self.assertEqual(result.status, ApplyStatus.LISTING_UNAVAILABLE)
        mock_post.assert_not_called()

    @patch("src.appliers.berlinovo.requests.post")
    @patch("src.appliers.berlinovo.requests.get")
    def test_apply_success_when_form_submitted_successfully(self, mock_get, mock_post):
        """Tests apply returns SUCCESS when POST returns success indicators."""
        form_html = """
        <html><body>
        <form action="/de/contact/submit" method="post">
            <input type="hidden" name="token" value="abc" />
            <input type="text" name="field_anrede" />
            <input type="text" name="field_name" />
            <input type="text" name="field_email" />
            <input type="text" name="field_telefon" />
        </form>
        </body></html>
        """
        mock_get.return_value = Mock(
            content=form_html.encode("utf-8"), raise_for_status=Mock()
        )
        mock_post.return_value = Mock(
            status_code=200,
            text="Vielen Dank für Ihre Kontaktanfrage.",
            url="https://www.berlinovo.de/de/contact/submit",
            raise_for_status=Mock(),
        )
        listing = Listing(
            source="berlinovo",
            identifier="https://www.berlinovo.de/wohnungen/123",
        )
        result = self.applier.apply(listing)
        self.assertEqual(result.status, ApplyStatus.SUCCESS)
        self.assertIsNotNone(result.applicant_data)


class TestBerlinovoFormStructure(unittest.TestCase):
    """Test _prepare_form_data with a minimal contact-like form."""

    FORM_HTML = """
    <form action="https://www.berlinovo.de/form/submit" method="post">
        <input type="hidden" name="form_build_id" value="xyz" />
        <select name="field_anrede">
            <option value="Frau">Frau</option>
            <option value="Herr">Herr</option>
        </select>
        <input type="text" name="field_name" />
        <input type="text" name="field_vorname" />
        <input type="email" name="field_email" />
        <input type="text" name="field_telefon" />
        <textarea name="field_anmerkungen"></textarea>
        <button type="submit">Absenden</button>
    </form>
    """

    def setUp(self):
        """Set up applier with config."""
        self.config = {
            "anrede": "Herr",
            "name": "Mustermann",
            "vorname": "Max",
            "email": "max@example.com",
            "telefon": "030123456",
            "anmerkungen": "Besichtigung erwünscht",
        }
        self.applier = BerlinovoApplier(self.config)

    def test_prepare_form_data_maps_fields(self):
        """Tests _prepare_form_data maps config to form field names."""
        soup = BeautifulSoup(self.FORM_HTML, "html.parser")
        form = soup.find("form")
        form_data = self.applier._prepare_form_data(form)
        self.assertEqual(form_data.get("field_anrede"), "Herr")
        self.assertEqual(form_data.get("field_name"), "Mustermann")
        self.assertEqual(form_data.get("field_vorname"), "Max")
        self.assertEqual(form_data.get("field_email"), "max@example.com")
        self.assertEqual(form_data.get("field_telefon"), "030123456")
        self.assertEqual(form_data.get("field_anmerkungen"), "Besichtigung erwünscht")

    def test_prepare_form_data_preserves_hidden_fields(self):
        """Tests _prepare_form_data preserves hidden inputs."""
        soup = BeautifulSoup(self.FORM_HTML, "html.parser")
        form = soup.find("form")
        form_data = self.applier._prepare_form_data(form)
        self.assertEqual(form_data.get("form_build_id"), "xyz")


if __name__ == "__main__":
    unittest.main()
