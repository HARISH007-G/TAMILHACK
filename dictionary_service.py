"""
MARAPOLI (மரபொலி) — Tamil Memory Dictionary Service (தமிழ்ச்சொல் நினைவகம்)
Powered by NVIDIA Hosted LLM API

Extracts culturally, historically, and regionally significant Tamil vocabulary,
traditional medicinal terms, agricultural terms, and dialect expressions from
oral history transcripts.
"""

import os
import re
import json
import time
import requests

# ---------------------------------------------------------------------------
# 1. Environment Loading (.env)
# ---------------------------------------------------------------------------
def _load_env():
    """Load environment variables from .env if present."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
            return
    except ImportError:
        pass

    # Simple fallback reader
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env()

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.2-11b-vision-instruct"
DEFAULT_TIMEOUT_SECONDS = 60


def get_nvidia_config():
    """Retrieve runtime NVIDIA API configuration from environment variables."""
    _load_env()
    api_key = os.environ.get('NVIDIA_API_KEY', '').strip()
    model = os.environ.get('NVIDIA_MODEL', '').strip() or DEFAULT_NVIDIA_MODEL
    base_url = os.environ.get('NVIDIA_API_BASE_URL', '').strip() or DEFAULT_NVIDIA_BASE_URL
    timeout = int(os.environ.get('NVIDIA_TIMEOUT', DEFAULT_TIMEOUT_SECONDS))

    # Strip trailing slashes from base_url
    if base_url.endswith('/'):
        base_url = base_url[:-1]

    return {
        'api_key': api_key,
        'model': model,
        'base_url': base_url,
        'timeout': timeout
    }


def is_nvidia_configured():
    """Check if NVIDIA API credentials are configured."""
    cfg = get_nvidia_config()
    return bool(cfg['api_key'])


# ---------------------------------------------------------------------------
# 2. Robust JSON Extraction from Model Response
# ---------------------------------------------------------------------------
def extract_json_from_model_output(raw_text):
    """
    Safely extract a JSON array or object from diverse model output shapes:
    - Markdown ```json ... ``` blocks
    - Raw JSON arrays [ ... ]
    - Wrapped JSON objects { "entries": [ ... ] } or { "words": [ ... ] }
    - Text with conversational preambles/postscripts
    """
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.strip()

    # 1. Check for markdown code blocks
    if '```json' in text:
        try:
            block = text.split('```json', 1)[1].split('```', 1)[0].strip()
            data = json.loads(block)
            return _normalize_parsed_data(data)
        except Exception:
            pass

    if '```' in text:
        try:
            block = text.split('```', 1)[1].split('```', 1)[0].strip()
            data = json.loads(block)
            return _normalize_parsed_data(data)
        except Exception:
            pass

    # 2. Try direct JSON parse
    try:
        data = json.loads(text)
        return _normalize_parsed_data(data)
    except Exception:
        pass

    # 3. Regex search for outermost JSON array [ ... ]
    array_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if array_match:
        try:
            data = json.loads(array_match.group(0))
            return _normalize_parsed_data(data)
        except Exception:
            pass

    # 4. Regex search for outermost JSON object { ... }
    obj_match = re.search(r'\{\s*".*"\s*:.*\}', text, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            return _normalize_parsed_data(data)
        except Exception:
            pass

    return []


def _normalize_parsed_data(data):
    """Ensure parsed JSON is returned as a list of dictionary entries."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ('entries', 'words', 'vocabulary', 'dictionary', 'items', 'terms'):
            if key in data and isinstance(data[key], list):
                return [item for item in data[key] if isinstance(item, dict)]
        # If dict itself represents a single entry
        if 'word' in data:
            return [data]
    return []


