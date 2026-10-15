"""
MARAPOLI (மரபொலி) — Tamil Oral Story AI Summarization Service
Powered by NVIDIA Hosted LLM API

Generates concise, culturally faithful summaries of Tamil oral transcripts
in both Tamil and English without inventing facts.
"""

import os
import json
import re
import time
import requests
import dictionary_service

DEFAULT_TIMEOUT_SECONDS = 75


def generate_story_summary(transcript):
    """
    Generate concise Tamil and English summaries from a Tamil transcript
    using NVIDIA's hosted LLM API.
    """
    clean_transcript = (transcript or '').strip()
    if not clean_transcript:
        return {
            "success": False,
            "error": "சுருக்கம் உருவாக்கத் தமிழ் உரை தேவை. தயவுசெய்து முதலில் ஒலியைப் பதிவு செய்யவும் (Tamil transcript is required)."
        }

    cfg = dictionary_service.get_nvidia_config()
    if not cfg['api_key']:
        return {
            "success": False,
            "error": "NVIDIA API Key கட்டமைக்கப்படவில்லை. தயவுசெய்து .env கோப்பில் NVIDIA_API_KEY வழங்கவும்."
        }

    # Limit transcript length to keep prompt within bounds
    truncated_transcript = clean_transcript
    if len(truncated_transcript) > 8000:
        truncated_transcript = truncated_transcript[:8000] + "..."

    prompt = (
        "You are an expert cultural researcher and summarizer for the Tamil Oral Heritage Archive (மொழி நினைவு).\n"
        "Your task is to accurately summarize the following spoken Tamil transcript.\n\n"
        f"Transcript:\n\"\"\"{truncated_transcript}\"\"\"\n\n"
        "INSTRUCTIONS:\n"
        "1. Provide a concise, meaningful summary in clear Tamil (2-3 sentences).\n"
        "2. Provide an accurate, faithful summary in English (2-3 sentences).\n"
        "3. Preserve the original meaning, people, places, traditional words, and cultural knowledge.\n"
        "4. Do NOT invent facts or events absent from the transcript.\n"
        "5. Output strictly a JSON object formatted as:\n"
        "{\n"
        '  "summary_ta": "<Tamil summary>",\n'
        '  "summary_en": "<English summary>"\n'
        "}\n\n"
        "JSON:"
    )

    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,
        'max_tokens': 400
    }

    endpoint_url = f"{cfg['base_url']}/chat/completions"
    timeout = int(os.environ.get('NVIDIA_SUMMARY_TIMEOUT', DEFAULT_TIMEOUT_SECONDS))

    response = None
    last_error = None
    for attempt in range(2):
        try:
            response = requests.post(endpoint_url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                break
            elif response.status_code in (401, 403, 404):
                break
            elif response.status_code == 429:
                time.sleep(2)
            elif response.status_code >= 500:
                time.sleep(1.5)
        except requests.exceptions.Timeout:
            last_error = "NVIDIA சேவையகத்தின் பதில் காலம் முடிந்தது (Timeout). தயவுசெய்து மீண்டும் முயற்சிக்கவும்."
            break
        except requests.exceptions.ConnectionError:
            last_error = "NVIDIA சேவையகத்துடன் தொடர்பு கொள்ள முடியவில்லை (Network Connection Error)."
            if attempt == 0:
                time.sleep(1)
        except Exception as e:
            last_error = f"சுருக்கம் உருவாக்கத்தில் பிழை: {str(e)}"
            break

    if response is None:
        return {
            "success": False,
            "error": last_error or "NVIDIA API-ஐ தொடர்பு கொள்ள முடியவில்லை."
        }

    if response.status_code == 401:
        return {
            "success": False,
            "error": "NVIDIA API அங்கீகாரப் பிழை (401 Unauthorized). API சாவி தவறானது அல்லது காலாவதியானது."
        }

    if response.status_code == 429:
        return {
            "success": False,
            "error": "NVIDIA API விகித வரம்பு எட்டப்பட்டது (429 Rate Limit Exceeded). சிறிது நேரம் கழித்து முயற்சிக்கவும்."
        }

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"NVIDIA API பிழை (Status {response.status_code}): {response.text[:200]}"
        }

    try:
        raw_text = response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return {
            "success": False,
            "error": f"NVIDIA பதிலை வாசிப்பதில் பிழை: {str(e)}"
        }

    parsed = _parse_summary_response(raw_text)
    return {
        "success": True,
        "summary_ta": parsed["summary_ta"],
        "summary_en": parsed["summary_en"],
        "key_points": parsed.get("key_points", []),
        "model": cfg['model']
    }


