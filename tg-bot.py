import requests
import time
from datetime import datetime, timezone
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# --- CONFIG ---
BOT_TOKEN = "7653056986:AAFXoTWhS1DXSqWwcsyGSdlKpX4ODtuisGE"  # Replace with your bot token
RPC_URL = "https://tea-sepolia.g.alchemy.com/public"  # Replace with your Tea Sepolia RPC

# --- FUNCTIONS ---

def rpc_batch(calls, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(RPC_URL, json=calls, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, requests.exceptions.ChunkedEncodingError) as e:
            print(f"Request failed (attempt {attempt+1}/{retries}): {e}")
            time.sleep(2)
    raise Exception("RPC batch failed after retries.")

def get_latest_block():
    response = requests.post(RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    })
    result = response.json()['result']
    return int(result, 16)

def get_block_timestamp(block_number):
    response = requests.post(RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False],
        "id": 1
    })
    result = response.json()['result']
    if result:
        return int(result['timestamp'], 16)
    return None

def find_start_block_of_today(latest_block):
    now = datetime.now(timezone.utc)
    today_start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    today_timestamp = int(today_start.timestamp())

    low = 0
    high = latest_block
    start_block = latest_block

    while low <= high:
        mid = (low + high) // 2
        ts = get_block_timestamp(mid)
        if ts is None:
            break
        if ts < today_timestamp:
            low = mid + 1
        else:
            start_block = mid
            high = mid - 1

    return start_block

def count_wallet_transactions_today(wallet_address):
    latest_block = get_latest_block()
    start_block = find_start_block_of_today(latest_block)

    total_tx = 0

    batch_size = 50
    block_range = list(range(start_block, latest_block + 1))
    batch_calls = []

    for block_number in block_range:
        batch_calls.append({
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), True],
            "id": block_number
        })

        if len(batch_calls) == batch_size or block_number == latest_block:
            responses = rpc_batch(batch_calls)
            for res in responses:
                if 'result' in res and res['result']:
                    transactions = res['result']['transactions']
                    for tx in transactions:
                        if tx.get('from', '').lower() == wallet_address.lower():
                            total_tx += 1
            batch_calls = []

    return total_tx

# --- TELEGRAM BOT HANDLERS ---

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Send me your wallet address (0x...) and I will tell you how many transactions you made today!"
    )

async def handle_wallet(update: Update, context: CallbackContext):
    wallet_address = update.message.text.strip()
    
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        await update.message.reply_text("⚠️ Please send a valid Ethereum wallet address (starting with 0x).")
        return

    await update.message.reply_text("🔎 Scanning blockchain for your transactions today... This might take a few seconds.")

    try:
        total_tx = count_wallet_transactions_today(wallet_address)
        await update.message.reply_text(f"✅ Wallet {wallet_address} made {total_tx} transactions today!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking transactions: {str(e)}")

# --- MAIN ---

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()


