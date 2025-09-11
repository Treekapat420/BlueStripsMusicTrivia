import asyncio, time
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from .utils.config import settings
from .db import Base, engine, SessionLocal
from .models import User, Score, Wallet
from .trivia import fetch_music_questions
from .scheduler import schedule_jobs
from .solana_payouts import PayoutClient

HELP = (
    "🎵 *Blue Strips Trivia Bot*\n"
    "• /join — enter this week's contest\n"
    "• /quiz — start a mini round\n"
    "• /answer A|B|C|D — answer current Q\n"
    "• /leaderboard — weekly top\n"
    "• /myscore — your stats\n"
    "• /wallet <address> — set SOL wallet for payouts\n"
    "• /rules — scoring rules\n"
    "• /help — command list\n"
    "Admins: /admin status | endweek | payout | reset"
)

# NEW: per-chat round state
CURRENT_ROUND = {}  # chat_id -> {"correct": "A", "deadline": ts, "answers": {user_id: "A"}, "task": asyncio.Task}
LOCKED_CHATS = set()

def week_key():
    now = datetime.now(timezone.utc)
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"

def ensure_db():
    Base.metadata.create_all(bind=engine)

def get_or_create_user(session: Session, msg: Message) -> User:
    u = session.execute(select(User).where(User.tg_id==msg.from_user.id)).scalar_one_or_none()
    if u: 
        # keep username up to date
        u.username = msg.from_user.username
        session.commit()
        return u
    u = User(
        tg_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name
    )
    session.add(u); session.commit()
    return u

def get_or_create_score(session: Session, user: User) -> Score:
    s = session.execute(select(Score).where(Score.user_id==user.id, Score.week_key==week_key())).scalar_one_or_none()
    if s: return s
    s = Score(user_id=user.id, week_key=week_key())
    session.add(s); session.commit()
    return s

async def cmd_start(msg: Message):
    await msg.answer("Welcome to *Blue Strips Trivia Bot*! Use /join to enter and /quiz to play. /help for more.", parse_mode="Markdown")

async def cmd_help(msg: Message):
    await msg.answer(HELP, parse_mode="Markdown")

async def cmd_rules(msg: Message):
    txt = (
        f"Scoring:\n"
        f"• Correct +10, Time bonus up to +5, Streak bonus +2 per correct (cap {settings.streak_bonus_cap}).\n"
        f"• Answer window: {settings.answer_seconds}s per question.\n"
        f"Use /answer A|B|C|D"
    )
    await msg.answer(txt)

async def cmd_join(msg: Message):
    with SessionLocal() as s:
        user = get_or_create_user(s, msg)
        get_or_create_score(s, user)
    await msg.answer("You're in for this week! Use /quiz to start a round.")

async def cmd_wallet(msg: Message):
    parts = (msg.text or "").strip().split()
    if len(parts) != 2:
        return await msg.answer("Usage: /wallet <solana_address>")
    addr = parts[1]
    if not (32 <= len(addr) <= 44):
        return await msg.answer("That doesn't look like a valid Solana address.")
    with SessionLocal() as s:
        user = get_or_create_user(s, msg)
        w = s.execute(select(Wallet).where(Wallet.user_id==user.id)).scalar_one_or_none()
        if w:
            w.address = addr
        else:
            w = Wallet(user_id=user.id, address=addr, verified=False)
            s.add(w)
        s.commit()
    await msg.answer("Wallet saved ✅")

async def cmd_quiz(msg: Message):
    if msg.chat.id in LOCKED_CHATS:
        return await msg.answer("A round is already in progress. Finish it or wait a moment.")
    LOCKED_CHATS.add(msg.chat.id)
    try:
        n = settings.round_len
        qs = await fetch_music_questions(n)
        await msg.answer(f"Starting a {n}-question round. Use /answer A|B|C|D within {settings.answer_seconds}s.")
        for q in qs:
            await _ask_question(msg, q)
    finally:
        LOCKED_CHATS.discard(msg.chat.id)

