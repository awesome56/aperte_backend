import json
import os
import re
import urllib.request

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '').strip()
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4-flash').strip()
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'

_SYSTEM_PROMPT = """You interpret natural-language Nigerian property-search queries into structured filters.

Rules:
- Fix typos and slang in the query (e.g. "chat" -> "flat" or "house", "2 bedroom" -> bedrooms=2, "bq" -> boys quarter, "self-con" -> self-contained).
- Prices mentioned are in Naira (₦, NGN). "m", "M" means million, "k" means thousand (e.g. "5m" = 5,000,000, "800k" = 800,000).
- "for rent" -> purpose=rent, "for sale" -> purpose=sale. "shortlet"/"short let" -> category=shortlet. "hotel" -> category=hotel. "venue"/"event centre"/"hall" -> category=hall or event_center. "land"/"plot" -> category=land.
- "2 bedroom" (or "2bed", "2 b/r", "2br") means bedrooms=2. "flat", "apartment", "house", "duplex", "bungalow", "shop", "office", "warehouse", "storey building" are property_type clues.
- Known Ibadan areas go in location (Bodija, Jericho, Agodi, Akobo, Ibadan North, Ring Road, Dugbe, Mokola, Alalubosa, Samonda, Ikolaba, Onireke, Eleyele, U.I., Challenge, Ologuneru, Akanran, Oluyole, Idi-Ape, Apata, Moniya, Akinyele, Orita-Mefa, Basorun, Ijokodo, Orogun, Old Bodija, New Bodija, Agbowo, Elebu, Kolapo Ishola...). Other cities (Lagos, Abuja, Port Harcourt...) go in city.
- Output a single valid json object. Do not include markdown fences, do not include any commentary. The json format:{"keywords": ["phrase", "or", "word"], "category": "property|land|hotel|hall|event_center|shortlet|other" or null, "purpose": "rent|sale" or null, "property_type": "Flat / Apartment|House|Duplex|Bungalow|Land|Shop|Office|Warehouse|Commercial Property|Shortlet|Hotel|Event Centre|Serviced Apartment" or null, "bedrooms": int or null, "bathrooms": int or null, "min_price": int or null, "max_price": int or null, "city": "Ibadan" or null, "location": "Bodija" or null, "suggested_query": "a cleaned-up search phrase"}
- "keywords" must contain the meaningful noun phrases ONLY (no stop words like "show", "me", "i", "want", "looking", "for", "a", "in", "the").
- If the query is a simple keyword like "Bodija", keywords=["Bodija"], location="Bodija".
"""


def ai_interpret(query):
    """Return structured filters for a natural-language query, or None if AI is unavailable."""
    if not DEEPSEEK_API_KEY:
        return None
    payload = {
        'model': DEEPSEEK_MODEL,
        'messages': [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': query},
        ],
        'temperature': 0,
        'max_tokens': 1024,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(payload).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(DEEPSEEK_API_KEY),
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        msg = body['choices'][0]['message']
        content = (msg.get('content') or msg.get('reasoning_content') or '').strip()
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception:
        return None
