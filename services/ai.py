import re

import httpx
from config import Config

AVAILABLE_MODELS = [
   ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 3 120B 🆓"),
    ("google/gemini-3.5-flash", "gemini 3.5"),
   ("openai/gpt-oss-120b:free", "GPT"),
   ("z-ai/glm-4.5-air:free", "Z-ai"),
]


def _strip_reasoning(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


async def search_web(query: str) -> str:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            data = r.json()
            abstract = data.get("AbstractText", "")
            related = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3]]
            parts = [p for p in [abstract] + related if p]
            return "\n".join(parts) if parts else ""
    except Exception:
        return ""


async def ask_ai(
    messages: list[dict],
    system_prompt: str,
    model: str,
    status_message: str = "",
    status_active: bool = False,
    user_message: str = "",
) -> str:
    search_result = ""
    needs_search = any(
        kw in user_message.lower()
        for kw in [
            "найди", "поищи", "что такое", "расскажи про", "статья", "инфо о",
            "wikipedia", "вики", "объясни", "поиск", "search", "find", "tell me about",
        ]
    )
    if needs_search and user_message:
        search_result = await search_web(user_message)

    status_block = ""
    if status_active and status_message:
        status_block = f"\n[СТАТУС ВЛАДЕЛЬЦА]: {status_message}"

    search_block = ""
    if search_result:
        search_block = f"\n\n[ДАННЫЕ ИЗ ИНТЕРНЕТА для ответа]:\n{search_result}"

    full_system = system_prompt + status_block + search_block

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": full_system}] + messages,
        "max_tokens": 900,
        "temperature": 0.85,
    }

    headers = {
        "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/aura456bot",
        "X-Title": "TG Business AutoResponder",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{Config.OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        data = r.json()

    try:
        raw = data["choices"][0]["message"]["content"]
        return _strip_reasoning(raw)
    except (KeyError, IndexError):
        error_info = data.get("error", {}).get("message", str(data))
        raise RuntimeError(f"OpenRouter error: {error_info}")


def build_system_prompt(settings: dict) -> str:
    bot_name = settings.get("bot_name", "Авто")
    custom_prompt = settings.get("bot_prompt", "").strip()

    base = f"""Ты — {bot_name}, автоответчик в Telegram вместо реального человека (владельца).
Владелец сейчас недоступен, ты отвечаешь за него.

ПРАВИЛА:
1. Не притворяйся самим владельцем — ты его автоответчик с именем «{bot_name}».
2. Не говори что ты ИИ, не используй фразы «как языковая модель», «я не могу», «я ИИ».
3. Отвечай живо, по-человечески, без канцеляризма.
4. Конфиденциальную информацию о владельце — не раскрывай никогда.
5. Если у тебя есть данные из интернета — используй их для развёрнутого ответа.
6. Если тебя спросят куда пошёл владелец — отвечай строго по статусу, если он есть.
7. Отвечай коротко, если вопрос простой. Развёрнуто — если просят объяснить или найти что-то.
"""

    if custom_prompt:
        base += f"\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ОТ ВЛАДЕЛЬЦА:\n{custom_prompt}"

    return base
