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
        
        # Get all available fields
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
        return """## Trading Portfolio Status:
No open positions currently.

Please analyze the following assets for potential entry opportunities:
- Bitcoin (BTC)
- Amazon (AMZN) 
- Google (GOOGL)
- Tesla (TSLA)"""
    
    summary = "## All Trading Positions Summary:\n\n"
    
    # Group by active and inactive
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
    else:
        summary += "### No active positions\n\n"
    
    if inactive:
        summary += f"\n### CLOSED POSITIONS: ({len(inactive)} position(s))\n\n"
        for pos in inactive:
            realized = safe_float(pos.get('realizedPnl', 0))
            summary += f"- **{pos.get('symbol')}**: Realized P&L: ${realized:.2f}\n"
    
    return summary



def generate_ai_trading_prompt(positions):
    """Generate AI trading analysis prompt based on current positions"""
    
    active_positions = [p for p in positions if safe_float(p.get('contracts', 0)) > 0]
    
    positions_summary = format_all_positions_for_analysis(positions)
    
    if not active_positions:
        # No open positions - generate prompt for new trading opportunities
        prompt = f"""I'm a cryptocurrency trader using BingX. I need analysis for quick profit trading.

{positions_summary}

You are a professional short-term trader focusing on quick profits. Analyze the latest market data for Bitcoin (BTC), Amazon (AMZN), Google (GOOGL), and Tesla (TSLA) with emphasis on:

1. **Immediate Entry Signals:**
   - Buy or sell signals suitable for quick entry and exit
   - Key support/resistance levels for scalping/swing trades
   - Entry and exit prices with tight stop-loss levels
   - Brief explanation of short-term trends, volatility, catalysts

2. **Profit Targets:**
   - Potential quick profit targets (1-5% gains)
   - Risk-to-reward ratio for each setup
   - Volume spike analysis and momentum indicators (RSI, MACD, Stochastic Oscillator)

3. **Risk Management:**
   - Highlight any rapid trading risks
   - Position sizing recommendations
   - Market volatility assessment

4. **Trading Orders to Place:**
   - Specific buy/sell orders with exact prices
   - Recommended entry points with quantities
   - Stop-loss and take-profit prices
   - Order types (limit, market, etc.)

Present in a concise table for fast decision-making. Prioritize actionable, timely, high-probability setups for rapid gains.

⚠️ NOTE: Currently NO open positions. These recommendations are for potential NEW entries to execute immediately."""
    else:
        # With open positions - generate prompt considering current holdings
        prompt = f"""I'm a cryptocurrency trader using BingX. I need comprehensive analysis for my portfolio.

{positions_summary}

Based on my open positions and the current market for Bitcoin (BTC), Amazon (AMZN), Google (GOOGL), and Tesla (TSLA), provide:

1. **CURRENT POSITION ANALYSIS:**
   - For each open position: Should I hold, add to, or exit?
   - Current risk/reward assessment
   - Stop-loss and take-profit recommendations
   - Unrealized P&L interpretation and next moves

2. **NEW TRADING OPPORTUNITIES:**
   - Immediate buy or sell signals for assets without positions
   - Key support/resistance levels
   - Entry and exit prices with tight stop-loss levels
   - Estimate quick profit targets (1-5% gains)
   - Momentum indicators (RSI, MACD, Stochastic) analysis

3. **PORTFOLIO RISK MANAGEMENT:**
   - Overall portfolio health assessment
   - Leverage and margin ratio evaluation
   - Funding rate impact on profitability
   - Position balance recommendations
   - Overall market risks and catalysts
   - Diversification suggestions

4. **QUICK PROFIT STRATEGY:**
   - Short-term trading opportunities (scalping/swing)
   - Volume spike analysis
   - Volatility assessment for each asset
   - Time-sensitive catalysts or news

5. **TRADING ORDERS TO PLACE:**
   - Specific orders for position adjustments
   - New entry points for uncovered assets
   - Exit prices for current positions if needed

Focus on short-term trends and actionable recommendations. Present in a concise table format for fast decision-making."""
    
    return prompt



def print_ai_prompt_section(positions):
    """Print the AI prompt that should be sent to an AI model"""
    print("\n" + "=" * 100)
    print("AI TRADING PROMPT FOR DEEP RESEARCH & QUICK PROFIT ANALYSIS")
    print("=" * 100)
    print()
    
    prompt = generate_ai_trading_prompt(positions)
    print(prompt)
    
    print("\n" + "=" * 100)
    print("USAGE INSTRUCTIONS:")
    print("=" * 100)
    print("""
1. Copy the prompt above
2. Send it to your AI model (ChatGPT, Claude, Perplexity, etc.)
3. The AI will analyze positions (if any) and recommend buy/sell actions
4. The prompt automatically generates trading recommendations even with NO positions
""")



def save_ai_prompt_to_file(positions, filename="ai_trading_prompt.txt"):
    """Save the AI prompt to a text file"""
    try:
        prompt = generate_ai_trading_prompt(positions)
        
        with open(filename, "w") as f:
            f.write("AI TRADING PROMPT FOR QUICK PROFIT ANALYSIS\n")
            f.write("=" * 100 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            f.write(prompt)
        
        print(f"\n✅ AI prompt saved to: {filename}")
        
    except Exception as e:
        print(f"❌ Error saving AI prompt: {e}")



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
                        'gridProperties': {'rowCount': 1000, 'columnCount': 20}
                    }
                }
            }]}
        ).execute()
        
        return True
    except Exception as e:
        raise



