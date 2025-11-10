import json
import sys
import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import requests


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


def safe_float(value, default=0.0):
    """Safely convert value to float with default fallback"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_round(value, decimals=8, default=0.0):
    """Safely round a value"""
    num = safe_float(value, default)
    return round(num, decimals)


def diagnose_account(api_key, api_secret):
    """Diagnose account and show what's available"""
    try:
        print("\n" + "="*100)
        print("ACCOUNT DIAGNOSTIC")
        print("="*100)
        
        client = BingxSync({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })
        
        print("\n1. Testing fetch_balance():")
        try:
            balance = client.fetch_balance()
            print(f"   ✓ Keys: {list(balance.keys())}")
            print(f"   Total: ${safe_float(balance.get('total', 0)):.2f}")
            print(f"   Free: ${safe_float(balance.get('free', 0)):.2f}")
            print(f"   Used: ${safe_float(balance.get('used', 0)):.2f}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n2. Testing fetch_positions():")
        try:
            positions = client.fetch_positions()
            active = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
            print(f"   ✓ Found {len(positions)} total, {len(active)} active positions")
            
            if active:
                pos = active[0]
                print(f"   Sample: {pos.get('symbol')}")
                print(f"     - Contracts: {pos.get('contracts')}")
                print(f"     - Entry: {pos.get('entryPrice')}")
                print(f"     - Unrealized P&L: {pos.get('unrealizedPnl')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n" + "="*100 + "\n")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")


def get_account_balance_from_positions(api_key, api_secret):
    """Calculate balance from positions - MOST RELIABLE"""
    try:
        print("Calculating balance from positions...")
        
        client = BingxSync({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })
        
        # Get positions
        positions = client.fetch_positions()
        
        total_collateral = 0
        total_unrealized_pnl = 0
        total_realized_pnl = 0
        active_positions = 0
        
        for pos in positions:
            contracts = safe_float(pos.get('contracts', 0))
            collateral = safe_float(pos.get('collateral', 0))
            unrealized = safe_float(pos.get('unrealizedPnl', 0))
            realized = safe_float(pos.get('realizedPnl', 0))
            
            if contracts > 0:
                active_positions += 1
                print(f"  {pos.get('symbol')}: Collateral=${collateral:.2f}, Unrealized=${unrealized:.2f}")
            
            total_collateral += collateral
            total_unrealized_pnl += unrealized
            total_realized_pnl += realized
        
        total_balance = total_collateral + total_unrealized_pnl + total_realized_pnl
        total_pnl = total_unrealized_pnl + total_realized_pnl
        pnl_percentage = (total_pnl / total_balance * 100) if total_balance > 0 else 0
        
        print(f"✓ Calculated from {len(positions)} positions ({active_positions} active):")
        print(f"  Total Collateral: ${total_collateral:.2f}")
        print(f"  Unrealized P&L: ${total_unrealized_pnl:.2f}")
        print(f"  Realized P&L: ${total_realized_pnl:.2f}")
        print(f"  Estimated Balance: ${total_balance:.2f}")
        print(f"  Total P&L: ${total_pnl:.2f} ({pnl_percentage:.2f}%)")
        
        return {
            'total': total_balance,
            'free': total_collateral,
            'used': total_unrealized_pnl,
            'unrealized_pnl': total_unrealized_pnl,
            'realized_pnl': total_realized_pnl,
            'total_pnl': total_pnl,
            'pnl_percentage': pnl_percentage,
            'status': 'OK'
        }
        
    except Exception as e:
        print(f"❌ Error calculating balance: {e}")
        return {
            'total': 0,
            'free': 0,
            'used': 0,
            'unrealized_pnl': 0,
            'realized_pnl': 0,
            'total_pnl': 0,
            'pnl_percentage': 0,
            'status': f'Error: {str(e)}'
        }