# ---------------------------------------------------------------------------
# 3. Entry Sanitization & Provenance Verification
# ---------------------------------------------------------------------------
def sanitize_dictionary_entry(raw_entry, transcript=""):
    """
    Clean, validate, and verify a candidate dictionary entry.
    - Preserves Tamil script.
    - Verifies presence in the transcript.
    - Does NOT fabricate timestamps when missing.
    - Flags ambiguous entries for review.
    """
    word = str(raw_entry.get('word', '')).strip()
    if not word:
        return None

    # Strip surrounding quotation marks or brackets from the word
    word = re.sub(r'^[\"\'\(\[\{]+|[\"\'\)\]\}]+$', '', word).strip()
    if len(word) < 2:
        return None

    meaning_ta = str(raw_entry.get('meaning_ta', '')).strip()
    meaning_en = str(raw_entry.get('meaning_en', '')).strip()

    if not meaning_ta and not meaning_en:
        return None

    if not meaning_ta:
        meaning_ta = f"{word} என்பதன் விளக்கம்."
    if not meaning_en:
        meaning_en = f"Explanation of {word}."

    contextual_ta = str(raw_entry.get('contextual_meaning_ta', '')).strip()
    example_sentence = str(raw_entry.get('example_sentence', '')).strip()
    category = str(raw_entry.get('category', 'பாரம்பரிய அறிவு')).strip() or 'பாரம்பரிய அறிவு'

    # Extract or verify source excerpt from transcript
    source_excerpt = str(raw_entry.get('source_excerpt', '')).strip()
    if not source_excerpt and transcript:
        # Locate the word in the transcript and extract surrounding sentence
        sentences = re.split(r'[\.\!\?\n]+', transcript)
        for s in sentences:
            if word in s:
                source_excerpt = s.strip()
                break

    # Confidence calculation: default 0.85, lowered if uncertain or absent from transcript
    confidence = 0.85
    review_status = 'pending_review'

    if transcript and word not in transcript:
        # Word appears slightly inflected or model suggested stem; lower confidence
        confidence = 0.60
        review_status = 'pending_review'

    # Check for timestamps (ONLY preserve if provided by transcription; never invent!)
    start_sec = raw_entry.get('start_seconds')
    end_sec = raw_entry.get('end_seconds')
    try:
        start_sec = float(start_sec) if start_sec is not None and str(start_sec).strip() != '' else None
        end_sec = float(end_sec) if end_sec is not None and str(end_sec).strip() != '' else None
    except (ValueError, TypeError):
        start_sec = None
        end_sec = None

    return {
        'word': word,
        'meaning_ta': meaning_ta,
        'meaning_en': meaning_en,
        'contextual_meaning_ta': contextual_ta,
        'example_sentence': example_sentence,
        'category': category,
        'source_excerpt': source_excerpt,
        'start_seconds': start_sec,
        'end_seconds': end_sec,
        'confidence': confidence,
        'review_status': review_status
    }


