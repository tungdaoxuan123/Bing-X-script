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
    """Load API keys from environment variables"""
    try:
        api_key = os.getenv('BINGX_API_KEY')
        api_secret = os.getenv('BINGX_API_SECRET')
        
        if not api_key or not api_secret:
            print("❌ BINGX_API_KEY or BINGX_API_SECRET environment variables not set!")
            print("\nSet them with:")
            print("  Windows: set BINGX_API_KEY=your_key")
            print("           set BINGX_API_SECRET=your_secret")
            print("  Linux/Mac: export BINGX_API_KEY=your_key")
            print("             export BINGX_API_SECRET=your_secret")
            sys.exit(1)
        
        print("✓ API keys loaded from environment variables")
        print(f"  - BINGX_API_KEY: {api_key[:10]}...{api_key[-5:]}")
        print(f"  - BINGX_API_SECRET: {api_secret[:10]}...{api_secret[-5:]}")
        
        return api_key, api_secret
        
    except Exception as e:
        print(f"❌ Error loading API keys: {e}")
        sys.exit(1)


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
        print("⚠️  Perplexity API key not found - market research will be skipped")
        return None


def safe_float(value, default=0.0):
    """Safely convert value to float with default fallback"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_round(value, decimals=2, default=0.0):
    """Safely round a value"""
    num = safe_float(value, default)
    return round(num, decimals)


def get_account_balance(api_key, api_secret):
    """Get account balance and calculate P&L - FIXED FOR BINGX"""
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
        
        # Get balance - BingX returns a dict with currency keys
        balance = client.fetch_balance()
        
        # Extract USDT balance (main trading currency)
        usdt_balance = balance.get('USDT', {})
        total_balance = safe_float(usdt_balance.get('total', 0))
        free_balance = safe_float(usdt_balance.get('free', 0))
        used_balance = safe_float(usdt_balance.get('used', 0))
        
        print(f"✓ Balance fetched:")
        print(f"  Total USDT: ${total_balance:.2f}")
        print(f"  Free USDT: ${free_balance:.2f}")
        print(f"  Used USDT: ${used_balance:.2f}")
        
        # Get positions for P&L calculation
        positions = client.fetch_positions()
        
        total_unrealized_pnl = 0
        total_realized_pnl = 0
        active_positions = 0
        
        for pos in positions:
            contracts = safe_float(pos.get('contracts', 0))
            unrealized = safe_float(pos.get('unrealizedPnl', 0))
            
            # Look for realized P&L in info
            info = pos.get('info', {})
            realized = 0
            
            # Try different keys for realized P&L
            if 'realisedProfit' in info:
                realized = safe_float(info['realisedProfit'], 0)
            elif 'realizedPnl' in info:
                realized = safe_float(info['realizedPnl'], 0)
            
            total_unrealized_pnl += unrealized
            total_realized_pnl += realized
            
            if contracts > 0:
                active_positions += 1
                print(f"  Position: {pos.get('symbol')} - Unrealized: ${unrealized:.4f}, Realized: ${realized:.4f}")
        
        total_pnl = total_unrealized_pnl + total_realized_pnl
        pnl_percentage = (total_pnl / total_balance * 100) if total_balance > 0 else 0
        
        print(f"✓ P&L calculated:")
        print(f"  Unrealized: ${total_unrealized_pnl:.4f}")
        print(f"  Realized: ${total_realized_pnl:.4f}")
        print(f"  Total P&L: ${total_pnl:.4f}")
        print(f"  P&L %: {pnl_percentage:.2f}%")
        print(f"  Active Positions: {active_positions}")
        
        return {
            'total': total_balance,
            'free': free_balance,
            'used': used_balance,
            'unrealized_pnl': total_unrealized_pnl,
            'realized_pnl': total_realized_pnl,
            'total_pnl': total_pnl,
            'pnl_percentage': pnl_percentage,
            'active_positions': active_positions,
            'status': 'OK'
        }
        
    except Exception as e:
        print(f"❌ Error fetching account balance: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'free': 0,
            'used': 0,
            'unrealized_pnl': 0,
            'realized_pnl': 0,
            'total_pnl': 0,
            'pnl_percentage': 0,
            'active_positions': 0,
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
            ["P&L (Total):", f"${safe_round(balance_info['total_pnl'], 4):.4f}"],
            ["P&L %:", f"{safe_round(balance_info['pnl_percentage'], 2):.2f}%"],
            ["", ""],
            ["Unrealized P&L:", f"${safe_round(balance_info['unrealized_pnl'], 4):.4f}"],
            ["Realized P&L:", f"${safe_round(balance_info['realized_pnl'], 4):.4f}"],
            ["", ""],
            ["Active Positions:", balance_info['active_positions']],
            ["", ""],
            ["Status", "PROFIT ✓" if balance_info['pnl_percentage'] >= 0 else "LOSS ✗"]
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


def write_all_positions_to_sheet(service, sheet_id, positions, timestamp):
    """Write ALL positions to Google Sheets"""
    try:
        sheet_name = "All Positions"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        headers = [
            "Timestamp", "Symbol", "Side", "Status", "Entry Price", "Mark Price", 
            "Contracts", "Collateral", "Unrealized P&L", "Realized P&L", 
            "Leverage", "Liquidation Price", "Margin Ratio"
        ]
        
        rows = [headers]
        
        if not positions:
            rows.append([timestamp, "NO POSITIONS", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"])
            print(f"✅ No positions - recorded in sheet")
        else:
            for pos in positions:
                contracts = safe_float(pos.get('contracts', 0))
                status = "ACTIVE" if contracts > 0 else "CLOSED"
                
                unrealized = safe_float(pos.get('unrealizedPnl', 0))
                entry_price = safe_float(pos.get('entryPrice', 0))
                mark_price = safe_float(pos.get('markPrice', 0))
                liquidation_price = safe_float(pos.get('liquidationPrice', 0))
                collateral = safe_float(pos.get('collateral', 0))
                margin_ratio = safe_float(pos.get('marginRatio', 0))
                
                # Get realized P&L from info
                info = pos.get('info', {})
                realized = 0
                if 'realisedProfit' in info:
                    realized = safe_float(info['realisedProfit'], 0)
                
                rows.append([
                    timestamp,
                    pos.get('symbol', ''),
                    pos.get('side', ''),
                    status,
                    safe_round(entry_price, 2),
                    safe_round(mark_price, 2),
                    safe_round(contracts, 4),
                    safe_round(collateral, 2),
                    safe_round(unrealized, 4),
                    safe_round(realized, 4),
                    pos.get('leverage', ''),
                    safe_round(liquidation_price, 2),
                    safe_round(margin_ratio, 4)
                ])
        
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:M2000'
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Updated 'All Positions' sheet with {len(rows)-1} positions")
        
    except Exception as e:
        print(f"❌ Error writing positions: {e}")


def generate_market_research_prompt():
    """Generate market research prompt for Perplexity"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""MARKET RESEARCH AND TRADING SIGNALS TASK:
