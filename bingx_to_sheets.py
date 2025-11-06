import json
import sys
import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Map ccxt module
import bingx.ccxt as ccxt_module
sys.modules['ccxt'] = ccxt_module

from bingx.ccxt import bingx as BingxSync

def load_api_keys():
    """Load API keys from file or environment variables"""
    # Try environment variables first (for GitHub Actions)
    api_key = os.getenv('BINGX_API_KEY')
    api_secret = os.getenv('BINGX_API_SECRET')
    
    if api_key and api_secret:
        return api_key, api_secret
    
    # Fall back to local file
    try:
        with open("api_key.json", "r") as f:
            data = json.load(f)
        return data["api_key"], data["api_secret"]
    except FileNotFoundError:
        raise Exception("API keys not found in environment or api_key.json file")

def load_google_credentials():
    """Load Google credentials from file or environment variable"""
    # Try environment variable first (for GitHub Actions)
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_json:
        # Write to temporary file
        with open("google_credentials.json", "w") as f:
            f.write(creds_json)
    
    # Check if file exists
    if not os.path.exists("google_credentials.json"):
        raise Exception("Google credentials not found")

def get_positions_data(api_key, api_secret):
    """Fetch all positions from BingX"""
    try:
        client = BingxSync({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })
        
        positions = client.fetch_positions()
        print(f"✓ Fetched {len(positions)} positions from BingX")
        return positions
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return []

def send_to_google_sheets(positions, sheet_id):
    """Send position data to Google Sheets"""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    try:
        # Load credentials
        load_google_credentials()
        
        # Authenticate
        creds = Credentials.from_service_account_file(
            'google_credentials.json', 
            scopes=SCOPES
        )
        
        service = build('sheets', 'v4', credentials=creds)
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if sheet exists and has data
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range='Positions!A1'
            ).execute()
            current_values = result.get('values', [])
        except Exception as e:
            print(f"⚠️  Sheet might not exist: {e}")
            current_values = []
        
        # Prepare header row (only once)
        headers = [
            "Timestamp", "Symbol", "Side", "Entry Price", "Mark Price", 
            "Contracts", "Notional", "Unrealized P&L", "Realized P&L", 
            "Total P&L", "Leverage", "Margin Mode", "Liquidation Price", 
            "Initial Margin", "P&L %"
        ]
        
        # Prepare data rows
        rows = []
        if not current_values:
            rows.append(headers)
        
        position_count = 0
        for position in positions:
            if position.get('contracts') and position.get('contracts') > 0:  # Only active positions
                unrealized = float(position.get('unrealizedPnl', 0))
                realized = float(position.get('realizedPnl', 0))
                total_pnl = unrealized + realized
                notional = float(position.get('notional', 0))
                pnl_percent = (total_pnl / notional * 100) if notional > 0 else 0
                
                row = [
                    timestamp,
                    position.get('symbol', ''),
                    position.get('side', ''),
                    round(float(position.get('entryPrice', 0)), 8),
                    round(float(position.get('markPrice', 0)), 8),
                    round(float(position.get('contracts', 0)), 8),
                    round(notional, 4),
                    round(unrealized, 8),
                    round(realized, 8),
                    round(total_pnl, 8),
                    position.get('leverage', ''),
                    position.get('marginMode', ''),
                    position.get('liquidationPrice', ''),
                    round(float(position.get('initialMargin', 0)), 4),
                    round(pnl_percent, 2)
                ]
                rows.append(row)
                position_count += 1
        
        if position_count == 0:
            print("⚠️  No active positions to log")
            return
        
        # Append to sheet
        body = {
            'values': rows
        }
        
        append_range = f"Positions!A{len(current_values) + 1}" if current_values else "Positions!A1"
        
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=append_range,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        updated_rows = result.get('updates', {}).get('updatedRows', 0)
        print(f"✅ Successfully logged {position_count} position(s) to Google Sheets")
        
    except Exception as e:
        print(f"❌ Error sending to Google Sheets: {e}")
        raise

if __name__ == "__main__":
    try:
        # Get Sheet ID from environment or use default
        SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1NADCWY48TpJU4jBrw0Bow1TEGxHBBwsTxwEstHDQPyU')
        
        print("=" * 50)
        print("BingX Portfolio Tracker")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Load API keys
        key, secret = load_api_keys()
        print("✓ API keys loaded")
        
        # Get positions
        positions = get_positions_data(key, secret)
        
        if positions:
            # Send to Google Sheets
            send_to_google_sheets(positions, SHEET_ID)
            print("=" * 50)
            print("✅ Tracker run completed successfully")
        else:
            print("❌ No positions found or error fetching data")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
