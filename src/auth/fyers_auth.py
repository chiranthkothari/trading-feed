import os
import json
import time
import logging
import pyotp
import requests
import urllib.parse
import hashlib
from datetime import datetime
import base64
from fyers_apiv3 import fyersModel
from src.config import Config

logger = logging.getLogger(__name__)

class FyersAuthenticator:
    def __init__(self, token_path="access_token.json", on_error=None):
        self.token_path = token_path
        self.client_id = Config.FYERS_APP_ID
        self.secret_key = Config.FYERS_SECRET_KEY
        self.redirect_uri = Config.FYERS_REDIRECT_URI
        self.user_id = Config.FYERS_USER_ID
        self.totp_secret = Config.FYERS_TOTP_SECRET
        self.pin = Config.FYERS_PIN
        self.access_token = None
        self.on_error = on_error  # Function to call on critical failure (e.g. for notifications)

    def get_totp(self):
        """Generates TOTP using the stored secret."""
        try:
            totp = pyotp.TOTP(self.totp_secret)
            return totp.now()
        except Exception as e:
            msg = f"Failed to generate TOTP: {e}"
            logger.error(msg)
            if self.on_error: self.on_error("AUTH_ERROR", msg)
            raise



    def authenticate(self):
        """Main authentication flow: Load token -> Check validity -> Refresh if possible -> Login if needed."""
        self.access_token = self._load_token()
        
        if self._is_token_valid():
            logger.info("Using cached access token.")
            return self.access_token
        
        # Try Refresh Token Flow
        if os.path.exists("refresh_token.json"):
            logger.info("Found refresh_token.json. Attempting to refresh access token...")
            new_token = self._generate_access_token_from_refresh_token()
            if new_token:
                logger.info("Refresh successful.")
                return new_token
            else:
                logger.error("Refresh token failed. Falling back to headless login...")

        logger.info("Token missing or invalid. Initiating fresh login...")
        return self._perform_login()

    def _generate_access_token_from_refresh_token(self):
        """Generates a new access token using the refresh token."""
        try:
            with open("refresh_token.json", "r") as f:
                data = json.load(f)
                refresh_token = data.get("refresh_token")
            
            if not refresh_token:
                logger.error("No refresh_token found in file.")
                return None

            # Prepare AppIdHash
            app_id = self.client_id
            # If app_id has -100 suffix, Fyers V3 often expects the full string for the hash
            # but sometimes just the prefix. Let's try full string first as per Config.
            
            app_id_hash = hashlib.sha256(f"{app_id}:{self.secret_key}".encode()).hexdigest()
            
            payload = {
                "grant_type": "refresh_token",
                "appIdHash": app_id_hash,
                "refresh_token": refresh_token,
                "pin": self.pin # Sometimes required? usually not for refresh check docs.
                # Docs: { "grant_type": "refresh_token", "appIdHash": "...", "refresh_token": "...", "pin": "..." }
            }
            
            headers = {"Content-Type": "application/json"}
            resp = requests.post("https://api-t1.fyers.in/api/v3/validate-refresh-token", json=payload, headers=headers)
            
            data = resp.json()
            if data.get("s") == "ok":
                access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                self._save_token(access_token, new_refresh_token)
                return access_token
            else:
                logger.error(f"Refresh API Failed: {data}")
                return None

        except Exception as e:
            logger.error(f"Refresh Token Flow Error: {e}")
            return None

    def _load_token(self):
        """Loads access token from file."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as f:
                    data = json.load(f)
                    token = data.get("access_token")
                    created_at = data.get("created_at", 0)
                    
                    # FYERS tokens are valid for the trading day.
                    # We check if the token was created today (local time).
                    token_date = datetime.fromtimestamp(created_at).date()
                    today = datetime.now().date()
                    
                    if token and token_date >= today:
                        return token
                    else:
                        logger.info("Cached token is expired or from a previous day.")
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}")
        return None

    def _save_token(self, access_token, refresh_token=None):
        """Saves access token and optionally refresh token to files."""
        try:
            # Save Access Token
            with open(self.token_path, "w") as f:
                json.dump({"access_token": access_token, "created_at": time.time()}, f)
            logger.info(f"Access token saved to {self.token_path}")
            
            # Save Refresh Token if provided
            if refresh_token:
                with open("refresh_token.json", "w") as f:
                    json.dump({"refresh_token": refresh_token}, f)
                logger.info("Refresh token updated in refresh_token.json")
                
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")

    def _is_token_valid(self):
        """
        Checks if the current token is valid (present and not expired).
        Expiration is handled during load, so mere presence here implies validity for now.
        """
        return self.access_token is not None

    def _perform_login(self, retries=3):
        """
        Performs the login flow using fyers-apiv3 to get a new access token.
        Uses requests to automate the headless login process via user credentials + TOTP.
        """
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        
        # URL that initiates the OAuth flow
        response_url = session.generate_authcode()
        
        # Automate the login process to get the auth_code from the redirect
        auth_code = self._headless_login(response_url)
        
        if not auth_code:
            raise Exception("Failed to obtain auth code from headless login.")

        # Exchange auth code for access token
        session.set_token(auth_code)
        response = session.generate_token()
        
        if response.get("s") == "ok":
            access_token = response.get("access_token")
            refresh_token = response.get("refresh_token")
            self._save_token(access_token, refresh_token)
            return access_token
        else:
            raise Exception(f"Token generation failed: {response}")

    def _headless_login(self, auth_url):
        """
        Simulates the browser login flow to extract the auth code.
        """
        # Headers mimicking a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://trade.fyers.in",
            "Referer": "https://trade.fyers.in/"
        }
        
        s = requests.Session()
        s.headers.update(headers)

        try:
            # 1. Send Login OTP Request (Vagator API)
            # This triggers the OTP to be sent (and allows TOTP verification)
            # NOTE: internal API expects Base64 encoded ID
            raw_uid = self.user_id.strip()
            logger.info(f"DEBUG: Raw User ID being encoded: {repr(raw_uid)}")
            encoded_fy_id = base64.b64encode(raw_uid.encode()).decode()
            logger.info(f"DEBUG: Encoded User ID: {encoded_fy_id}")
            
            payload_otp = {
                "fy_id": encoded_fy_id,
                "app_id": 2  # Changed to int 2
            }
            logger.info(f"Sending OTP for User ID (Encoded): '{payload_otp['fy_id']}'")
            res_otp = s.post("https://api-t2.fyers.in/vagator/v2/send_login_otp_v2", json=payload_otp)
            
            try:
                res_otp_data = res_otp.json()
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON. Response: {res_otp.text}")
                return None
            
            if "request_key" not in res_otp_data:
                 logger.error(f"Failed to send OTP: {res_otp_data}")
                 return None
            
            request_key = res_otp_data["request_key"]

            # 2. Verify TOTP
            # Note: We use the TOTP secret to generate the current OTP
            current_otp = self.get_totp()
            payload_verify = {
                "request_key": request_key,
                "otp": current_otp
            }
            res_verify = s.post("https://api-t2.fyers.in/vagator/v2/verify_otp", json=payload_verify)
            res_verify_data = res_verify.json()
            
            if "request_key" not in res_verify_data:
                logger.error(f"Failed to verify TOTP: {res_verify_data}")
                return None
            
            request_key = res_verify_data["request_key"]

            # 3. Verify PIN
            payload_pin = {
                "request_key": request_key,
                "identity_type": "pin",
                "identifier": self.pin,
                "recaptcha_token": "" # Usually optional for API
            }
            res_pin = s.post("https://api-t2.fyers.in/vagator/v2/verify_pin_v2", json=payload_pin)
            res_pin_data = res_pin.json()
            
            if res_pin_data.get("data", {}).get("access_token"):
                 internal_token = res_pin_data["data"]["access_token"]
            else:
                 logger.error(f"Failed to verify PIN: {res_pin_data}")
                 return None

            # 4. Authorize App
            # Now we have the internal token, we visit the headers Auth URL
            headers["authorization"] = f"Bearer {internal_token}"
            headers["content-type"] = "application/json" # Reset content type if needed
            
            # We follow the redirect to capture the auth code
            # The auth_url from session.generate_authcode() is the target
            res_auth = s.get(auth_url, headers=headers, allow_redirects=False)
            
            if res_auth.status_code == 302:
                location = res_auth.headers.get("Location")
                parsed = urllib.parse.urlparse(location)
                params = urllib.parse.parse_qs(parsed.query)
                return params.get("auth_code", [None])[0]
            else:
                 # Sometimes it redirects multiple times or 200 OK with meta refresh
                 # If we are already logged in, it should 302 to the redirect_uri
                 logger.error(f"Auth URL did not redirect as expected. Status: {res_auth.status_code}")
                 return None

        except Exception as e:
            logger.error(f"Headless login failed: {e}")
            return None
