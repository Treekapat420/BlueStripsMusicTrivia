from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
    round_len: int = int(os.getenv("ROUND_LEN", 1))
    answer_seconds: int = int(os.getenv("ANSWER_SECONDS", 20))
    streak_bonus_cap: int = int(os.getenv("STREAK_BONUS_CAP", 10))
    weekly_reset_day: str = os.getenv("WEEKLY_RESET_DAY", "SUN").upper()
    winners_count: int = int(os.getenv("WINNERS_COUNT", 3))
    payouts_dry_run: bool = os.getenv("PAYOUTS_DRY_RUN", "true").lower() == "true"

    database_url: str | None = os.getenv("DATABASE_URL", None)

    # Solana
    treasury_private_key: str | None = os.getenv("TREASURY_PRIVATE_KEY", None)
    strip_mint: str | None = os.getenv("STRIP_MINT", None)
    rpc_endpoint: str = os.getenv("RPC_ENDPOINT", "https://api.mainnet-beta.solana.com")
    rpc_commitment: str = os.getenv("RPC_COMMITMENT", "processed")

settings = Settings()
