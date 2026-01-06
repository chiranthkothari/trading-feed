import pytest
from unittest.mock import MagicMock, patch
from src.market.websocket_client import MarketDataClient

@pytest.fixture
def mock_fyers_socket():
    with patch("src.market.websocket_client.FyersDataSocket") as MockSocket:
        yield MockSocket

def test_connect_success(mock_fyers_socket):
    client = MarketDataClient("test_token")
    client.connect()
    
    # Check if FyersDataSocket initialized with correct args
    mock_fyers_socket.assert_called_once()
    args, kwargs = mock_fyers_socket.call_args
    assert "test_token" in kwargs["access_token"]
    assert kwargs["reconnect"] is True
    
    # Check connect called
    mock_fyers_socket.return_value.connect.assert_called_once()
    assert client.is_connected is True # We set it naively in connect()

def test_connect_failure_triggers_callback(mock_fyers_socket):
    error_callback = MagicMock()
    client = MarketDataClient("test_token", on_error=error_callback)
    
    mock_fyers_socket.side_effect = Exception("Connection Failed")
    
    with pytest.raises(Exception):
        client.connect()
        
    error_callback.assert_called_with("WS_CONNECT_ERROR", "Connection Failed")

def test_subscribe_queues_if_disconnected():
    client = MarketDataClient("test_token")
    client.is_connected = False
    
    client.subscribe(["NSE:SBIN-EQ"])
    assert "NSE:SBIN-EQ" in client.subscriptions
    # FyersSocket subscribe not called because disconnected
    # (Mock socket is None by default)

def test_subscribe_calls_socket_if_connected(mock_fyers_socket):
    client = MarketDataClient("test_token")
    client.connect() # Init socket
    client.is_connected = True
    
    client.subscribe(["NSE:SBIN-EQ"])
    
    mock_fyers_socket.return_value.subscribe.assert_called()
    call_args = mock_fyers_socket.return_value.subscribe.call_args
    assert ["NSE:SBIN-EQ"] == call_args.kwargs["symbols"]

def test_callbacks_forwarding():
    msg_handler = MagicMock()
    err_handler = MagicMock()
    client = MarketDataClient("test_token", on_message=msg_handler, on_error=err_handler)
    
    # Simulate internal callbacks
    client._on_message({"data": "test"})
    msg_handler.assert_called_with({"data": "test"})
    
    client._on_error("Some Error")
    err_handler.assert_called_with("WS_ERROR", "Some Error")
    
    client._on_close("Reason")
    err_handler.assert_called_with("WS_CLOSED", "Connection closed.")
    assert client.is_connected is False

def test_resubscribe_on_reconnect(mock_fyers_socket):
    client = MarketDataClient("test_token")
    client.connect()
    client.subscriptions.add("NSE:RELIANCE-EQ")
    
    # Simulate reconnect callback
    client._on_connect()
    
    # Should call subscribe again
    # We expect 2 calls: 1 from connect() (if we verified that), but let's check recent call
    mock_fyers_socket.return_value.subscribe.assert_called_with(symbols=["NSE:RELIANCE-EQ"])
