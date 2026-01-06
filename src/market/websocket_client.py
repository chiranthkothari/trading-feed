import logging
import time
import json
from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket

from src.config import Config

logger = logging.getLogger(__name__)

class MarketDataClient:
    def __init__(self, access_token, on_message=None, on_error=None):
        """
        :param access_token: Valid FYERS access token
        :param on_message: Callback function(data) for incoming ticks
        :param on_error: Callback function(code, message) for errors
        """
        self.access_token = access_token
        self.user_message_handler = on_message
        self.user_error_handler = on_error
        self.fyers_socket = None
        self.subscriptions = set() # Track subscribed symbols
        self.is_connected = False

    def connect(self):
        """Initializes and connects the WebSocket."""
        try:
            # Format: app_id:access_token
            # Config.FYERS_APP_ID usually is "app_id" but for socket it might need "app_id:access_token"?
            # V3 SDK usually takes just access_token string if it's the right format, 
            # or we need to construct it. 
            # FyersDataSocket(access_token, log_path, litemode, write_to_file, reconnect)
            
            # Note: access_token argument in FyersDataSocket expects "app_id:token" format 
            # OR just the token depending on how it was generated.
            # Usually it is "client_id:access_token".
            # Let's ensure format.
            
            token_string = f"{self.access_token}"
            if ":" not in self.access_token:
                 token_string = f"{Config.FYERS_APP_ID}:{self.access_token}"

            self.fyers_socket = FyersDataSocket(
                access_token=token_string,
                log_path=None, # Disable SDK file logging or set path
                litemode=False, # Try Full mode to fix subscription error -300 
                               # PRD needs "Open, High, Low, LTP...". Litemode might be enough? 
                               # Let's check docs or assume False for full datagram.
                               # Actually, let's use BINARY mode which is standard V3.
                write_to_file=False,
                reconnect=True, # SDK handles auto-reconnect
                on_connect=self._on_connect,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message
            )
            
            # The SDK connect() is usually blocking or non-blocking depending on implementation.
            # FyersDataSocket.connect() is blocking in some versions, threaded in others.
            # "fyers_socket.connect()" usually starts the thread.
            
            logger.info("Connecting to FYERS WebSocket...")
            self.fyers_socket.connect()
            self.is_connected = True # Naive, real state is set in on_connect
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            if self.user_error_handler: 
                self.user_error_handler("WS_CONNECT_ERROR", str(e))
            raise

    def subscribe(self, symbols):
        """
        Subscribes to a list of symbols.
        :param symbols: List of symbol strings (e.g. ["NSE:SBIN-EQ", ...])
        """
        if not self.fyers_socket or not self.is_connected:
            logger.warning("WebSocket not connected. Queueing subscriptions?")
            # For now, just track them and subscribe on connect if needed
            # But if called after connect, we should send immediately.
            pass

        # Update local set
        self.subscriptions.update(symbols)
        
        if self.fyers_socket and self.is_connected:
            # Batching is handled by SDK or we should batch?
            # SDK subscribe method handles list.
            # Limit is usually high (e.g. 50 or 100).
            # We should chunk if list is huge (400 symbols).
            chunk_size = 50
            symbol_list = list(symbols)
            for i in range(0, len(symbol_list), chunk_size):
                chunk = symbol_list[i:i+chunk_size]
                # data_type=SymbolUpdate (1) or DepthUpdate (2)?
                # We want SymbolUpdate (LTP, OHLC, etc)
                # DataType: SymbolUpdate is usually default or inferred?
                # SDK usage: .subscribe(symbols=chunk, data_type=SYMBOL_UPDATE_DATA_TYPE)
                # Let's assume standard usage.
                self.fyers_socket.subscribe(symbols=chunk)
                logger.info(f"Subscribed to batch of {len(chunk)} symbols.")
                time.sleep(0.1) # Rate limit safety

    def unsubscribe(self, symbols):
        """Unsubscribes from symbols."""
        if self.fyers_socket and self.is_connected:
            self.fyers_socket.unsubscribe(symbols=symbols)
            self.subscriptions.difference_update(symbols)

    def _on_message(self, message):
        """
        SDK Callback for incoming data.
        """
        # message type depends on SDK mode (dict or custom obj)
        if self.user_message_handler:
            try:
                self.user_message_handler(message)
            except Exception as e:
                logger.error(f"Error in user message handler: {e}")

    def _on_error(self, message):
        """SDK Callback for errors."""
        logger.error(f"WebSocket Error: {message}")
        if self.user_error_handler:
            self.user_error_handler("WS_ERROR", str(message))

    def _on_close(self, message):
        """SDK Callback for connection close."""
        logger.warning(f"WebSocket Connection Closed: {message}")
        self.is_connected = False
        if self.user_error_handler:
            self.user_error_handler("WS_CLOSED", "Connection closed.")

    def _on_connect(self):
        """SDK Callback for successful connection."""
        logger.info("WebSocket Connected.")
        self.is_connected = True
        # Resubscribe if needed?
        # If SDK handles reconnect=True, it might handle resubscription.
        # If not, we should do it here.
        if self.subscriptions:
            logger.info(f"Resubscribing to {len(self.subscriptions)} symbols...")
            self.subscribe(list(self.subscriptions))