Time generated: {current_time}

Analyze the current cryptocurrency and stock markets for Bitcoin (BTC), Ethereum (ETH), Solana (SOL), Amazon (AMZN), Google (GOOGL), and Tesla (TSLA).

Use REAL-TIME current prices and data:

1. **CURRENT PRICE & SENTIMENT TABLE:**
| Asset | Current Price | 24h Change % | Sentiment | Trend | Volume |

2. **TECHNICAL ANALYSIS TABLE:**
| Asset | RSI | MACD | Moving Avg | Support | Resistance | Signal |

3. **TRADING OPPORTUNITIES TABLE:**
| Asset | Signal | Entry Price | Stop Loss | Take Profit | P&L Target % | R:R Ratio | Confidence % | Timeframe |

4. **SHORT-TERM TRADING SETUPS:**
- Scalping opportunities (quick 1-5% gains)
- Swing trade setups (5-15% gains)
- Momentum plays with catalysts

5. **MARKET CORRELATIONS & RISKS:**
- Asset correlations
- Macro risks (interest rates, economic data)
- Liquidation risk analysis

CRITICAL REQUIREMENTS:
- Provide specific price levels (not ranges)
- Include all units ($, %, etc.)
- Format tables with pipe separators | for easy import
- Use section headers (##) for organization
- Be specific about timeframes for trades
- Include confidence levels and risk assessments"""


def send_to_perplexity_market_research(perplexity_api_key):
    """Send market research request to Perplexity"""
    try:
        print("\n🔍 Sending market research request to Perplexity...")
        
        prompt = generate_market_research_prompt()
        
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "top_p": 0.75,
            "max_tokens": 10000,
            "search_recency_filter": "day",
            "frequency_penalty": 0.1,
            "presence_penalty": 0.0
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=180
        )
        
        response.raise_for_status()
        result = response.json()
        
        research = result['choices'][0]['message']['content']
        print("✓ Received market research from Perplexity")
        
        return research
    except Exception as e:
        print(f"❌ Error in market research: {e}")
        return None


def format_analysis_for_csv(analysis_content):
    """Format analysis content into CSV-compatible rows"""
    try:
        rows = []
        lines = analysis_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Handle table rows (CSV format for Sheets)
            if line.startswith('|'):
                cells = [cell.strip() for cell in line.split('|')]
                cells = [cell for cell in cells if cell and cell != '---' and not all(c == '-' for c in cell)]
                if cells:
                    rows.append(cells)
            
            # Handle headers with ##
            elif line.startswith('##'):
                header = line.replace('##', '').replace('#', '').strip()
                if header:
                    rows.append([header])
                    rows.append([""])
            
            # Handle bullet points
            elif line.startswith('-'):
                content = line[1:].strip()
                if content:
                    rows.append([content])
            
            # Handle bold text
            elif '**' in line:
                content = line.replace('**', '').strip()
                if content:
                    rows.append([content])
            
            # Regular text (longer than 10 chars)
            elif len(line) > 10:
                rows.append([line])
        
        return rows if rows else [["No data"]]
    
    except Exception as e:
        print(f"Error formatting analysis: {e}")
        return [["Error parsing analysis"]]


def write_to_analysis_sheet(service, sheet_id, sheet_name, analysis_content, timestamp):
    """Write analysis to Google Sheets in CSV-compatible format"""
    try:
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        print(f"🗑️  Clearing '{sheet_name}' sheet...")
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:Z5000'
        ).execute()
        
        rows = [
            ["Timestamp", timestamp],
            ["Type", sheet_name],
            ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""]
        ]
        
        # Format and add analysis
        analysis_rows = format_analysis_for_csv(analysis_content)
        rows.extend(analysis_rows)
        
        # Write new data
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Updated '{sheet_name}' sheet with {len(rows)} rows")
        
    except Exception as e:
        print(f"❌ Error writing to {sheet_name}: {e}")


if __name__ == "__main__":
    try:
        print("=" * 100)
        print("BingX Portfolio Tracker - Environment Variables Version")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        print()
        
        # Get Sheet ID from environment or use default
        SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1NADCWY48TpJU4jBrw0Bow1TEGxHBBwsTxwEstHDQPyU')
        
        # Load API keys from environment
        api_key, api_secret = load_api_keys()
        
        # Get positions
        print("\n📊 Step 1: Fetching Positions")
        print("-" * 100)
        positions = get_positions(api_key, api_secret)
        
        # Get account balance (NOW FIXED)
        print("\n💰 Step 2: Fetching Account Balance")
        print("-" * 100)
        balance_info = get_account_balance(api_key, api_secret)
        
        print(f"\n✓ Final Balance Info:")
        print(f"  Total: ${balance_info['total']:.2f}")
        print(f"  P&L: ${balance_info['total_pnl']:.4f}")
        print(f"  P&L %: {balance_info['pnl_percentage']:.2f}%")
        print(f"  Status: {balance_info['status']}")
        
        # Setup Google Sheets
        print("\n📝 Step 3: Writing to Google Sheets")
        print("-" * 100)
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
        
        # Write positions
        write_all_positions_to_sheet(service, SHEET_ID, positions, timestamp)
        
        # Market Research (Optional - only if API key available)
        perplexity_key = load_perplexity_api_key()
        
        if perplexity_key:
            print("\n🔍 Step 4: Generating Market Research")
            print("-" * 100)
            
            market_research = send_to_perplexity_market_research(perplexity_key)
            
            if market_research:
                print("Market research received, formatting for sheets...")
                write_to_analysis_sheet(service, SHEET_ID, "Market Research", market_research, timestamp)
        else:
            print("\n⏭️  Step 4: Skipping Market Research (API key not available)")
        
        print()
        print("=" * 100)
        print("✅ Portfolio tracker completed successfully!")
        print("=" * 100)
        print("\n📊 Google Sheets updated:")
        print("   - '📈 Portfolio' sheet (Balance, P&L, P&L %)")
        print("   - 'All Positions' sheet (position details)")
        if perplexity_key:
            print("   - 'Market Research' sheet (trading signals & analysis)")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)