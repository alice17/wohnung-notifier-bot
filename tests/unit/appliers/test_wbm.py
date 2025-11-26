"""
Unit tests for the WBMApplier class.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.appliers.base import ApplyStatus
from src.appliers.wbm import WBMApplier, FormFieldMapper
from src.core.listing import Listing


class TestWBMApplier(unittest.TestCase):
    """Test suite for WBMApplier class."""

    def setUp(self):
        """Set up common test fixtures."""
        self.config = {
            "anrede": "Herr",
            "name": "Mustermann",
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

    def test_is_listing_unavailable_returns_true_when_no_offers(self):
        """Tests _is_listing_unavailable detects German unavailable message."""
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <div>Leider haben wir derzeit keine verfügbaren Angebote</div>
        </body></html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        self.assertTrue(self.applier._is_listing_unavailable(soup))

    def test_is_listing_unavailable_returns_false_for_available_listing(self):
        """Tests _is_listing_unavailable returns False for active listings."""
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <div>Wohnung in Berlin Mitte</div>
            <div>Besichtigungstermin anfragen</div>
        </body></html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        self.assertFalse(self.applier._is_listing_unavailable(soup))

    @patch('src.appliers.wbm.requests.get')
    def test_apply_returns_listing_unavailable_when_no_offers(self, mock_get):
        """Tests apply returns LISTING_UNAVAILABLE when listing is gone."""
        mock_response = Mock()
        mock_response.content = b"""
        <html><body>
            <div>Leider haben wir derzeit keine verfuegbaren Angebote</div>
            <form><input name="tx_powermail_pi1[field]"></form>
        </body></html>
        """
        mock_get.return_value = mock_response
        
        listing = Listing(
            source="wbm",
            link="https://www.wbm.de/listing/123"
        )
        result = self.applier.apply(listing)
        
        self.assertEqual(result.status, ApplyStatus.LISTING_UNAVAILABLE)
        self.assertIn("no longer available", result.message.lower())


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


class TestWBMRealFormStructure(unittest.TestCase):
    """
    Test suite using real WBM form structure.
    
    Based on actual form from:
    https://www.wbm.de/wohnungen-berlin/angebote/details/?tx_openimmo_immobilie[immobilie]=50-518512/4/82
    """

    # Real WBM form HTML captured from Spandau 2-Zimmer listing
    REAL_FORM_HTML = '''
    <form action="https://www.wbm.de/wohnungen-berlin/angebote/details/?tx_powermail_pi1%5Baction%5D=checkCreate&amp;tx_powermail_pi1%5Bcontroller%5D=Form&amp;cHash=29eef4e3e5da07075c9425623247866f#c722" method="post">
        <input type="hidden" name="tx_powermail_pi1[__referrer][@extension]" value="Powermail">
        <input type="hidden" name="tx_powermail_pi1[__referrer][@controller]" value="Form">
        <input type="hidden" name="tx_powermail_pi1[__referrer][@action]" value="form">
        <input type="hidden" name="tx_powermail_pi1[__referrer][arguments]" value="YTowOnt9ef52e62da51d49537d9b67d61f39b458b8f18280">
        <input type="hidden" name="tx_powermail_pi1[__referrer][@request]" value='{"@extension":"Powermail","@controller":"Form","@action":"form"}8a5cf3532bf879a9b29d031470302d1b74c43f98'>
        <input type="hidden" name="tx_powermail_pi1[__trustedProperties]" value='{"field":{"objekt":1,"wbsvorhanden":1}}12c8ddf50560cc63d41eb4dca707a42154e5a3d4'>
        <input type="hidden" name="tx_powermail_pi1[field][objekt]" value="50-518512/4/82" id="powermail_field_objekt">
        <input type="radio" name="tx_powermail_pi1[field][wbsvorhanden]" value="1" id="powermail_field_wbsvorhanden_1">
        <input type="radio" name="tx_powermail_pi1[field][wbsvorhanden]" value="0" id="powermail_field_wbsvorhanden_2" checked>
        <input type="date" name="tx_powermail_pi1[field][wbsgueltigbis]" id="powermail_field_wbsgueltigbis">
        <select name="tx_powermail_pi1[field][wbszimmeranzahl]" id="powermail_field_wbszimmeranzahl">
            <option value="1">1</option>
            <option value="2">2</option>
        </select>
        <select name="tx_powermail_pi1[field][einkommensgrenzenacheinkommensbescheinigung9]" id="powermail_field_einkommensgrenzenacheinkommensbescheinigung9">
            <option value="100">WBS 100</option>
            <option value="140">WBS 140</option>
        </select>
        <input type="hidden" name="tx_powermail_pi1[field][wbsmitbesonderemwohnbedarf]" value="">
        <input type="checkbox" name="tx_powermail_pi1[field][wbsmitbesonderemwohnbedarf][]" value="1" id="powermail_field_wbsmitbesonderemwohnbedarf_1">
        <select name="tx_powermail_pi1[field][anrede]" id="powermail_field_anrede">
            <option value="Frau" selected>Frau</option>
            <option value="Herr">Herr</option>
            <option value="Offen">Offen</option>
        </select>
        <input type="text" name="tx_powermail_pi1[field][name]" id="powermail_field_name">
        <input type="text" name="tx_powermail_pi1[field][vorname]" id="powermail_field_vorname">
        <input type="text" name="tx_powermail_pi1[field][strasse]" id="powermail_field_strasse">
        <input type="text" name="tx_powermail_pi1[field][plz]" id="powermail_field_plz">
        <input type="text" name="tx_powermail_pi1[field][ort]" id="powermail_field_ort">
        <input type="text" name="tx_powermail_pi1[field][e_mail]" id="powermail_field_e_mail">
        <input type="text" name="tx_powermail_pi1[field][telefon]" id="powermail_field_telefon">
        <input type="hidden" name="tx_powermail_pi1[field][datenschutzhinweis]" value="">
        <input type="checkbox" name="tx_powermail_pi1[field][datenschutzhinweis][]" value="1" id="powermail_field_datenschutzhinweis_1">
        <input type="hidden" name="tx_powermail_pi1[mail][form]" value="2">
        <input type="text" name="tx_powermail_pi1[field][__hp]" id="powermail_hp_2">
        <button type="submit">Anfrage absenden</button>
    </form>
    '''

    def setUp(self):
        """Set up test fixtures with realistic config."""
        self.config = {
            "anrede": "Herr",
            "name": "Mustermann",
            "vorname": "Max",
            "strasse": "Teststraße 42",
            "plz": "10115",
            "ort": "Berlin",
            "email": "max.mustermann@example.com",
            "telefon": "030123456789",
            "wbs": "nein"
        }
        self.applier = WBMApplier(self.config)

    def test_prepare_form_data_with_real_form_structure(self):
        """Tests _prepare_form_data correctly maps to real WBM form fields."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = self.applier._build_applicant_data()
        form_data = self.applier._prepare_form_data(form, applicant_data)
        
        # Verify contact fields are correctly mapped
        self.assertEqual(
            form_data["tx_powermail_pi1[field][name]"],
            "Mustermann",
            "Last name should map to [name] field"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][vorname]"],
            "Max"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][strasse]"],
            "Teststraße 42"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][plz]"],
            "10115"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][ort]"],
            "Berlin"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][e_mail]"],
            "max.mustermann@example.com"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[field][telefon]"],
            "030123456789"
        )

    def test_prepare_form_data_includes_anrede(self):
        """Tests _prepare_form_data sets Anrede dropdown correctly."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = self.applier._build_applicant_data()
        form_data = self.applier._prepare_form_data(form, applicant_data)
        
        self.assertEqual(
            form_data["tx_powermail_pi1[field][anrede]"],
            "Herr"
        )

    def test_prepare_form_data_sets_wbs_no(self):
        """Tests WBS vorhanden is set to '0' when wbs=nein."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = self.applier._build_applicant_data()
        form_data = self.applier._prepare_form_data(form, applicant_data)
        
        self.assertEqual(
            form_data["tx_powermail_pi1[field][wbsvorhanden]"],
            "0"
        )

    def test_prepare_form_data_sets_wbs_yes(self):
        """Tests WBS vorhanden is set to '1' when wbs=ja."""
        config_with_wbs = self.config.copy()
        config_with_wbs["wbs"] = "ja"
        applier = WBMApplier(config_with_wbs)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = applier._build_applicant_data()
        form_data = applier._prepare_form_data(form, applicant_data)
        
        self.assertEqual(
            form_data["tx_powermail_pi1[field][wbsvorhanden]"],
            "1"
        )

    def test_prepare_form_data_includes_privacy_checkbox(self):
        """Tests Datenschutzhinweis checkbox is included."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = self.applier._build_applicant_data()
        form_data = self.applier._prepare_form_data(form, applicant_data)
        
        self.assertIn(
            "tx_powermail_pi1[field][datenschutzhinweis][]",
            form_data
        )

    def test_prepare_form_data_preserves_hidden_fields(self):
        """Tests that hidden form fields are preserved."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        applicant_data = self.applier._build_applicant_data()
        form_data = self.applier._prepare_form_data(form, applicant_data)
        
        # Verify hidden fields from form are preserved
        self.assertEqual(
            form_data["tx_powermail_pi1[field][objekt]"],
            "50-518512/4/82"
        )
        self.assertEqual(
            form_data["tx_powermail_pi1[__referrer][@extension]"],
            "Powermail"
        )

    def test_get_submit_url_from_real_form(self):
        """Tests submit URL extraction from real form."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.REAL_FORM_HTML, 'html.parser')
        form = soup.find('form')
        
        submit_url = self.applier._get_submit_url(
            form,
            "https://www.wbm.de/wohnungen-berlin/angebote/details/"
        )
        
        self.assertIn("tx_powermail_pi1", submit_url)
        self.assertIn("checkCreate", submit_url)


if __name__ == '__main__':
    unittest.main()


