from __future__ import annotations
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.publickey import PublicKey
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address
import base58, json

class PayoutClient:
    def __init__(self, rpc_endpoint: str, commitment: str = "processed"):
        self.client = Client(rpc_endpoint, commitment=commitment)

    @staticmethod
    def _kp_from_any(key: str) -> Keypair:
        key = key.strip()
        # Supports base58 string or JSON array
        try:
            return Keypair.from_secret_key(base58.b58decode(key))
        except Exception:
            arr = json.loads(key)
            return Keypair.from_secret_key(bytes(arr))

    def transfer_spl(self, mint: str, treasury_key: str, to_wallet: str, amount: int, dry_run: bool = True):
        # In this template we DO NOT broadcast real txs unless dry_run == False and code extended.
        kp = self._kp_from_any(treasury_key)
        mint_pk = PublicKey(mint)
        to_pk = PublicKey(to_wallet)
        ata = get_associated_token_address(to_pk, mint_pk, TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID)
        # For safety, we only return a pseudo signature in dry-run.
        if dry_run:
            return f"DRY_RUN_TX_SIG_{str(ata)[:8]}"
        # Implement real token transfer logic here if you want to go live.
        raise NotImplementedError("Live SPL transfer not implemented in template.")
