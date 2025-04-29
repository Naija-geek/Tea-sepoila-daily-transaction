from flask import Flask, request, render_template_string
import requests
import time
from datetime import datetime, timezone

app = Flask(__name__)
RPC_URL = "https://tea-sepolia.g.alchemy.com/public"

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Wallet Transaction Checker</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f4f4f4;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px;
        }
        h1 {
            color: #333;
        }
        form {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 500px;
            position: relative;
        }
        label {
            font-weight: bold;
            display: block;
            margin-bottom: 10px;
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid #ccc;
            border-radius: 6px;
        }
        button {
            background-color: #008cba;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        }
        button:hover {
            background-color: #005f73;
        }
        .result {
            margin-top: 20px;
            background: #e7ffe7;
            padding: 20px;
            border: 1px solid #b2d8b2;
            border-radius: 10px;
            max-width: 500px;
        }
        .spinner {
            border: 6px solid #f3f3f3;
            border-top: 6px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            position: absolute;
            top: 50%;
            left: 50%;
            margin-top: -20px;
            margin-left: -20px;
            display: none;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        #timer {
            text-align: center;
            margin-top: 10px;
            font-size: 14px;
            color: #333;
        }
    </style>
    <script>
        let timerInterval;
        let seconds = 0;

        function startTimer() {
            seconds = 0;
            document.getElementById("timer").textContent = "⏱ Time elapsed: 0s";
            timerInterval = setInterval(() => {
                seconds++;
                document.getElementById("timer").textContent = `⏱ Time elapsed: ${seconds}s`;
            }, 1000);
        }

        function showSpinner() {
            document.getElementById("spinner").style.display = "block";
            startTimer();
        }
    </script>
</head>
<body>
    <h1>Check Today's Wallet Transactions</h1>
    <form method="POST" onsubmit="showSpinner()">
        <label for="wallet">Wallet Address:</label>
        <input type="text" name="wallet" id="wallet" placeholder="0x..." required>
        <button type="submit">Check</button>
        <div class="spinner" id="spinner"></div>
        <div id="timer"></div>
    </form>
    {% if transactions is not none %}
        <div class="result">
            ✅ Wallet <strong>{{ wallet }}</strong> made <strong>{{ transactions }}</strong> transaction(s) today.
            <br><br>⏱ <strong>Time taken:</strong> {{ duration }} seconds.
        </div>
    {% endif %}
</body>
</html>
'''


# Same RPC functions as before
def rpc_batch(calls, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(RPC_URL, json=calls, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            time.sleep(2)
    return []

def get_latest_block():
    response = requests.post(RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    })
    return int(response.json()['result'], 16)

def get_block_timestamp(block_number):
    response = requests.post(RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False],
        "id": 1
    })
    result = response.json()['result']
    return int(result['timestamp'], 16) if result else None

def find_start_block_of_today(latest_block):
    today_ts = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    low, high, start_block = 0, latest_block, latest_block
    while low <= high:
        mid = (low + high) // 2
        ts = get_block_timestamp(mid)
        if ts is None:
            break
        if ts < today_ts:
            low = mid + 1
        else:
            start_block = mid
            high = mid - 1
    return start_block

def count_wallet_transactions_today(wallet_address):
    latest_block = get_latest_block()
    start_block = find_start_block_of_today(latest_block)
    total_tx = 0
    batch_size = 500
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
                    for tx in res['result']['transactions']:
                        if tx.get('from', '').lower() == wallet_address.lower():
                            total_tx += 1
            batch_calls = []
    return total_tx

@app.route('/', methods=['GET', 'POST'])
def home():
    transactions = None
    wallet = None
    duration = None

    if request.method == 'POST':
        wallet = request.form['wallet'].strip().lower()
        start_time = time.time()
        transactions = count_wallet_transactions_today(wallet)
        duration = round(time.time() - start_time)

    return render_template_string(HTML_TEMPLATE, transactions=transactions, wallet=wallet, duration=duration)

if __name__ == "__main__":
    app.run(debug=True)
