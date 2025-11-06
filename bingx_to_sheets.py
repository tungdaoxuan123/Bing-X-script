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
    """Load API keys from environment or file"""
    api_key = os.getenv('BINGX_API_KEY')
    api_secret = os.getenv('BINGX_API_SECRET')
    
    if api_key and api_secret:
        print("✓ API keys loaded from environment")
        return api_key, api_secret
    
    try:
        with open("api_key.json", "r") as f:
            data = json.load(f)
        if "api_key" not in data or "api_secret" not in data:
            raise Exception("JSON file must contain 'api_key' and 'api_secret'")
        print("✓ API keys loaded from file")
        return data["api_key"], data["api_secret"]
    except FileNotFoundError:
        raise Exception("API keys not found in environment or api_key.json")


def get_positions(api_key, api_secret):
    """Get your own trading positions"""
    try:
        print("Fetching positions...")
        
        client = BingxSync({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })
        
        positions = client.fetch_positions()
        active = [p for p in positions if p.get('contracts', 0) > 0]
        print(f"✓ Found {len(active)} active position(s)")
        
        return positions
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return []


def load_google_credentials():
    """Load Google credentials from environment or file"""
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_json:
        with open("google_credentials.json", "w") as f:
            f.write(creds_json)
        print("✓ Google credentials loaded from environment")
        return
    
    if not os.path.exists("google_credentials.json"):
        raise Exception("Google credentials not found in environment or file")
    
    print("✓ Google credentials loaded from file")


def ensure_sheet_exists(service, sheet_id, sheet_name):
    """Ensure sheet exists"""
    try:
        props = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        for sheet in props.get('sheets', []):
            if sheet['properties']['title'] == sheet_name:
                return True
        
        # Create sheet
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name,
                        'gridProperties': {'rowCount': 1000, 'columnCount': 15}
                    }
                }
            }]}
        ).execute()
        
        return True
    except Exception as e:
        raise


def write_positions(service, sheet_id, positions, timestamp):
    """Write positions to sheet"""
    try:
        sheet_name = "Positions"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        # Clear sheet
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:O1000'
        ).execute()
        
        headers = [
            "Timestamp", "Symbol", "Side", "Entry Price", "Mark Price", 
            "Contracts", "Notional", "Unrealized P&L", "Realized P&L", 
            "Total P&L", "Leverage", "Margin Mode", "Liquidation Price", 
            "Initial Margin", "P&L %"
        ]
        
        rows = [headers]
        count = 0
        
        for pos in positions:
            if pos.get('contracts', 0) > 0:
                unrealized = float(pos.get('unrealizedPnl', 0))
                realized = float(pos.get('realizedPnl', 0))
                total_pnl = unrealized + realized
                notional = float(pos.get('notional', 0))
                pnl_pct = (total_pnl / notional * 100) if notional > 0 else 0
                
                rows.append([
                    timestamp,
                    pos.get('symbol', ''),
                    pos.get('side', ''),
                    round(float(pos.get('entryPrice', 0)), 8),
                    round(float(pos.get('markPrice', 0)), 8),
                    round(float(pos.get('contracts', 0)), 8),
                    round(notional, 4),
                    round(unrealized, 8),
                    round(realized, 8),
                    round(total_pnl, 8),
                    pos.get('leverage', ''),
                    pos.get('marginMode', ''),
                    pos.get('liquidationPrice', ''),
                    round(float(pos.get('initialMargin', 0)), 4),
                    round(pnl_pct, 2)
                ])
                count += 1
        
        if count == 0:
            rows = [headers]
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Wrote {count} position(s) to Google Sheets")
        
    except Exception as e:
        print(f"❌ Error writing to sheet: {e}")
        raise


if __name__ == "__main__":
    try:
        print("=" * 80)
        print("BingX Portfolio Tracker")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Get Sheet ID from environment or use default
        SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1NADCWY48TpJU4jBrw0Bow1TEGxHBBwsTxwEstHDQPyU')
        
        # Load API keys
        api_key, api_secret = load_api_keys()
        
        # Get positions
        positions = get_positions(api_key, api_secret)
        
        if not positions:
            print("No positions data")
            sys.exit(1)
        
        # Load Google credentials
        load_google_credentials()
        
        # Write to Google Sheets
        creds = Credentials.from_service_account_file(
            'google_credentials.json',
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        
        service = build('sheets', 'v4', credentials=creds)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        write_positions(service, SHEET_ID, positions, timestamp)
        
        print()
        print("=" * 80)
        print("✅ Tracker completed successfully")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