def get_account_balance(api_key, api_secret):
    """Get account balance - PRIMARY METHOD"""
    try:
        print("Fetching account balance...")
        
        client = BingxSync({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })
        
        # Try primary method
        try:
            account = client.fetch_balance()
            total_balance = safe_float(account.get('total', 0))
            free_balance = safe_float(account.get('free', 0))
            used_balance = safe_float(account.get('used', 0))
            
            print(f"✓ fetch_balance() returned:")
            print(f"  Total: ${total_balance:.2f}")
            
            # If we got a real balance, use it
            if total_balance > 0:
                # Calculate P&L from positions
                positions = client.fetch_positions()
                total_unrealized = sum(safe_float(p.get('unrealizedPnl', 0)) for p in positions)
                total_realized = sum(safe_float(p.get('realizedPnl', 0)) for p in positions)
                total_pnl = total_unrealized + total_realized
                pnl_percentage = (total_pnl / total_balance * 100) if total_balance > 0 else 0
                
                return {
                    'total': total_balance,
                    'free': free_balance,
                    'used': used_balance,
                    'unrealized_pnl': total_unrealized,
                    'realized_pnl': total_realized,
                    'total_pnl': total_pnl,
                    'pnl_percentage': pnl_percentage,
                    'status': 'OK'
                }
        except Exception as e:
            print(f"⚠️  Primary method failed: {e}")
        
        # Fallback: Calculate from positions
        print("Falling back to position-based calculation...")
        return get_account_balance_from_positions(api_key, api_secret)
        
    except Exception as e:
        print(f"❌ Error fetching account balance: {e}")
        return {
            'total': 0,
            'free': 0,
            'used': 0,
            'unrealized_pnl': 0,
            'realized_pnl': 0,
            'total_pnl': 0,
            'pnl_percentage': 0,
            'status': f'Error: {str(e)}'
        }


def get_positions(api_key, api_secret):
    """Get all trading positions"""
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
        active = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
        print(f"✓ Found {len(positions)} total position(s), {len(active)} active")
        
        return positions
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return []


def load_perplexity_api_key():
    """Load Perplexity API key from environment or file"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    
    if api_key:
        print("✓ Perplexity API key loaded from environment")
        return api_key
    
    try:
        with open("perplexity_key.json", "r") as f:
            data = json.load(f)
        if "api_key" not in data:
            raise Exception("JSON file must contain 'api_key'")
        print("✓ Perplexity API key loaded from file")
        return data["api_key"]
    except FileNotFoundError:
        raise Exception("Perplexity API key not found in environment or perplexity_key.json")


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
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name,
                        'gridProperties': {'rowCount': 2000, 'columnCount': 20}
                    }
                }
            }]}
        ).execute()
        
        return True
    except Exception as e:
        raise


def write_portfolio_summary_to_sheet(service, sheet_id, balance_info, timestamp):
    """Write portfolio summary to Google Sheets"""
    try:
        sheet_name = "📈 Portfolio"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        # Format portfolio data
        rows = [
            ["📈 Portfolio Summary"],
            ["", ""],
            ["Updated", timestamp],
            ["", ""],
            ["Balance:", f"${safe_round(balance_info['total'], 2):.2f}"],
            ["Free Balance:", f"${safe_round(balance_info['free'], 2):.2f}"],
            ["Used Balance:", f"${safe_round(balance_info['used'], 2):.2f}"],
            ["", ""],
            ["P&L (Total):", f"${safe_round(balance_info['total_pnl'], 2):.2f}"],
            ["P&L %:", f"{safe_round(balance_info['pnl_percentage'], 2):.2f}%"],
            ["", ""],
            ["Unrealized P&L:", f"${safe_round(balance_info['unrealized_pnl'], 2):.2f}"],
            ["Realized P&L:", f"${safe_round(balance_info['realized_pnl'], 2):.2f}"],
            ["", ""],
            ["Status", balance_info['pnl_percentage'] >= 0 and "PROFIT ✓" or "LOSS ✗"]
        ]
        
        # Clear and update sheet
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:Z500'
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Updated '📈 Portfolio' sheet")
        
    except Exception as e:
        print(f"❌ Error writing portfolio summary: {e}")


if __name__ == "__main__":
    try:
        print("=" * 100)
        print("BingX Portfolio Tracker - FIXED VERSION")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        print()
        
        # Get Sheet ID from environment or use default
        SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1NADCWY48TpJU4jBrw0Bow1TEGxHBBwsTxwEstHDQPyU')
        
        # Load API keys
        api_key, api_secret = load_api_keys()
        
        # Run diagnostic
        print("\n📋 Running diagnostics...")
        diagnose_account(api_key, api_secret)
        
        # Get positions
        positions = get_positions(api_key, api_secret)
        
        # Get account balance (with fallback)
        balance_info = get_account_balance(api_key, api_secret)
        
        print(f"\n✓ Final Balance Info:")
        print(f"  Total: ${balance_info['total']:.2f}")
        print(f"  P&L: ${balance_info['total_pnl']:.2f}")
        print(f"  P&L %: {balance_info['pnl_percentage']:.2f}%")
        print(f"  Status: {balance_info['status']}")
        
        # Setup Google Sheets
        load_google_credentials()
        
        creds = Credentials.from_service_account_file(
            'google_credentials.json',
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        
        service = build('sheets', 'v4', credentials=creds)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write portfolio
        write_portfolio_summary_to_sheet(service, SHEET_ID, balance_info, timestamp)
        
        print()
        print("=" * 100)
        print("✅ Portfolio tracker completed successfully!")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
