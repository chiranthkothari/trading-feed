import pytest
from unittest.mock import MagicMock, patch
from gspread.exceptions import APIError
from src.sheets.sheets_client import SheetsClient

@pytest.fixture
def mock_client_setup():
    """Patches Config and internal connection logic for testing."""
    with patch("src.sheets.sheets_client.Config") as MockConfig, \
         patch("src.sheets.sheets_client.Credentials") as MockCreds, \
         patch("src.sheets.sheets_client.gspread") as MockGspread:
        
        MockConfig.GOOGLE_SHEET_ID = "test_sheet_id"
        MockConfig.GOOGLE_SERVICE_ACCOUNT_JSON_PATH = "test.json"
        
        client = SheetsClient()
        # Mock internal gspread client and sheet objects
        client.client = MagicMock()
        client.sheet = MagicMock()
        
        yield client, MockGspread, MockCreds

def test_connect_success(mock_client_setup):
    client, MockGspread, MockCreds = mock_client_setup
    # Reset client.client/sheet to None to test connect() logic
    client.client = None
    client.sheet = None
    
    MockGspread.authorize.return_value.open_by_key.return_value = "mock_sheet_obj"
    
    assert client.connect() is True
    assert client.client is not None
    assert client.sheet == "mock_sheet_obj"

def test_read_config(mock_client_setup):
    client, _, _ = mock_client_setup
    mock_worksheet = MagicMock()
    client.sheet.worksheet.return_value = mock_worksheet
    
    # Mock data from sheet
    mock_worksheet.get_all_records.return_value = [
        {"Symbol": "NSE:RELIANCE-EQ", "Enabled": "TRUE"},
        {"Symbol": "NSE:TCS-EQ", "Enabled": "FALSE"},
        {"Symbol": "NSE:INFY-EQ", "Enabled": "TRUE"},
        {"Symbol": "NSE:HDFCBANK-EQ", "Enabled": 1} # Should be converted to string upper
    ]
    
    result = client.read_config()
    
    # Expecting 2 enabled instruments (TRUE ones)
    # Note: Logic was `str(row.get("Enabled", "")).upper() == "TRUE"`
    # "1" string upper is "1", not "TRUE". So only explicit "TRUE".
    
    assert len(result) == 2
    assert result[0]["Symbol"] == "NSE:RELIANCE-EQ"
    assert result[1]["Symbol"] == "NSE:INFY-EQ"

def test_write_live_data_success(mock_client_setup):
    client, _, _ = mock_client_setup
    mock_worksheet = MagicMock()
    client.sheet.worksheet.return_value = mock_worksheet
    
    data = [["A", 1], ["B", 2]]
    client.write_live_data(data)
    
    # Range should be A2:B3 (2 rows, 2 cols -> Col B)
    mock_worksheet.update.assert_called_with(values=data, range_name="A2:B3")

def test_write_live_data_retry_on_429(mock_client_setup):
    client, _, _ = mock_client_setup
    mock_worksheet = MagicMock()
    client.sheet.worksheet.return_value = mock_worksheet
    
    # Mock Response object for APIError
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": {"code": 429, "message": "Quota exceeded"}}
    mock_response.text = '{"error": {"code": 429, "message": "Quota exceeded"}}'
    
    error_429 = APIError(mock_response)
    error_429.response = MagicMock()
    error_429.response.status_code = 429
    
    # First call fails, second succeeds
    mock_worksheet.update.side_effect = [error_429, None]
    
    with patch("time.sleep") as mock_sleep:
        client.write_live_data([["data"]])
        
        assert mock_worksheet.update.call_count == 2
        mock_sleep.assert_called_once()

def test_write_live_data_triggers_callback(mock_client_setup):
    client, _, _ = mock_client_setup
    mock_worksheet = MagicMock()
    client.sheet.worksheet.return_value = mock_worksheet
    
    # Mock persistent failure
    client.on_error = MagicMock()
    mock_worksheet.update.side_effect = Exception("General Error")
    
    with patch("time.sleep"): # Suppress sleep
        with pytest.raises(Exception):
            client.write_live_data([["data"]], retries=2)
            
    assert client.on_error.call_count == 1
    call_args = client.on_error.call_args
    assert call_args[0][0] == "SHEETS_WRITE_ERROR"