async def _ask_question(msg: Message, q: dict):
    mapping = q["options"]
    lines = [
        f"*{q['prompt']}*",
        f"A) {mapping['A']}",
        f"B) {mapping['B']}",
        f"C) {mapping['C']}",
        f"D) {mapping['D']}",
        "",
        f"_You have {settings.answer_seconds}s. Use_ `/answer A|B|C|D`",
    ]
    deadline = time.time() + settings.answer_seconds

    # cancel any previous finalize task, just in case
    old = CURRENT_ROUND.get(msg.chat.id)
    if old and old.get("task"):
        try:
            old["task"].cancel()
        except Exception:
            pass

    CURRENT_ROUND[msg.chat.id] = {
        "correct": q["correct_opt"],
        "deadline": deadline,
        "answers": {},  # user_id -> choice
        "task": asyncio.create_task(_finalize_question_after(msg.chat.id, msg.chat.type))
    }

    await msg.answer("\n".join(lines), parse_mode="Markdown")
    
async def _finalize_question_after(chat_id: int, chat_type: str):
    try:
        await asyncio.sleep(settings.answer_seconds)
    except asyncio.CancelledError:
        return

    round_state = CURRENT_ROUND.get(chat_id)
    if not round_state:
        return

    correct = round_state["correct"]
    answers = round_state["answers"]

    # Tally & award points
    awarded = []
    with SessionLocal() as s:
        # Build a map: user_id -> (User, Score)
        for user_id, choice in answers.items():
            # skip late-tamper safety (not strictly needed, but fine)
            if choice is None:
                continue
            # load user & weekly score row
            u = s.execute(select(User).where(User.tg_id == user_id)).scalar_one_or_none()
            if not u:
                continue
            sc = s.execute(select(Score).where(Score.user_id == u.id, Score.week_key == week_key())).scalar_one_or_none()
            if not sc:
                # if someone answered without /join, auto-create score
                sc = Score(user_id=u.id, week_key=week_key())
                s.add(sc)
                s.commit()

            if choice == correct:
                # award flat +10 (group mode); you can add streak logic if you like
                sc.points += 10
                sc.correct += 1
                s.commit()
                awarded.append(u)

    # Build a summary message
    total = len(answers)
    correct_count = sum(1 for c in answers.values() if c == correct)
    lines = [
        f"⏰ Time! Correct answer: *{correct}*",
        f"Answered: {total} • Correct: {correct_count}",
    ]
    if awarded:
        names = ", ".join([f"@{u.username}" if u.username else str(u.tg_id) for u in awarded[:12]])
        more = "" if len(awarded) <= 12 else f" +{len(awarded)-12} more"
        lines.append(f"✅ Points awarded to: {names}{more}")
    else:
        lines.append("No correct answers this round.")

    # send summary
    # (we don't have Bot instance here; we can reply in chat via dp.bot in newer aiogram, but simpler:
    # store a message object when asking. Alternatively, send via Bot API with chat_id.)
    try:
        # We need a Bot instance; easiest: import and create a temp Bot with the token (lightweight)
        from aiogram import Bot
        bot = Bot(settings.bot_token)
        await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    except Exception:
        pass

    # clear round
    CURRENT_ROUND.pop(chat_id, None)

async def cmd_answer(msg: Message):
    parts = (msg.text or "").split()
    if len(parts) != 2 or parts[1].upper() not in ("A","B","C","D"):
        return await msg.answer("Usage: /answer <A|B|C|D>")

    choice = parts[1].upper()
    st = CURRENT_ROUND.get(msg.chat.id)
    if not st:
        return await msg.answer("No active question. Use /quiz to start.")

    if time.time() > st["deadline"]:
        return await msg.answer("Too late—time is up. Wait for the next question.")

    # Create/refresh user, but pull out the primitive id before the session closes
    with SessionLocal() as s:
        user = get_or_create_user(s, msg)
        tg_id = int(user.tg_id)  # <- capture primitive

    # Only first answer counts
    if tg_id in st["answers"]:
        return await msg.answer("You already locked in an answer for this question.")

    st["answers"][tg_id] = (choice, time.time())
    await msg.answer("✅ Answer locked in. Wait for the reveal!")

async def cmd_leaderboard(msg: Message):
    with SessionLocal() as s:
        wk = week_key()
        rows = s.execute(
            select(Score, User).join(User, User.id==Score.user_id)
            .where(Score.week_key==wk).order_by(desc(Score.points)).limit(15)
        ).all()
        if not rows:
            return await msg.answer("No scores yet this week. /join and /quiz to play!")
        lines = [f"*Leaderboard {wk}*"]
        for i, (sc, u) in enumerate(rows, start=1):
            uname = f"@{u.username}" if u.username else str(u.tg_id)
            lines.append(f"{i}. {uname}: {sc.points} pts ({sc.correct}✓/{sc.wrong}✗)")
    await msg.answer("\n".join(lines), parse_mode="Markdown")

