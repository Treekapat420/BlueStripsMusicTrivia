# Manual-payout stub: no Solana SDK needed

class PayoutClient:
    def __init__(self, *args, **kwargs):
        # kept for compatibility with the rest of the code
        pass

    def transfer_spl(self, mint: str, treasury_key: str, to_wallet: str, amount: int, dry_run: bool = True):
        # We do NOT broadcast any transactions in manual mode.
        # Return a fake signature so the admin output looks consistent.
        _ = (mint, treasury_key, to_wallet, amount, dry_run)
        return f"DRY_RUN_TX_SIG_{(to_wallet or 'WALLET')[:8]}"