# ---------------------------------------------------------------------------
# 4. NVIDIA API Call & Generation
# ---------------------------------------------------------------------------
def generate_dictionary_from_transcript(transcript, story_metadata=None):
    """
    Calls NVIDIA hosted LLM API to extract rich Tamil Memory Dictionary entries.
    Returns:
    {
        "success": bool,
        "entries": list[dict],
        "count": int,
        "model": str,
        "error": str or None
    }
    """
    if not transcript or not transcript.strip():
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": "",
            "error": "உரை எதுவும் வழங்கப்படவில்லை. அகராதி உருவாக்கத் தமிழ் உரை தேவை."
        }

    cfg = get_nvidia_config()
    if not cfg['api_key']:
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": "NVIDIA API Key கட்டமைக்கப்படவில்லை. தயவுசெய்து .env கோப்பில் NVIDIA_API_KEY வழங்கவும்."
        }

    # Prepare prompt
    clean_transcript = transcript.strip()
    if len(clean_transcript) > 12000:
        clean_transcript = clean_transcript[:12000] + "..."

    topic_hint = ""
    region_hint = ""
    if story_metadata:
        if story_metadata.get('topic'):
            topic_hint = f"தலைப்பு / வகை: {story_metadata['topic']}"
        if story_metadata.get('region'):
            region_hint = f"வட்டாரம் / ஊர்: {story_metadata['region']}"

    system_instruction = (
        "You are an expert Tamil Lexicographer, Dialectologist, and Cultural Anthropologist "
        "working for the Tamil Oral Heritage Archive (மொழி நினைவு • தமிழ்ச் சொல் நினைவகம்).\n"
        "Your task is to analyze authentic spoken Tamil transcripts and extract culturally, historically, "
        "or regionally significant Tamil words, expressions, and phrases.\n\n"
        "PRIORITIZE:\n"
        "- Traditional agriculture & farming tools (விவசாயம், நாட்டுப்புறக் கருவிகள்)\n"
        "- Siddha medicine, herbs, and healing practices (சித்த மருத்துவம், பாரம்பரிய மூலிகைகள்)\n"
        "- Food heritage & rural culinary items (நாட்டுப்புற பாரம்பரிய உணவு முறைகள்)\n"
        "- Regional dialects, idioms, and oral expressions (வட்டார வழக்கு, மரபுச் சொற்கள்)\n"
        "- Ancient rituals, customs, folk arts, and festivals (கிராமியக் கலைகள், சடங்குகள், விழாக்கள்)\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. DO NOT extract ordinary common vocabulary or grammatical words (e.g., நான், அவன், வந்தது, மற்றும், இல்லை, என்று, போட்டு, விட்டு).\n"
        "2. Do NOT fabricate historical facts, etymologies, or timestamps.\n"
        "3. Preserve the original Tamil script faithfully.\n"
        "4. Return ONLY a valid JSON array of objects with the exact schema:\n"
        "   [\n"
        "     {\n"
        "       \"word\": \"தமிழ்ச் சொல்\",\n"
        "       \"meaning_ta\": \"தெளிவான தமிழ் விளக்கம்\",\n"
        "       \"meaning_en\": \"Clear English explanation\",\n"
        "       \"contextual_meaning_ta\": \"இக்கதையில் இதன் சூழல்சார்ந்த பயன்\",\n"
        "       \"example_sentence\": \"எடுத்துக்காட்டு வாக்கியம்\",\n"
        "       \"category\": \"பிரிவு (எ.கா: சித்த மருத்துவம், விவசாயம், வட்டார வழக்கு, நாட்டுப்புறக் கலைகள்)\",\n"
        "       \"source_excerpt\": \"உரையில் இச்சொல் இடம்பெற்ற வாக்கியம்\"\n"
        "     }\n"
        "   ]\n"
        "Do NOT enclose in markdown or preamble. Output raw JSON array."
    )

    user_content = f"Tamil Oral History Transcript:\n\"\"\"{clean_transcript}\"\"\"\n"
    if topic_hint or region_hint:
        user_content += f"Story Context: {topic_hint} | {region_hint}\n"
    user_content += "\nExtract 2 to 4 significant cultural/dialect terms and return strictly as a JSON array:"

    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_content}
        ],
        'temperature': 0.1,
        'max_tokens': 450
    }

    endpoint_url = f"{cfg['base_url']}/chat/completions"

    # Make request with timeout and 1 transient retry
    response = None
    last_error = None
    for attempt in range(2):
        try:
            response = requests.post(
                endpoint_url,
                headers=headers,
                json=payload,
                timeout=cfg['timeout']
            )
            # Break if success or non-retryable 4xx
            if response.status_code == 200:
                break
            elif response.status_code in (401, 403, 404):
                # Credentials/model errors are non-retryable
                break
            elif response.status_code == 429:
                # Rate limit; wait 2s and retry
                time.sleep(2)
            elif response.status_code >= 500:
                # Server error; wait 1.5s and retry
                time.sleep(1.5)
        except requests.exceptions.Timeout:
            last_error = "NVIDIA API கோரிக்கைக்கான காலம் முடிந்தது (Timeout). தயவுசெய்து சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்."
            if attempt == 0:
                time.sleep(1)
        except requests.exceptions.ConnectionError:
            last_error = "NVIDIA சேவையகத்துடன் தொடர்பு கொள்ள முடியவில்லை (Network Connection Error)."
            if attempt == 0:
                time.sleep(1)
        except Exception as e:
            last_error = f"அகராதி உருவாக்கத்தில் எதிர்பாராத பிழை: {str(e)}"
            break

    if response is None:
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": last_error or "NVIDIA API தொடர்பு கொள்ள முடியவில்லை."
        }

    # Handle HTTP error statuses
    if response.status_code == 401:
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": "NVIDIA API அங்கீகாரப் பிழை (401 Unauthorized). வழங்கப்பட்ட API சாவி தவறானது அல்லது காலாவதியானது."
        }

    if response.status_code == 429:
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": "NVIDIA API விகித வரம்பு எட்டப்பட்டது (429 Rate Limit Exceeded). சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்."
        }

    if response.status_code != 200:
        err_detail = response.text[:200]
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": f"NVIDIA API பிழை (Status {response.status_code}): {err_detail}"
        }

    # Parse response
    try:
        resp_json = response.json()
        raw_text = resp_json['choices'][0]['message']['content']
    except Exception as e:
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": f"NVIDIA API பதிலைப் பாகுபடுத்துவதில் பிழை: {str(e)}"
        }

    # Extract JSON entries safely
    raw_entries = extract_json_from_model_output(raw_text)
    if not raw_entries:
        # Fallback: check if the text has bullet points or lines
        return {
            "success": False,
            "entries": [],
            "count": 0,
            "model": cfg['model'],
            "error": "NVIDIA மாதிரி செல்லுபடியாகும் அகராதித் தரவை வழங்கவில்லை (Invalid Model Response Shape)."
        }

    # Sanitize and validate every entry
    sanitized_entries = []
    seen_words = set()
    for item in raw_entries:
        cleaned = sanitize_dictionary_entry(item, transcript)
        if cleaned:
            w = cleaned['word'].strip().lower()
            if w not in seen_words:
                seen_words.add(w)
                sanitized_entries.append(cleaned)

    return {
        "success": True,
        "entries": sanitized_entries,
        "count": len(sanitized_entries),
        "model": cfg['model'],
        "error": None
    }


