const express = require('express');
const axios = require('axios');
const { DateTime } = require('luxon');

const RPC_URL = "https://tea-sepolia.g.alchemy.com/public";
const app = express();
app.use(express.json());

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function rpcBatch(calls, retries = 3) {
    for (let attempt = 0; attempt < retries; attempt++) {
        try {
            const response = await axios.post(RPC_URL, calls, { timeout: 30000 });
            return response.data;
        } catch (e) {
            console.log(`Request failed (attempt ${attempt + 1}/${retries}): ${e}`);
            await sleep(2000);
        }
    }
    throw new Error("RPC batch failed after retries.");
}

async function getLatestBlock() {
    const response = await axios.post(RPC_URL, {
        jsonrpc: "2.0",
        method: "eth_blockNumber",
        params: [],
        id: 1
    });
    return parseInt(response.data.result, 16);
}

async function getBlockTimestamp(blockNumber) {
    const response = await axios.post(RPC_URL, {
        jsonrpc: "2.0",
        method: "eth_getBlockByNumber",
        params: [ '0x' + blockNumber.toString(16), false ],
        id: 1
    });
    const result = response.data.result;
    if (result) {
        return parseInt(result.timestamp, 16);
    }
    return null;
}

async function findStartBlockOfToday(latestBlock) {
    const now = DateTime.utc();
    const todayStart = DateTime.utc(now.year, now.month, now.day, 0, 0, 0);
    const todayTimestamp = Math.floor(todayStart.toSeconds());

    let low = 0;
    let high = latestBlock;
    let startBlock = latestBlock;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const ts = await getBlockTimestamp(mid);
        if (ts === null) break;
        if (ts < todayTimestamp) {
            low = mid + 1;
        } else {
            startBlock = mid;
            high = mid - 1;
        }
    }
    return startBlock;
}

async function countWalletTransactionsToday(walletAddress) {
    const latestBlock = await getLatestBlock();
    const startBlock = await findStartBlockOfToday(latestBlock);

    let totalTx = 0;
    const batchSize = 800;
    const blockRange = [];
    for (let i = startBlock; i <= latestBlock; i++) blockRange.push(i);

    let batchCalls = [];
    for (let i = 0; i < blockRange.length; i++) {
        const blockNumber = blockRange[i];
        batchCalls.push({
            jsonrpc: "2.0",
            method: "eth_getBlockByNumber",
            params: [ '0x' + blockNumber.toString(16), true ],
            id: blockNumber
        });

        if (batchCalls.length === batchSize || blockNumber === latestBlock) {
            const responses = await rpcBatch(batchCalls);
            for (const res of responses) {
                if (res.result && res.result.transactions) {
                    for (const tx of res.result.transactions) {
                        if ((tx.from || '').toLowerCase() === walletAddress) {
                            totalTx += 1;
                        }
                    }
                }
            }
            batchCalls = [];
        }
    }
    return totalTx;
}

app.get('/', (req, res) => {
    res.sendFile(__dirname + '/index.html');
});

app.post('/scan', async (req, res) => {
    const walletAddress = (req.body.wallet_address || '').trim().toLowerCase();
    try {
        const totalTxToday = await countWalletTransactionsToday(walletAddress);
        res.json({ total_transactions: totalTxToday });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});