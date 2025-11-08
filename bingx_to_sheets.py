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


def get_all_position_fields(position):
    """Extract ALL available fields from a position object"""
    fields = {
        'Basic Info': {
            'symbol': position.get('symbol'),
            'side': position.get('side'),
            'positionMode': position.get('positionMode'),
            'marginMode': position.get('marginMode'),
            'marginType': position.get('marginType'),
        },
        'Pricing': {
            'entryPrice': position.get('entryPrice'),
            'markPrice': position.get('markPrice'),
            'liquidationPrice': position.get('liquidationPrice'),
            'estLiquidationPrice': position.get('estLiquidationPrice'),
        },
        'Position Size': {
            'contracts': position.get('contracts'),
            'contractSize': position.get('contractSize'),
            'percentage': position.get('percentage'),
            'notional': position.get('notional'),
            'collateral': position.get('collateral'),
        },
        'P&L': {
            'unrealizedPnl': position.get('unrealizedPnl'),
            'realizedPnl': position.get('realizedPnl'),
        },
        'Leverage & Margin': {
            'leverage': position.get('leverage'),
            'initialMargin': position.get('initialMargin'),
            'maintMargin': position.get('maintMargin'),
            'marginRequired': position.get('marginRequired'),
            'marginAvailable': position.get('marginAvailable'),
            'marginRatio': position.get('marginRatio'),
            'mmratio': position.get('mmratio'),
        },
        'Funding': {
            'fundingRate': position.get('fundingRate'),
            'fundingFee': position.get('fundingFee'),
            'nextFundingTime': position.get('nextFundingTime'),
        },
        'Timestamps': {
            'timestamp': position.get('timestamp'),
            'datetime': position.get('datetime'),
        }
    }
    return fields


def print_all_positions_detailed(positions):
    """Print detailed information for ALL positions"""
    if not positions:
        print("\n⚠️  No positions found - will still generate trading recommendations")
        return
    
    print(f"\n{'='*100}")
    print(f"DETAILED POSITION INFORMATION - Total: {len(positions)} positions")
    print(f"{'='*100}")
    
    for idx, pos in enumerate(positions, 1):
        contracts = safe_float(pos.get('contracts', 0))
        status = "ACTIVE" if contracts > 0 else "CLOSED"
        
        print(f"\n[Position {idx}] {pos.get('symbol', 'UNKNOWN')} - {status}")
        print("-" * 100)
        
        all_fields = get_all_position_fields(pos)
        
        for category, fields_dict in all_fields.items():
            has_values = any(v is not None for v in fields_dict.values())
            if has_values:
                print(f"\n  {category}:")
                for field_name, value in fields_dict.items():
                    if value is not None:
                        print(f"    {field_name}: {value}")


def format_all_positions_for_analysis(positions):
    """Format ALL positions (active and inactive) for Perplexity analysis"""
    if not positions:
        return """No open positions currently."""
    
    summary = ""
    
    active = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
    inactive = [p for p in positions if safe_float(p.get('contracts', 0)) == 0]
    
    if active:
        summary += "### ACTIVE POSITIONS:\n\n"
        for pos in active:
            unrealized = safe_float(pos.get('unrealizedPnl', 0))
            realized = safe_float(pos.get('realizedPnl', 0))
            total_pnl = unrealized + realized
            notional = safe_float(pos.get('notional', 0))
            pnl_pct = (total_pnl / notional * 100) if notional > 0 else 0
            
            summary += f"""**{pos.get('symbol')} ({pos.get('side')})**
- Entry: {pos.get('entryPrice')} | Mark: {pos.get('markPrice')} | Liquidation: {pos.get('liquidationPrice')}
- Size: {pos.get('contracts')} contracts | Notional: ${notional:.2f}
- P&L: ${total_pnl:.2f} ({pnl_pct:.2f}%) | Unrealized: ${unrealized:.2f} | Realized: ${realized:.2f}
- Leverage: {pos.get('leverage')}x | Margin: ${safe_float(pos.get('initialMargin', 0)):.2f} | Mode: {pos.get('marginMode')}
- Funding Rate: {pos.get('fundingRate')}
- Margin Ratio: {pos.get('marginRatio')}


"""
    
    if inactive:
        summary += f"### CLOSED POSITIONS: ({len(inactive)} position(s))\n\n"
        for pos in inactive:
            realized = safe_float(pos.get('realizedPnl', 0))
            summary += f"- **{pos.get('symbol')}**: Realized P&L: ${realized:.2f}\n"
    
    return summary