async def cmd_myscore(msg: Message):
    with SessionLocal() as s:
        user = get_or_create_user(s, msg)
        sc = s.execute(select(Score).where(Score.user_id==user.id, Score.week_key==week_key())).scalar_one_or_none()
        if not sc:
            return await msg.answer("No score yet. Use /join and /quiz to play.")
        await msg.answer(f"Your score this week: {sc.points} pts • {sc.correct}✓/{sc.wrong}✗ • streak {sc.streak}")

def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids

async def cmd_admin(msg: Message):
    if not _is_admin(msg.from_user.id):
        return await msg.answer("Admins only.")
    parts = (msg.text or "").split()
    if len(parts) == 1:
        return await msg.answer("Usage: /admin <status|endweek|payout|reset>")
    sub = parts[1].lower()
    if sub == "status":
        await msg.answer(f"OK. week={week_key()} dry_run={settings.payouts_dry_run} admins={settings.admin_ids}")
    elif sub == "endweek":
        await _admin_endweek(msg)
    elif sub == "payout":
        await _admin_payout(msg)
    elif sub == "reset":
        await _admin_reset(msg)
    else:
        await msg.answer("Unknown admin subcommand.")

async def _admin_endweek(msg: Message):
    from .scheduler import export_weekly_csv
    wk = week_key()
    with SessionLocal() as s:
        path = export_weekly_csv(s, wk)
    await msg.answer(f"Exported weekly CSV for {wk}: {path}")

async def _admin_payout(msg: Message):
    # Compute proportional payouts among top N
    N = settings.winners_count
    wk = week_key()
    with SessionLocal() as s:
        q = s.execute(
            select(Score, User).join(User, User.id==Score.user_id)
            .where(Score.week_key==wk).order_by(desc(Score.points)).limit(N)
        ).all()
        if not q:
            return await msg.answer("No scores to pay out.")
        total_pts = sum(sc.points for sc, _ in q)
        if total_pts == 0:
            return await msg.answer("Top players have 0 points; nothing to pay.")
        # For this template, we won't compute token pool. Adjust as needed.
        # Example: 1000_000_000 lamports (decimals for your SPL) distributed proportionally.
        pool = 1_000_000  # placeholder smallest units (change to your SPL decimals)
        lines = [f"Payouts for {wk} (pool={pool} units, dry_run={settings.payouts_dry_run}):"]
        pc = PayoutClient(settings.rpc_endpoint, settings.rpc_commitment)
        for sc, u in q:
            share = int(pool * (sc.points / total_pts))
            w = s.execute(select(Wallet).where(Wallet.user_id==u.id)).scalar_one_or_none()
            addr = w.address if w else None
            if not addr:
                lines.append(f"- @{u.username or u.tg_id}: NO WALLET ON FILE -> skipped")
                continue
            sig = pc.transfer_spl(
                mint=settings.strip_mint or "MINT_PLACEHOLDER",
                treasury_key=settings.treasury_private_key or "KEY_PLACEHOLDER",
                to_wallet=addr,
                amount=share,
                dry_run=settings.payouts_dry_run
            )
            lines.append(f"- @{u.username or u.tg_id}: {share} -> {sig}")
    await msg.answer("\n".join(lines))

async def _admin_reset(msg: Message):
    wk = week_key()
    # In a real reset, you might snapshot then delete; here we soft reset by rolling to new week (no-op).
    await msg.answer(f"Reset signal acknowledged for {wk}. To truly clear, rotate week or implement archival delete.")

async def main():
    ensure_db()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    # attach admin ids on bot object for scheduler notices
    setattr(bot, "admin_ids", settings.admin_ids)

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_rules, Command("rules"))
    dp.message.register(cmd_join, Command("join"))
    dp.message.register(cmd_quiz, Command("quiz"))
    dp.message.register(cmd_answer, Command("answer"))
    dp.message.register(cmd_leaderboard, Command("leaderboard"))
    dp.message.register(cmd_myscore, Command("myscore"))
    dp.message.register(cmd_wallet, Command("wallet"))
    dp.message.register(cmd_admin, Command("admin"))

    # fire up weekly scheduler
    schedule_jobs(bot)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
