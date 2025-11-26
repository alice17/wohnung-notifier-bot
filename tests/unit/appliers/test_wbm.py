"""
Unit tests for the WBMApplier class.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.appliers.base import ApplyStatus
from src.appliers.wbm import WBMApplier, FormFieldMapper
from src.listing import Listing


class TestWBMApplier(unittest.TestCase):
    """Test suite for WBMApplier class."""

    def setUp(self):
        """Set up common test fixtures."""
        self.config = {
            "anrede": "Herr",
            "nachname": "Mustermann",
            "vorname": "Max",
            "strasse": "Teststr. 1",
            "plz": "10115",
            "ort": "Berlin",
            "email": "max@example.com",
            "telefon": "030123456",
            "wbs": "ja"
        }
        self.applier = WBMApplier(self.config)

    def test_name_property(self):
        """Tests that name returns 'WBM'."""
        self.assertEqual(self.applier.name, "WBM")

    def test_url_patterns_property(self):
        """Tests that url_patterns includes WBM URLs."""
        patterns = self.applier.url_patterns
        self.assertIn("https://www.wbm.de/", patterns)
        self.assertIn("https://wbm.de/", patterns)

    def test_can_apply_matches_wbm_url(self):
        """Tests can_apply returns True for WBM URLs."""
        listing = Listing(
            source="wbm",
            link="https://www.wbm.de/wohnungen-berlin/angebote/details/?id=123"
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_matches_wbm_url_without_www(self):
        """Tests can_apply returns True for WBM URLs without www."""
        listing = Listing(
            source="wbm",
            link="https://wbm.de/wohnungen-berlin/angebote/details/?id=123"
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_returns_false_for_other_urls(self):
        """Tests can_apply returns False for non-WBM URLs."""
        listing = Listing(
            source="degewo",
            link="https://www.degewo.de/listing/123"
        )
        self.assertFalse(self.applier.can_apply(listing))

    def test_is_configured_returns_true_with_valid_config(self):
        """Tests is_configured returns True with valid config."""
        self.assertTrue(self.applier.is_configured())

    def test_is_configured_returns_false_without_config(self):
        """Tests is_configured returns False without config."""
        empty_applier = WBMApplier({})
        self.assertFalse(empty_applier.is_configured())

    def test_apply_returns_missing_config_when_not_configured(self):
        """Tests apply returns MISSING_CONFIG when config is empty."""
        empty_applier = WBMApplier({})
        listing = Listing(
            source="wbm",
            link="https://www.wbm.de/listing/123"
        )
        
        result = empty_applier.apply(listing)
        
        self.assertEqual(result.status, ApplyStatus.MISSING_CONFIG)
        self.assertIn("missing", result.message.lower())

    def test_build_applicant_data_creates_correct_structure(self):
        """Tests _build_applicant_data creates proper data dictionary."""
        data = self.applier._build_applicant_data()
        
        self.assertEqual(data["Anrede"], "Herr")
        self.assertEqual(data["Name"], "Mustermann")
        self.assertEqual(data["Vorname"], "Max")
        self.assertEqual(data["Strasse"], "Teststr. 1")
        self.assertEqual(data["PLZ"], "10115")
        self.assertEqual(data["Ort"], "Berlin")
        self.assertEqual(data["E-Mail"], "max@example.com")
        self.assertEqual(data["Telefon"], "030123456")
        self.assertEqual(data["WBS vorhanden"], "Ja")

    def test_build_applicant_data_wbs_no(self):
        """Tests _build_applicant_data correctly handles WBS = No."""
        config_no_wbs = self.config.copy()
        config_no_wbs["wbs"] = "nein"
        applier = WBMApplier(config_no_wbs)
        
        data = applier._build_applicant_data()
        
        self.assertEqual(data["WBS vorhanden"], "Nein")

    def test_build_applicant_data_wbs_variations(self):
        """Tests _build_applicant_data handles various WBS true values."""
        for wbs_value in ["ja", "yes", "true", "1", "Ja", "YES"]:
            config = self.config.copy()
            config["wbs"] = wbs_value
            applier = WBMApplier(config)
            data = applier._build_applicant_data()
            self.assertEqual(
                data["WBS vorhanden"], "Ja",
                f"WBS value '{wbs_value}' should result in 'Ja'"
            )

    def test_format_data_for_log(self):
        """Tests _format_data_for_log creates readable log output."""
        applicant_data = {"Name": "Test", "Email": "test@example.com"}
        
        log_output = self.applier._format_data_for_log(applicant_data)
        
        self.assertIn("Application Data:", log_output)
        self.assertIn("Name: Test", log_output)
        self.assertIn("Email: test@example.com", log_output)

    def test_format_success_message_creates_telegram_format(self):
        """Tests format_success_message creates MarkdownV2 format."""
        applicant_data = {"Name": "Mustermann", "Email": "test@example.com"}
        listing_url = "https://www.wbm.de/listing/123"
        
        message = self.applier.format_success_message(listing_url, applicant_data)
        
        self.assertIn("✅", message)
        self.assertIn("*Automatically applied", message)
        self.assertIn("WBM", message)
        self.assertIn("Application Data", message)

    @patch('src.appliers.wbm.requests.get')
    def test_fetch_and_find_form_returns_none_when_no_form(self, mock_get):
        """Tests _fetch_and_find_form returns None when no form found."""
        mock_response = Mock()
        mock_response.content = b"<html><body>No form here</body></html>"
        mock_get.return_value = mock_response
        
        form, soup = self.applier._fetch_and_find_form("https://www.wbm.de/test")
        
        self.assertIsNone(form)

    @patch('src.appliers.wbm.requests.get')
    def test_fetch_and_find_form_finds_powermail_form(self, mock_get):
        """Tests _fetch_and_find_form finds Powermail forms."""
        mock_response = Mock()
        mock_response.content = b"""
        <html><body>
            <form action="/submit" method="post">
                <input type="hidden" name="tx_powermail_pi1[token]" value="abc123">
            </form>
        </body></html>
        """
        mock_get.return_value = mock_response
        
        form, soup = self.applier._fetch_and_find_form("https://www.wbm.de/test")
        
        self.assertIsNotNone(form)

    def test_get_submit_url_returns_listing_url_when_no_action(self):
        """Tests _get_submit_url returns listing URL when form has no action."""
        mock_form = Mock()
        mock_form.get.return_value = None
        listing_url = "https://www.wbm.de/listing/123"
        
        result = self.applier._get_submit_url(mock_form, listing_url)
        
        self.assertEqual(result, listing_url)

    def test_get_submit_url_resolves_relative_url(self):
        """Tests _get_submit_url resolves relative action URL."""
        mock_form = Mock()
        mock_form.get.return_value = "/submit-form"
        listing_url = "https://www.wbm.de/listing/123"
        
        result = self.applier._get_submit_url(mock_form, listing_url)
        
        self.assertEqual(result, "https://www.wbm.de/submit-form")

    def test_get_submit_url_returns_absolute_action(self):
        """Tests _get_submit_url returns absolute action URL as-is."""
        mock_form = Mock()
        mock_form.get.return_value = "https://other.wbm.de/form"
        listing_url = "https://www.wbm.de/listing/123"
        
        result = self.applier._get_submit_url(mock_form, listing_url)
        
        self.assertEqual(result, "https://other.wbm.de/form")

    @patch('src.appliers.wbm.requests.post')
    def test_is_submission_successful_detects_success_indicators(self, mock_post):
        """Tests _is_submission_successful detects success indicators."""
        mock_response = Mock()
        mock_response.text = "Vielen Dank für Ihre Anfrage"
        mock_response.url = "https://www.wbm.de/success"
        
        self.assertTrue(self.applier._is_submission_successful(mock_response))

    @patch('src.appliers.wbm.requests.post')
    def test_is_submission_successful_detects_vielen_dank_in_url(self, mock_post):
        """Tests _is_submission_successful detects vielen-dank in URL."""
        mock_response = Mock()
        mock_response.text = "Some other content"
        mock_response.url = "https://www.wbm.de/vielen-dank"
        
        self.assertTrue(self.applier._is_submission_successful(mock_response))

    @patch('src.appliers.wbm.requests.post')
    def test_is_submission_successful_returns_false_for_no_indicators(self, mock_post):
        """Tests _is_submission_successful returns False without indicators."""
        mock_response = Mock()
        mock_response.text = "Error occurred"
        mock_response.url = "https://www.wbm.de/error"
        
        self.assertFalse(self.applier._is_submission_successful(mock_response))


class TestFormFieldMapper(unittest.TestCase):
    """Test suite for FormFieldMapper helper class."""

    def _create_mock_form(self, fields: list) -> Mock:
        """Creates a mock form with specified fields."""
        mock_form = Mock()
        mock_inputs = []
        
        for field in fields:
            mock_input = Mock()
            mock_input.get.return_value = field
            mock_inputs.append(mock_input)
        
        mock_form.find_all.return_value = mock_inputs
        return mock_form

    def test_find_field_name_finds_matching_field(self):
        """Tests find_field_name finds field containing partial name."""
        mock_form = self._create_mock_form([
            "tx_powermail_pi1[field][name]",
            "tx_powermail_pi1[field][email]"
        ])
        mapper = FormFieldMapper(mock_form)
        
        result = mapper.find_field_name("name")
        
        self.assertEqual(result, "tx_powermail_pi1[field][name]")

    def test_find_field_name_returns_none_for_no_match(self):
        """Tests find_field_name returns None when no match found."""
        mock_form = self._create_mock_form([
            "tx_powermail_pi1[field][name]"
        ])
        mapper = FormFieldMapper(mock_form)
        
        result = mapper.find_field_name("telefon")
        
        self.assertIsNone(result)

    def test_find_field_name_matches_exact_bracket_pattern(self):
        """Tests find_field_name matches exact [field_name] pattern."""
        mock_form = self._create_mock_form([
            "tx_powermail_pi1[field][e_mail]",
            "some_other_email_field"
        ])
        mapper = FormFieldMapper(mock_form)
        
        result = mapper.find_field_name("e_mail")
        
        self.assertEqual(result, "tx_powermail_pi1[field][e_mail]")


if __name__ == '__main__':
    unittest.main()


