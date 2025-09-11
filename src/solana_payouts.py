# src/solana_payouts.py
from __future__ import annotations
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.publickey import PublicKey
import base58, json

class PayoutClient:
    def __init__(self, rpc_endpoint: str, commitment: str = "processed"):
        # Keep a client handy if you later implement live transfers
        self.client = Client(rpc_endpoint, commitment=commitment)

    @staticmethod
    def _kp_from_any(key: str) -> Keypair:
        key = key.strip()
        # Supports base58 or JSON array secret keys
        try:
            return Keypair.from_secret_key(base58.b58decode(key))
        except Exception:
            arr = json.loads(key)
            return Keypair.from_secret_key(bytes(arr))

    def transfer_spl(self, mint: str, treasury_key: str, to_wallet: str, amount: int, dry_run: bool = True):
        # Manual-payout mode: we DO NOT broadcast any transactions.
        # This returns a fake signature so admin logs look consistent.
        # Later, when you want auto-payouts, implement real SPL transfers here.
        _ = (mint, treasury_key, to_wallet, amount, dry_run)
        pseudo = f"DRY_RUN_TX_SIG_{to_wallet[:8]}"
        return pseudo
