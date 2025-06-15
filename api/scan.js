import { countWalletTransactionsToday } from './scan-lib.js';

export default async function handler(req, res) {
    if (req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }
    const { wallet_address } = req.body;
    if (!wallet_address) {
        res.status(400).json({ error: 'wallet_address is required' });
        return;
    }
    try {
        const totalTxToday = await countWalletTransactionsToday(wallet_address.trim().toLowerCase());
        res.status(200).json({ total_transactions: totalTxToday });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
}