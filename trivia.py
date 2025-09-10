import httpx, random, html, json, os
from typing import Literal

Choice = Literal['A','B','C','D']

async def fetch_music_questions(n: int = 5):
    # Try local JSON first
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "questions.json")
    if os.path.exists(local):
        try:
            with open(local, "r", encoding="utf-8") as f:
                items = json.load(f)
            return [_normalize_local(i) for i in random.sample(items, k=min(n, len(items)))]
        except Exception:
            pass

    # Fallback to OpenTDB: Category 12 = Music, type=multiple
    url = f"https://opentdb.com/api.php?amount={n}&category=12&type=multiple"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    questions = []
    for item in data.get("results", []):
        prompt = html.unescape(item["question"])
        correct = html.unescape(item["correct_answer"])
        incorrect = [html.unescape(x) for x in item["incorrect_answers"]]
        opts = incorrect + [correct]
        random.shuffle(opts)
        mapping = { 'A': opts[0], 'B': opts[1], 'C': opts[2], 'D': opts[3] }
        correct_opt = [k for k,v in mapping.items() if v == correct][0]
        questions.append({
            "category": "Music",
            "prompt": prompt,
            "options": mapping,
            "correct_opt": correct_opt
        })
    return questions

def _normalize_local(item: dict):
    mapping = {'A': item['opt_a'], 'B': item['opt_b'], 'C': item['opt_c'], 'D': item['opt_d']}
    return {
        "category": item.get("category", "Music"),
        "prompt": item["prompt"],
        "options": mapping,
        "correct_opt": item["correct_opt"].upper()
    }