def lookup_tamil_word(word, context=''):
    """
    Directly query the NVIDIA API for the detailed cultural and linguistic meaning of a single Tamil word.
    """
    w = str(word).strip()
    if not w:
        return {"success": False, "error": "தமிழ்ச் சொல் தேவை (Tamil word is required)."}

    cfg = get_nvidia_config()
    if not cfg['api_key']:
        return {"success": False, "error": "NVIDIA API Key கட்டமைக்கப்படவில்லை."}

    user_msg = f"தமிழ்ச் சொல்: \"{w}\"\n"
    if context:
        user_msg += f"பயன்படுத்தப்பட்ட சூழல் / வாக்கியம்: \"{context}\"\n"
    user_msg += (
        "இச்சொல்லின் தமிழ்ப் பொருள், ஆங்கிலப் பொருள், பயன்பாட்டு சூழல், வகை ஆகியவற்றை ஆராய்ந்து "
        "கீழ்க்கண்ட JSON வடிவில் மட்டும் தரவும்:\n"
        "[\n"
        "  {\n"
        f"    \"word\": \"{w}\",\n"
        "    \"meaning_ta\": \"தெளிவான தமிழ் விளக்கம்\",\n"
        "    \"meaning_en\": \"English meaning\",\n"
        "    \"contextual_meaning_ta\": \"இச்சூழலில் பொருள்\",\n"
        "    \"category\": \"பிரிவு (சித்த மருத்துவம் / விவசாயம் / வட்டார வழக்கு / பண்பாடு)\",\n"
        "    \"example_sentence\": \"எடுத்துக்காட்டு வாக்கியம்\"\n"
        "  }\n"
        "]"
    )

    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': 'You are an authoritative Tamil linguist and cultural lexicographer. Return valid JSON only.'},
            {'role': 'user', 'content': user_msg}
        ],
        'temperature': 0.1,
        'max_tokens': 600
    }

    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=cfg['timeout']
        )
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            parsed = extract_json_from_model_output(content)
            if parsed:
                san = sanitize_dictionary_entry(parsed[0], context)
                return {"success": True, "entry": san}
            return {"success": False, "error": "பொருளைப் பாகுபடுத்த முடியவில்லை."}
        else:
            return {"success": False, "error": f"NVIDIA API பிழை (Status {resp.status_code})"}
    except Exception as e:
        return {"success": False, "error": f"API தொடர்புப் பிழை: {str(e)}"}