def generate_position_analysis_prompt(positions):
    """Generate prompt for analyzing current positions only"""
    
    active_positions = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
    
    if not active_positions:
        return "No active positions to analyze."
    
    positions_summary = format_all_positions_for_analysis(positions)
    
    prompt = f"""POSITION ANALYSIS TASK:

{positions_summary}

Analyze my current open positions and provide:

1. **CURRENT POSITION STATUS TABLE:**
   | Symbol | Side | Entry | Mark | P&L $ | P&L % | Leverage | Liquidation | Margin Ratio | Status |
   
2. **POSITION MANAGEMENT RECOMMENDATIONS:**
   For each position:
   - Should I HOLD, ADD, or EXIT?
   - Current risk/reward ratio
   - Recommended stop-loss level
   - Take-profit targets
   - Time to exit recommendation (if any)

3. **RISK ASSESSMENT:**
   - Overall portfolio leverage
   - Funding rate impact per position
   - Correlation risks between positions
   - Liquidation risk analysis
   - Margin requirements vs available margin

4. **ACTION ITEMS:**
   | Symbol | Action | Target Price | Reason | Priority |

Format as structured tables with specific numbers. Be precise and actionable."""

    return prompt


def generate_market_research_prompt():
    """Generate prompt for deep market research on assets"""
    
    prompt = """MARKET RESEARCH AND TRADING SIGNALS TASK:

Analyze the current cryptocurrency and stock markets for Bitcoin (BTC), Amazon (AMZN), Google (GOOGL), and Tesla (TSLA).

1. **CURRENT PRICE & SENTIMENT TABLE:**
   | Asset | Current Price | 24h Change % | Sentiment | Trend | Volume |

2. **TECHNICAL ANALYSIS TABLE:**
   | Asset | RSI | MACD | Moving Avg | Support | Resistance | Signal |

3. **FUNDAMENTAL CATALYSTS:**
   For each asset:
   - Recent news and events
   - Upcoming earnings or economic data
   - Regulatory updates
   - Market sentiment indicators

4. **TRADING OPPORTUNITIES TABLE:**
   | Asset | Signal | Entry Price | Stop Loss | Take Profit | P&L Target % | R:R Ratio | Confidence % | Timeframe | Rationale |

5. **SHORT-TERM TRADING SETUPS:**
   - Scalping opportunities (quick 1-5% gains)
   - Swing trade setups (5-15% gains)
   - Momentum plays with catalysts
   - Volume spike analysis

6. **EXECUTION PLAN:**
   | Asset | Action | Order Type | Price | Quantity | Risk/Reward | Notes |

7. **MARKET CORRELATIONS & RISKS:**
   - Asset correlations
   - Sector movements affecting each asset
   - Macro risks (interest rates, economic data)
   - Timing considerations for entries

CRITICAL REQUIREMENTS:
- Use REAL-TIME current prices and data
- Provide specific price levels (not ranges)
- Include all units ($, %, etc.)
- Format all data as copy-paste ready for Google Sheets
- Cite news sources for catalysts
- Use section headers (##) for organization
- Be specific about timeframes for trades
- Include confidence levels and risk assessments"""

    return prompt


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