def write_all_positions_to_sheet(service, sheet_id, positions, timestamp):
    """Write ALL positions (including closed ones) to Google Sheets with safe value handling"""
    try:
        sheet_name = "All Positions"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        # Extended headers
        headers = [
            "Timestamp", "Symbol", "Side", "Status", "Entry Price", "Mark Price", 
            "Contracts", "Notional Value", "Unrealized P&L", "Realized P&L", 
            "Total P&L", "P&L %", "Leverage", "Margin Mode", "Initial Margin",
            "Liquidation Price", "Funding Rate", "Margin Ratio", "Percentage"
        ]
        
        rows = [headers]
        active_count = 0
        closed_count = 0
        
        if not positions:
            rows.append([timestamp, "NO POSITIONS", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"])
            print(f"✅ No positions to write - recorded in sheet")
        else:
            # Loop through ALL positions with safe value handling
            for pos in positions:
                contracts = safe_float(pos.get('contracts', 0))
                status = "ACTIVE" if contracts > 0 else "CLOSED"
                
                if status == "ACTIVE":
                    active_count += 1
                else:
                    closed_count += 1
                
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
            
            print(f"✅ Wrote {active_count} active + {closed_count} closed position(s) to sheet")
        
        # Clear and update sheet
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:S1000'
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
    except Exception as e:
        print(f"❌ Error writing to sheet: {e}")
        import traceback
        traceback.print_exc()
        raise



def write_analysis_to_sheet(service, sheet_id, analysis, timestamp):
    """Write Perplexity analysis to Google Sheet"""
    try:
        sheet_name = "Analysis"
        ensure_sheet_exists(service, sheet_id, sheet_name)
        
        # Split analysis into paragraphs and write each as a row
        paragraphs = analysis.split('\n\n')
        
        rows = [
            ["Timestamp", f"{timestamp}"],
            ["Analysis Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["Analysis Results", ""]
        ]
        
        for para in paragraphs:
            if para.strip():
                lines = para.split('\n')
                for line in lines:
                    if line.strip():
                        rows.append([line.strip()])
        
        # Clear and update sheet
        service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1:B1000'
        ).execute()
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body={'values': rows}
        ).execute()
        
        print(f"✅ Wrote analysis to 'Analysis' sheet")
        
    except Exception as e:
        print(f"❌ Error writing analysis to sheet: {e}")
        import traceback
        traceback.print_exc()
        raise



def send_to_perplexity_for_analysis(positions, perplexity_api_key):
    """Send all position data to Perplexity API for DEEP research analysis"""
    try:
        print("\nSending to Perplexity (Deep Research Mode) for analysis...")
        
        prompt = generate_ai_trading_prompt(positions)
        
        # Enhanced prompt for deep research
        deep_research_prompt = f"""{prompt}

RESEARCH REQUIREMENTS FOR DEEP ANALYSIS:
1. Search for latest market sentiment and technical analysis
2. Find recent news catalysts affecting each asset
3. Analyze funding rates and leverage trends
4. Check correlation between assets
5. Research upcoming events/earnings/economic data
6. Compare current prices vs historical support/resistance
7. Analyze volume patterns and order book dynamics
8. Identify institutional positioning if available
9. Research regulatory updates affecting these assets
10. Provide multiple trading scenarios with probabilities

Be thorough and cite all sources. Include specific data points, percentages, and timeframes.
Provide actionable trading orders ready to execute immediately."""

        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",  # Research mode
            "messages": [
                {"role": "user", "content": deep_research_prompt}
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
        
        analysis = result['choices'][0]['message']['content']
        print("✓ Received deep research analysis from Perplexity")
        
        return analysis
    except requests.exceptions.RequestException as e:
        print(f"❌ Error communicating with Perplexity: {e}")
        return "Error: Could not retrieve analysis from Perplexity"
    except Exception as e:
        print(f"❌ Error processing Perplexity response: {e}")
        return f"Error: {str(e)}"



if __name__ == "__main__":
    try:
        print("=" * 100)
        print("BingX Portfolio Tracker with Perplexity Deep Research Analysis")
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
        
        # Continue even if no positions
        print_all_positions_detailed(positions)
        
        # Generate and print AI trading prompt (works with or without positions)
        print_ai_prompt_section(positions)
        
        # Save AI prompt to file
        save_ai_prompt_to_file(positions)
        
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
        
        # Write positions to sheet (even if empty)
        write_all_positions_to_sheet(service, SHEET_ID, positions, timestamp)
        
        # Send positions to Perplexity for analysis
        analysis = send_to_perplexity_for_analysis(positions, perplexity_api_key)
        
        # Write analysis to sheet
        write_analysis_to_sheet(service, SHEET_ID, analysis, timestamp)
        
        print()
        print("=" * 100)
        print("✅ Tracker completed successfully")
        print("=" * 100)
        print("\n📁 Generated files:")
        print("   - ai_trading_prompt.txt (Trading recommendations)")
        print("   - Google Sheet updated with analysis")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)