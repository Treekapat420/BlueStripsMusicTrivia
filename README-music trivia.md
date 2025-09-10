# Blue Strips Trivia Bot

A Telegram bot for **weekly music-trivia** contests that tracks scores, shows leaderboards, and prepares **$STRIP (Solana SPL)** payouts each week.

## Features
- 🎵 Multiple-choice **music trivia** (OpenTDB Music category) or local JSON questions.
- ⏱️ Timed rounds, streak bonuses, anti-spam cool-down.
- 🏆 **Weekly scoreboard** with automatic ISO-week key (e.g., 2025-W35).
- 📤 Weekly **CSV export** for records and payouts.
- 💸 Admin tools to **compute payouts** and (optionally) **send SPL tokens** from a treasury wallet (*dry-run by default*).
- 🧑‍🤝‍🧑 Works in **groups** or **DMs**. SQLite by default; Postgres via `DATABASE_URL`.
- 🚀 Railway/Nixpacks ready (`Procfile`, `nixpacks.toml`).

## Quick Start
1. Create a bot with **@BotFather** → copy the token.
2. Create/choose a **Solana treasury** wallet that will fund weekly payouts; keep its key **secret**.
3. Copy `.env.example` → `.env`, fill in values.
4. Install & run locally:
   ```bash
   pip install -r requirements.txt
   python -m src.bot
   ```
5. Deploy on **Railway**:
   - Create a project → Upload this repo/zip.
   - Add environment variables from `.env.example`.
   - Railway auto-starts the worker via `Procfile`.

## Commands
- `/start` – Register and get help.
- `/join` – Opt in to this week’s contest (creates your weekly score row).
- `/quiz` – Start a mini round (3–10 questions).
- `/answer <A|B|C|D>` – Answer the current question.
- `/leaderboard` – Show weekly top users.
- `/myscore` – Show your stats this week.
- `/wallet <address>` – Save your Solana address for payouts.
- `/rules` – Show scoring rules.
- `/help` – Show commands.

### Admin
- `/admin status` – Bot and env status.
- `/admin endweek` – Lock/export current week CSV.
- `/admin payout` – Compute/execute SPL payouts (respects `PAYOUTS_DRY_RUN`).
- `/admin reset` – Reset weekly board (after export).

## Scoring (defaults)
- Correct: **+10 pts**
- Time bonus: **up to +5** (faster answers earn more)
- Streak bonus: **+2** per consecutive correct (caps at `STREAK_BONUS_CAP`)
- Wrong: **0** (ends streak)
- Answer window: **20s per question** (`ANSWER_SECONDS`)

## Payouts
- Top `WINNERS_COUNT` players split the pool **proportionally** to their points (or adjust the logic).
- Users must set a wallet via `/wallet <address>`.
- Payouts rely on **solana-py**; **dry-run by default**. Only enable live transfers once tested.

## Data
- Tables: `users`, `wallets`, `scores`, `questions`, `payouts`.
- Weekly export to `data/leaderboard_<YYYY-WW>.csv`.

## Security
- Keep `TREASURY_PRIVATE_KEY` secret (env var). Use a **dedicated payout wallet**.
- Keep `PAYOUTS_DRY_RUN=true` until you’re ready.

## Local Questions
Add custom music Qs in `data/questions.json` (schema in file).

---

MIT License