def _parse_summary_response(raw_text):
    """
    Parses LLM output into Tamil summary, English summary, and key points.
    Handles JSON blocks, truncated JSON, plain text with language labels,
    and strips any raw JSON formatting artifacts.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {
            "summary_ta": "",
            "summary_en": "",
            "key_points": []
        }

    summary_ta = ""
    summary_en = ""
    key_points = []

    # 1. Attempt standard JSON parsing
    json_candidate = raw_text.strip()
    if '```json' in json_candidate:
        json_candidate = json_candidate.split('```json', 1)[1].split('```', 1)[0].strip()
    elif '```' in json_candidate:
        json_candidate = json_candidate.split('```', 1)[1].split('```', 1)[0].strip()
    else:
        obj_m = re.search(r'\{\s*".*"\s*:.*\}', json_candidate, re.DOTALL)
        if obj_m:
            json_candidate = obj_m.group(0)

    try:
        data = json.loads(json_candidate)
        if isinstance(data, dict):
            summary_ta = str(data.get('summary_ta', '')).strip()
            summary_en = str(data.get('summary_en', '')).strip()
            raw_kp = data.get('key_points', [])
            if isinstance(raw_kp, list):
                key_points = [str(p).strip() for p in raw_kp if str(p).strip()]
    except Exception:
        pass

    # 2. Resilient regex extraction from JSON fields
    # Handles truncated JSON (missing closing quotes, brackets, or braces)
    if not summary_ta or not summary_en:
        ta_m = re.search(r'"summary_ta"\s*:\s*"((?:[^"\\]|\\.)*?)(?:"\s*,|\s*"\w+"\s*:|"\s*\}|$)', raw_text, re.DOTALL)
        if ta_m:
            summary_ta = ta_m.group(1).replace('\\"', '"').replace('\\n', '\n').strip()

        en_m = re.search(r'"summary_en"\s*:\s*"((?:[^"\\]|\\.)*?)(?:"\s*,|\s*"\w+"\s*:|"\s*\}|$)', raw_text, re.DOTALL)
        if en_m:
            summary_en = en_m.group(1).replace('\\"', '"').replace('\\n', '\n').strip()

        if not key_points and 'key_points' in raw_text:
            kp_section = raw_text.split('key_points', 1)[1]
            kp_matches = re.findall(r'"([^"\n\r]{3,100})"', kp_section)
            key_points = [p.strip() for p in kp_matches if not p.startswith('summary_') and p.strip()]

    # 3. Fallback heuristic: Parse labelled headers in free-form text
    if not summary_ta or not summary_en:
        ta_match = re.search(r'(?:தமிழ் சுருக்கம்|Tamil Summary|தமிழ்):\s*([^\n\r]+(?:\n(?!(?:English Summary|ஆங்கில விளக்கம்|English:))[^\n\r]+)*)', raw_text, re.IGNORECASE)
        if ta_match:
            summary_ta = ta_match.group(1).strip()

        en_match = re.search(r'(?:English Summary|ஆங்கில விளக்கம்|English):\s*([^\n\r]+(?:\n(?!(?:தமிழ் சுருக்கம்|Key Points|குறிப்புகள்))[^\n\r]+)*)', raw_text, re.IGNORECASE)
        if en_match:
            summary_en = en_match.group(1).strip()

    # 4. Helper to ensure NO raw JSON artifacts, keys, quotes, or braces ever leak to the UI
    def _sanitize_output_text(s):
        if not s:
            return ""
        s = re.sub(r'[{}\[\]]', '', s)
        s = re.sub(r'"(?:summary_ta|summary_en|key_points)"\s*:\s*', '', s)
        s = s.strip(' \t\n\r",')
        return s

    if not summary_ta and not summary_en:
        summary_ta = _sanitize_output_text(raw_text)
        summary_en = "English summary of oral heritage recording."
    else:
        summary_ta = _sanitize_output_text(summary_ta)
        summary_en = _sanitize_output_text(summary_en)

    return {
        "summary_ta": summary_ta,
        "summary_en": summary_en,
        "key_points": key_points
    }