def write_all_positions_to_sheet(service, sheet_id, positions, timestamp):
    """Write ALL positions to Google Sheets"""
    try:
        sheet_name = "All Positions"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        # STEP 1: Clear ALL data from sheet (A1:Z5000)
        print(f"🗑️  Clearing '{sheet_name}' sheet...")
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:Z5000'
        ).execute()
        
        headers = [
            "Timestamp", "Symbol", "Side", "Status", "Entry Price", "Mark Price", 
            "Contracts", "Notional Value", "Unrealized P&L", "Realized P&L", 
            "Total P&L", "P&L %", "Leverage", "Margin Mode", "Initial Margin",
            "Liquidation Price", "Funding Rate", "Margin Ratio", "Percentage"
        ]
        
        rows = [headers]
        
        if not positions:
            rows.append([timestamp, "NO POSITIONS", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"])
            print(f"✅ No positions - recorded in sheet")
        else:
            for pos in positions:
                contracts = safe_float(pos.get('contracts', 0))
                status = "ACTIVE" if contracts > 0 else "CLOSED"
                
                unrealized = safe_float(pos.get('unrealizedPnl', 0))
                realized = safe_float(pos.get('realizedPnl', 0))
                total_pnl = unrealized + realized
                notional = safe_float(pos.get('notional', 0))
                pnl_pct = (total_pnl / notional * 100) if notional > 0 else 0
                entry_price = safe_float(pos.get('entryPrice', 0))
                mark_price = safe_float(pos.get('markPrice', 0))
                liquidation_price = safe_float(pos.get('liquidationPrice', 0))
                initial_margin = safe_float(pos.get('initialMargin', 0))
                margin_ratio = safe_float(pos.get('marginRatio', 0))
                percentage = safe_float(pos.get('percentage', 0))
                
                rows.append([
                    timestamp,
                    pos.get('symbol', ''),
                    pos.get('side', ''),
                    status,
                    safe_round(entry_price, 8),
                    safe_round(mark_price, 8),
                    safe_round(contracts, 8),
                    safe_round(notional, 4),
                    safe_round(unrealized, 8),
                    safe_round(realized, 8),
                    safe_round(total_pnl, 8),
                    safe_round(pnl_pct, 2),
                    pos.get('leverage', ''),
                    pos.get('marginMode', ''),
                    safe_round(initial_margin, 4),
                    safe_round(liquidation_price, 2),
                    pos.get('fundingRate', ''),
                    safe_round(margin_ratio, 4),
                    safe_round(percentage, 2)
                ])
        
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:S2000'
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Updated 'All Positions' sheet")
        
    except Exception as e:
        print(f"❌ Error writing positions: {e}")
        raise


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
                # Parse markdown table
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
        
        rows = [
            ["Timestamp", timestamp],
            ["Type", sheet_name],
            ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""]
        ]
        
        # Format and add analysis
        analysis_rows = format_analysis_for_csv(analysis_content)
        rows.extend(analysis_rows)
        
        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:Z2000'
        ).execute()
        
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
        raise


def send_to_perplexity_for_position_analysis(positions, perplexity_api_key):
    """Send position analysis request to Perplexity"""
    try:
        active_positions = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
        
        if not active_positions:
            print("⚠️  No active positions - skipping position analysis")
            return None
        
        print("\n📊 Sending position analysis to Perplexity (Research Mode)...")
        
        prompt = generate_position_analysis_prompt(positions)
        
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 2000,
            "search_recency_filter": "week"
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        response.raise_for_status()
        result = response.json()
        
        analysis = result['choices'][0]['message']['content']
        print("✓ Received position analysis from Perplexity")
        
        return analysis
    except Exception as e:
        print(f"❌ Error in position analysis: {e}")
        return None


def send_to_perplexity_for_market_research(perplexity_api_key):
    """Send market research request to Perplexity"""
    try:
        print("\n🔍 Sending market research request to Perplexity (Deep Research Mode)...")
        
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
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 4000,
            "top_k": 3,
            "search_recency_filter": "month"
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


if __name__ == "__main__":
    try:
        print("=" * 100)
        print("BingX Portfolio Tracker - All Analysis to Google Sheets")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        print()
        
        # Get Sheet ID from environment or use default
        SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '1NADCWY48TpJU4jBrw0Bow1TEGxHBBwsTxwEstHDQPyU')
        
        # Load API keys
        api_key, api_secret = load_api_keys()
        perplexity_api_key = load_perplexity_api_key()
        
        # Get all positions
        positions = get_positions(api_key, api_secret)
        
        # Print position details
        print_all_positions_detailed(positions)
        
        # Load Google credentials
        load_google_credentials()
        
        # Setup Google Sheets service
        creds = Credentials.from_service_account_file(
            'google_credentials.json',
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        
        service = build('sheets', 'v4', credentials=creds)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write positions to sheet
        write_all_positions_to_sheet(service, SHEET_ID, positions, timestamp)
        
        # PART 1: Position Analysis (if have positions)
        position_analysis = send_to_perplexity_for_position_analysis(positions, perplexity_api_key)
        
        if position_analysis:
            print("Position analysis received, formatting for sheets...")
            write_to_analysis_sheet(service, SHEET_ID, "Position Analysis", position_analysis, timestamp)
        
        # PART 2: Market Research (always run)
        market_research = send_to_perplexity_for_market_research(perplexity_api_key)
        
        if market_research:
            print("Market research received, formatting for CSV-compatible sheets...")
            write_to_analysis_sheet(service, SHEET_ID, "Market Research", market_research, timestamp)
        
        print()
        print("=" * 100)
        print("✅ Tracker completed successfully - All data written to Google Sheets")
        print("=" * 100)
        print("\n📊 Google Sheets updated:")
        print("   - 'All Positions' sheet (current holdings)")
        if position_analysis:
            print("   - 'Position Analysis' sheet (hold/exit/add recommendations)")
        print("   - 'Market Research' sheet (trading signals & opportunities)")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
