"""
MARAPOLI (மரபொலி) — Tamil Dialect DNA & Linguistic Analysis Service
(வட்டார மொழி அடையாளம்)
Powered by NVIDIA Hosted LLM API

Provides evidence-based linguistic analysis of Tamil oral transcripts:
- Identifies directly observed colloquial expressions, morphological patterns, and discourse particles.
- Extracts distinctive vocabulary with verbatim transcript context.
- Highlights potential regional dialect indicators with rigorous caveats and alternative explanations.
- Generates structured distribution metrics for the Dialect DNA visualization.
- Does NOT fabricate ungrounded probabilities or make definitive claims about a speaker's personal identity.
"""

import os
import re
import json
import time
import unicodedata
import requests
import dictionary_service

DEFAULT_TIMEOUT_SECONDS = 75

# Recognized Tamil dialect varieties for structured classification
SUPPORTED_REGIONS = [
    "Kongu Tamil",             # கொங்குத் தமிழ் (Coimbatore, Erode, Salem, Tiruppur)
    "Madurai Tamil",           # மதுரை / பாண்டித் தமிழ் (Madurai, Theni, Dindigul, Ramanathapuram)
    "Nellai Tamil",            # நெல்லை / தூத்துக்குடித் தமிழ் (Tirunelveli, Thoothukudi, Tenkasi)
    "Thanjavur Tamil",         # தஞ்சைத் தமிழ் (Thanjavur, Tiruvarur, Nagapattinam, Mayiladuthurai)
    "Chennai Colloquial Tamil",# சென்னை / வட ஆற்காடு பேச்சுத்தமிழ் (Chennai, Tiruvallur, Kanchipuram)
    "General Spoken Tamil",    # பொதுப் பேச்சுத்தமிழ் (Shared colloquial spoken register)
    "Formal / Literary Tamil", # பொதுத் தமிழ் / செந்தமிழ் (Standard or formal written/spoken register)
    "Insufficient Evidence"    # போதிய சான்றுகள் இல்லை (Ambiguous / inadequate sample)
]

# Standard categories for the Dialect DNA Feature Distribution Radar
LINGUISTIC_CATEGORIES = [
    {"key": "colloquial_lexicon", "label_ta": "பேச்சு வழக்குச் சொற்கள்", "label_en": "Colloquial Lexicon"},
    {"key": "morphological_markers", "label_ta": "உருபனியல் கூறுகள்", "label_en": "Morphological Markers"},
    {"key": "discourse_particles", "label_ta": "விளி & சொல் உரையாடல் கூறுகள்", "label_en": "Discourse Particles"},
    {"key": "regional_indicators", "label_ta": "வட்டாரத் தனித்துவச் சொற்கள்", "label_en": "Regional Lexical Indicators"},
    {"key": "syntactic_patterns", "label_ta": "தொடரியல் & வாக்கிய மரபு", "label_en": "Syntactic Patterns"}
]


def analyze_dialect(transcript):
    """
    Main entry point for Tamil Dialect DNA analysis.
    Validates transcript, checks minimum sample requirements, invokes the NVIDIA LLM,
    and returns a rigorously validated, evidence-linked linguistic profile.
    """
    if transcript is None:
        return {
            "success": False,
            "status": "empty_input",
            "error": "வட்டார மொழிப் பகுப்பாய்வு செய்யத் தமிழ் உரை தேவை (Tamil transcript is required)."
        }

    # Normalize unicode and whitespace
    clean_text = unicodedata.normalize('NFC', str(transcript)).strip()
    if not clean_text:
        return {
            "success": False,
            "status": "empty_input",
            "error": "வட்டார மொழிப் பகுப்பாய்வு செய்யத் தமிழ் உரை தேவை. தயவுசெய்து ஒலியைப் பதிவு செய்து உரையாக்கவும் (Tamil transcript is required)."
        }

    # Inspect length & word count
    words = [w for w in re.split(r'\s+', clean_text) if w.strip()]
    if len(clean_text) < 15 or len(words) < 3:
        return {
            "success": True,
            "status": "insufficient_evidence",
            "analysisType": "transcript_based_linguistic_analysis",
            "language": "Tamil",
            "overallAssessment": (
                "வழங்கப்பட்ட உரை மிகக் குறுகியதாக உள்ளது (குறைந்தபட்சம் 3-4 சொற்களுக்கு மேல் தேவை). "
                "நம்பகமான வட்டார வழக்கு அல்லது மொழியியல் அடையாளங்களைக் கண்டறிய நீண்ட உரைப் பகுதி பரிந்துரைக்கப்படுகிறது."
            ),
            "regionalIndicators": [],
            "linguisticFeatures": [],
            "distinctiveVocabulary": [],
            "radarMetrics": [
                {"category": cat["key"], "label_ta": cat["label_ta"], "label_en": cat["label_en"], "score": 10, "evidenceCount": 0}
                for cat in LINGUISTIC_CATEGORIES
            ],
            "limitations": [
                "உரையின் நீளம் மிகக் குறைவாக இருப்பதால் வட்டார வழக்குக் கூறுகளை உறுதிசெய்ய இயலாது.",
                "குறைந்தபட்சம் இரண்டு அல்லது மூன்று வாக்கியங்கள் கொண்ட உரை மட்டுமே போதுமான மொழியியல் சான்றுகளை வழங்கும்."
            ],
            "sampleStats": {
                "characterCount": len(clean_text),
                "wordCount": len(words)
            }
        }

    # Retrieve NVIDIA runtime configuration
    cfg = dictionary_service.get_nvidia_config()
    if not cfg['api_key']:
        return {
            "success": False,
            "status": "configuration_error",
            "error": "NVIDIA API Key கட்டமைக்கப்படவில்லை. தயவுசெய்து .env கோப்பில் NVIDIA_API_KEY வழங்கவும்."
        }

    # Truncate to reasonable bounds (max 8000 characters) to avoid prompt overflows
    truncated_transcript = clean_text[:8000] if len(clean_text) > 8000 else clean_text

    prompt = _build_dialect_analysis_prompt(truncated_transcript)

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
        'temperature': 0.1,  # Low temperature for deterministic, factual linguistic extraction
        'max_tokens': 1200
    }

    endpoint_url = f"{cfg['base_url']}/chat/completions"
    timeout = int(os.environ.get('NVIDIA_DIALECT_TIMEOUT', DEFAULT_TIMEOUT_SECONDS))

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
            last_error = f"வட்டார மொழிப் பகுப்பாய்வில் பிழை: {str(e)}"
            break

    if response is None:
        return {
            "success": False,
            "status": "network_error",
            "error": last_error or "NVIDIA API-ஐ தொடர்பு கொள்ள முடியவில்லை."
        }

    if response.status_code == 401:
        return {
            "success": False,
            "status": "auth_error",
            "error": "NVIDIA API அங்கீகாரப் பிழை (401 Unauthorized). API சாவி தவறானது அல்லது காலாவதியானது."
        }

    if response.status_code == 429:
        return {
            "success": False,
            "status": "rate_limit",
            "error": "NVIDIA API விகித வரம்பு எட்டப்பட்டது (429 Rate Limit Exceeded). சிறிது நேரம் கழித்து முயற்சிக்கவும்."
        }

    if response.status_code != 200:
        return {
            "success": False,
            "status": "api_error",
            "error": f"NVIDIA API பிழை (Status {response.status_code}): {response.text[:200]}"
        }

    try:
        raw_text = response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return {
            "success": False,
            "status": "parse_error",
            "error": f"NVIDIA பதிலை வாசிப்பதில் பிழை: {str(e)}"
        }

    # Validate and structure the output strictly
    analysis_result = _parse_and_validate_dialect_response(raw_text, clean_text)
    analysis_result["success"] = True
    analysis_result["model"] = cfg['model']
    analysis_result["sampleStats"] = {
        "characterCount": len(clean_text),
        "wordCount": len(words)
    }

    return analysis_result


def _build_dialect_analysis_prompt(transcript):
    """
    Constructs a dedicated computational linguistics prompt for Tamil dialect analysis.
    Demands exact verbatim quotes, forbids hallucination of speaker identity or ungrounded percentages,
    and emphasizes objective linguistic observation with alternative explanations.
    """
    return (
        "You are a distinguished Tamil computational linguist and dialectologist working for the "
        "MARAPOLI Tamil Oral Heritage Archive (மொழி நினைவு — வட்டார மொழி அடையாளம்).\n"
        "Your task is to conduct an objective, evidence-based linguistic analysis of the spoken Tamil transcript below.\n\n"
        f"Transcript:\n\"\"\"{transcript}\"\"\"\n\n"
        "LINGUISTIC PRINCIPLES & GUIDELINES:\n"
        "1. GROUND TRUTH: Base all observations strictly on the transcript text. Every observation MUST cite an exact verbatim phrase from the transcript.\n"
        "2. CAUTION & AMBIGUITY: Do NOT make definitive claims about a speaker's geographic origin, hometown, caste, religion, or personal identity. Spoken Tamil features often overlap across districts.\n"
        "3. REGIONAL VARIETIES: If colloquial markers suggest a regional variety (e.g., Kongu Tamil, Madurai Tamil, Nellai/Tuticorin Tamil, Thanjavur Tamil, Chennai colloquial), present it ONLY as a tentative hypothesis with alternative explanations. If the text is standard spoken or formal Tamil, state that it represents General Spoken Tamil (பொதுப் பேச்சுத்தமிழ்) with no regional bias.\n"
        "4. METRICS / FEATURE DISTRIBUTION: Provide an observed feature score (10 to 90 integer) for 5 linguistic categories based strictly on evidence density:\n"
        "   - colloquial_lexicon: Presence of spoken/informal words vs formal written Tamil.\n"
        "   - morphological_markers: Suffixes, honorifics, verb endings (e.g. -ங்கொ, -ல, -ஆப்ல, -ச்சேன்).\n"
        "   - discourse_particles: Interjections, address particles, conversational fillers (e.g. ஏலே, வே, பா, ஆமாம்).\n"
        "   - regional_indicators: Words or patterns specifically documented in regional dialects.\n"
        "   - syntactic_patterns: Sentence structure, spoken cadence, repetitions, or oral narration flow.\n"
        "   (Scores represent observed linguistic feature density in this sample, NOT regional probabilities!)\n"
        "5. DISTINCTIVE VOCABULARY: Extract up to 6 distinctive or culturally notable words. For each, give the word, exact context phrase from the transcript, brief observation, meaning if known, and possible regional note.\n"
        "6. LIMITATIONS: Include 2-3 honest limitations of transcript-only dialect analysis (e.g., lack of audio pitch/prosody, overlap between neighboring districts, brevity of sample).\n\n"
        "OUTPUT FORMAT: Return STRICTLY a valid JSON object matching this schema without any markdown formatting or commentary:\n"
        "{\n"
        '  "status": "success",\n'
        '  "overallAssessment": "<Concise 2-3 sentence overview in Tamil describing the register and linguistic character of the speech>",\n'
        '  "regionalIndicators": [\n'
        "    {\n"
        '      "region": "<e.g. Kongu Tamil | Madurai Tamil | Nellai Tamil | Thanjavur Tamil | Chennai Colloquial | General Spoken Tamil>",\n'
        '      "region_ta": "<Regional variety name in Tamil>",\n'
        '      "assessment": "<possible_indicator | shared_feature | insufficient_evidence>",\n'
        '      "confidenceLabel": "<சாத்தியமான அடையாளம் | பொதுப் பேச்சு வழக்கு | போதுமான சான்றில்லை>",\n'
        '      "evidence": [\n'
        "        {\n"
        '          "text": "<Exact phrase from transcript>",\n'
        '          "observation": "<Linguistic explanation in Tamil>",\n'
        '          "interpretation": "<Why this might suggest this variety>",\n'
        '          "limitations": "<Alternative explanation or ambiguity>"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "linguisticFeatures": [\n'
        "    {\n"
        '      "category": "<colloquial_expression | morphological_pattern | discourse_particle | syntactic_pattern>",\n'
        '      "label_ta": "<Tamil category label>",\n'
        '      "observation": "<Description of the observed feature in Tamil>",\n'
        '      "examples": [\n'
        "        {\n"
        '          "text": "<Exact phrase from transcript>",\n'
        '          "explanation": "<Explanation in Tamil>"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "distinctiveVocabulary": [\n'
        "    {\n"
        '      "word": "<Tamil word from transcript>",\n'
        '      "context": "<Exact phrase from transcript containing the word>",\n'
        '      "meaning": "<Brief meaning in Tamil or null>",\n'
        '      "regionalAssociation": "<Possible region or null>",\n'
        '      "evidenceLevel": "observed",\n'
        '      "explanation": "<Linguistic observation in Tamil>"\n'
        "    }\n"
        "  ],\n"
        '  "radarMetrics": [\n'
        '    {"category": "colloquial_lexicon", "score": <int 10-90>, "evidenceCount": <int>},\n'
        '    {"category": "morphological_markers", "score": <int 10-90>, "evidenceCount": <int>},\n'
        '    {"category": "discourse_particles", "score": <int 10-90>, "evidenceCount": <int>},\n'
        '    {"category": "regional_indicators", "score": <int 10-90>, "evidenceCount": <int>},\n'
        '    {"category": "syntactic_patterns", "score": <int 10-90>, "evidenceCount": <int>}\n'
        "  ],\n"
        '  "limitations": [\n'
        '    "<Limitation 1 in Tamil>",\n'
        '    "<Limitation 2 in Tamil>"\n'
        "  ]\n"
        "}\n\n"
        "JSON:"
    )


def _parse_and_validate_dialect_response(raw_text, original_transcript):
    """
    Parses LLM output, validates against schema, sanitizes text, and verifies
    that all cited evidence excerpts actually occur in the original transcript.
    """
    data = None

    # Strip code block wrappers
    candidate = raw_text.strip()
    if '```json' in candidate:
        candidate = candidate.split('```json', 1)[1].split('```', 1)[0].strip()
    elif '```' in candidate:
        candidate = candidate.split('```', 1)[1].split('```', 1)[0].strip()
    else:
        obj_m = re.search(r'\{\s*".*"\s*:.*\}', candidate, re.DOTALL)
        if obj_m:
            candidate = obj_m.group(0)

    try:
        data = json.loads(candidate)
    except Exception:
        # Resilient JSON recovery if model output was truncated or slightly malformed
        data = _salvage_dialect_json(raw_text, original_transcript)

    if not isinstance(data, dict):
        data = _generate_fallback_linguistic_profile(original_transcript)

    # 1. Overall assessment
    overall = str(data.get('overallAssessment', '')).strip()
    if not overall or len(overall) < 10:
        overall = "இவ்வுரையில் இயல்பான வாய்மொழித் தமிழ் நடை மற்றும் சமகாலப் பேச்சுவழக்குக் கூறுகள் காணப்படுகின்றன."

    # 2. Regional Indicators validation & evidence check
    raw_indicators = data.get('regionalIndicators', [])
    clean_indicators = []
    if isinstance(raw_indicators, list):
        for ind in raw_indicators:
            if not isinstance(ind, dict):
                continue
            region = str(ind.get('region', '')).strip() or "General Spoken Tamil"
            region_ta = str(ind.get('region_ta', '')).strip() or region
            assessment = str(ind.get('assessment', 'possible_indicator')).strip()
            conf_label = str(ind.get('confidenceLabel', 'சாத்தியமான அடையாளம்')).strip()

            raw_ev = ind.get('evidence', [])
            clean_ev = []
            if isinstance(raw_ev, list):
                for e in raw_ev:
                    if not isinstance(e, dict):
                        continue
                    text = str(e.get('text', '')).strip()
                    if not text:
                        continue
                    # Cross-verify evidence text against original transcript
                    is_in_transcript = (text.lower() in original_transcript.lower()) or _fuzzy_phrase_match(text, original_transcript)
                    clean_ev.append({
                        "text": text,
                        "observation": str(e.get('observation', '')).strip() or "மொழியியல் அவதானிப்பு.",
                        "interpretation": str(e.get('interpretation', '')).strip() or "பேச்சு வழக்குச் சாயல்.",
                        "limitations": str(e.get('limitations', '')).strip() or "பிற மாவட்டங்களிலும் இவ்வழக்கு காணப்படலாம்.",
                        "verifiedInTranscript": is_in_transcript
                    })

            clean_indicators.append({
                "region": region,
                "region_ta": region_ta,
                "assessment": assessment,
                "confidenceLabel": conf_label,
                "evidence": clean_ev
            })

    # If indicators are empty, provide an evidence-based default for General Spoken Tamil
    if not clean_indicators:
        clean_indicators = [{
            "region": "General Spoken Tamil",
            "region_ta": "பொதுப் பேச்சுத்தமிழ்",
            "assessment": "shared_feature",
            "confidenceLabel": "பொதுப் பேச்சு வழக்கு",
            "evidence": [{
                "text": original_transcript[:60] + ("..." if len(original_transcript) > 60 else ""),
                "observation": "இவ்வுரையில் தனித்துவமான வட்டாரச் சார்பின்றி பொதுவான பேச்சுத்தமிழ் வாக்கிய அமைப்புகள் காணப்படுகின்றன.",
                "interpretation": "தமிழ்நாடு முழுவதும் பரவலாகப் பேசப்படும் பொது வழக்கு.",
                "limitations": "வட்டார அடையாளங்களை அறுதியிட கூடுதல் ஒலியியல் அல்லது சொல்லியல் சான்றுகள் தேவை.",
                "verifiedInTranscript": True
            }]
        }]

    # 3. Linguistic Features validation
    raw_features = data.get('linguisticFeatures', [])
    clean_features = []
    if isinstance(raw_features, list):
        for f in raw_features:
            if not isinstance(f, dict):
                continue
            cat = str(f.get('category', 'colloquial_expression')).strip()
            label_ta = str(f.get('label_ta', '')).strip() or "பேச்சு வழக்குக் கூறு"
            obs = str(f.get('observation', '')).strip()
            if not obs:
                continue

            raw_examples = f.get('examples', [])
            clean_examples = []
            if isinstance(raw_examples, list):
                for ex in raw_examples:
                    if isinstance(ex, dict):
                        ex_text = str(ex.get('text', '')).strip()
                        ex_expl = str(ex.get('explanation', '')).strip()
                        if ex_text:
                            clean_examples.append({
                                "text": ex_text,
                                "explanation": ex_expl or obs,
                                "verifiedInTranscript": (ex_text.lower() in original_transcript.lower()) or _fuzzy_phrase_match(ex_text, original_transcript)
                            })
                    elif isinstance(ex, str) and ex.strip():
                        clean_examples.append({
                            "text": ex.strip(),
                            "explanation": obs,
                            "verifiedInTranscript": (ex.strip().lower() in original_transcript.lower())
                        })

            clean_features.append({
                "category": cat,
                "label_ta": label_ta,
                "observation": obs,
                "examples": clean_examples
            })

    # 4. Distinctive Vocabulary validation
    raw_vocab = data.get('distinctiveVocabulary', [])
    clean_vocab = []
    if isinstance(raw_vocab, list):
        for v in raw_vocab:
            if not isinstance(v, dict):
                continue
            word = str(v.get('word', '')).strip()
            if not word:
                continue
            context = str(v.get('context', '')).strip() or word
            meaning = v.get('meaning')
            if meaning is not None:
                meaning = str(meaning).strip()
                if meaning.lower() in ('null', 'none', ''):
                    meaning = None

            reg_assoc = v.get('regionalAssociation')
            if reg_assoc is not None:
                reg_assoc = str(reg_assoc).strip()
                if reg_assoc.lower() in ('null', 'none', ''):
                    reg_assoc = None

            clean_vocab.append({
                "word": word,
                "context": context,
                "meaning": meaning,
                "regionalAssociation": reg_assoc,
                "evidenceLevel": "observed",
                "explanation": str(v.get('explanation', '')).strip() or "வாய்மொழி உரையாடலில் பயின்றுவந்துள்ள சொல்.",
                "verifiedInTranscript": (word.lower() in original_transcript.lower())
            })

    # 5. Radar Metrics validation (5 standardized categories)
    raw_radar = data.get('radarMetrics', [])
    radar_map = {}
    if isinstance(raw_radar, list):
        for rm in raw_radar:
            if isinstance(rm, dict) and 'category' in rm:
                k = str(rm['category']).strip()
                try:
                    score = int(rm.get('score', 30))
                    score = max(10, min(95, score))
                except (ValueError, TypeError):
                    score = 30
                try:
                    ev_count = int(rm.get('evidenceCount', 1))
                except (ValueError, TypeError):
                    ev_count = 1
                radar_map[k] = {"score": score, "evidenceCount": ev_count}

    final_radar = []
    for cat in LINGUISTIC_CATEGORIES:
        k = cat['key']
        entry = radar_map.get(k, {})
        score = entry.get('score', 35)
        ev_count = entry.get('evidenceCount', 1)
        final_radar.append({
            "category": k,
            "label_ta": cat["label_ta"],
            "label_en": cat["label_en"],
            "score": score,
            "evidenceCount": ev_count
        })

    # 6. Limitations
    raw_limits = data.get('limitations', [])
    clean_limits = []
    if isinstance(raw_limits, list):
        for l in raw_limits:
            if str(l).strip():
                clean_limits.append(str(l).strip())

    if not clean_limits:
        clean_limits = [
            "எழுத்து வடிவிலான உரை மட்டுமே பகுப்பாய்வு செய்யப்பட்டுள்ளது; ஒலியின் ஏற்ற இறக்கங்கள் (intonation/prosody) கருத்தில் கொள்ளப்படவில்லை.",
            "அருகருகே உள்ள மாவட்டங்களின் பேச்சுவழக்குகள் ஒன்றுடன் ஒன்று கலந்திருப்பதால், ஒரு குறிப்பிட்ட பகுதியை உறுதியாக வரையறுக்க இயலாது.",
            "பேசுபவரின் தனிப்பட்ட மொழி நடை அல்லது தற்காலிகப் பேச்சுச்சூழல் இதில் பிரதிபலிக்கலாம்."
        ]

    return {
        "status": "success",
        "analysisType": "transcript_based_linguistic_analysis",
        "language": "Tamil",
        "overallAssessment": overall,
        "regionalIndicators": clean_indicators,
        "linguisticFeatures": clean_features,
        "distinctiveVocabulary": clean_vocab,
        "radarMetrics": final_radar,
        "limitations": clean_limits
    }


def _fuzzy_phrase_match(phrase, full_text):
    """
    Checks if words in phrase largely appear in contiguous order within full_text.
    Tolerates minor punctuation or whitespace differences.
    """
    if not phrase or not full_text:
        return False
    clean_phrase = re.sub(r'[^\w\s]', '', phrase).strip()
    clean_full = re.sub(r'[^\w\s]', '', full_text).strip()
    return clean_phrase.lower() in clean_full.lower()


def _salvage_dialect_json(raw_text, original_transcript):
    """
    Attempts regex recovery of core fields if model output contains truncated or malformed JSON.
    """
    overall = ""
    ov_m = re.search(r'"overallAssessment"\s*:\s*"((?:[^"\\]|\\.)*?)(?:"\s*,|\s*"\w+"\s*:|"\s*\}|$)', raw_text, re.DOTALL)
    if ov_m:
        overall = ov_m.group(1).replace('\\"', '"').replace('\\n', ' ').strip()

    # Extract any vocabulary words
    vocab = []
    words_found = re.findall(r'"word"\s*:\s*"([^"]+)"', raw_text)
    for w in words_found[:5]:
        if w.strip() and w.strip() in original_transcript:
            vocab.append({
                "word": w.strip(),
                "context": w.strip(),
                "meaning": None,
                "regionalAssociation": None,
                "evidenceLevel": "observed",
                "explanation": "உரையில் அவதானிக்கப்பட்ட தனித்துவச் சொல்."
            })

    return {
        "status": "success",
        "overallAssessment": overall or "இவ்வுரையில் பேச்சு வழக்கு மற்றும் உரையாடல் கூறுகள் காணப்படுகின்றன.",
        "regionalIndicators": [],
        "linguisticFeatures": [],
        "distinctiveVocabulary": vocab,
        "radarMetrics": [],
        "limitations": []
    }


def _generate_fallback_linguistic_profile(transcript):
    """
    Provides a safe, non-hallucinatory linguistic structure when upstream model output is unparseable.
    """
    words = [w for w in re.split(r'\s+', transcript) if w.strip()]
    return {
        "status": "success",
        "overallAssessment": f"வழங்கப்பட்ட {len(words)} சொற்கள் கொண்ட தமிழ் உரை பகுப்பாய்வு செய்யப்பட்டது. பொதுப் பேச்சு வழக்கு அமைப்பு அவதானிக்கப்பட்டது.",
        "regionalIndicators": [{
            "region": "General Spoken Tamil",
            "region_ta": "பொதுப் பேச்சுத்தமிழ்",
            "assessment": "shared_feature",
            "confidenceLabel": "பொதுப் பேச்சு வழக்கு",
            "evidence": [{
                "text": transcript[:60],
                "observation": "இவ்வுரையில் பொதுவான வாய்மொழி வாக்கிய அமைப்பு பயின்றுவந்துள்ளது.",
                "interpretation": "தமிழ்நாடு முழுவதும் பகிரப்பட்ட பேச்சு வழக்கு.",
                "limitations": "வட்டார அடையாளங்களை உறுதிப்படுத்த கூடுதல் உரைத் தரவுகள் தேவை.",
                "verifiedInTranscript": True
            }]
        }],
        "linguisticFeatures": [{
            "category": "colloquial_expression",
            "label_ta": "வாய்மொழி உரை நடை",
            "observation": "இயல்பான பேச்சுத் தமிழ் வாக்கிய அமைப்பு.",
            "examples": [{"text": transcript[:40], "explanation": "உரையாடல் நடை.", "verifiedInTranscript": True}]
        }],
        "distinctiveVocabulary": [],
        "radarMetrics": [
            {"category": cat["key"], "score": 35, "evidenceCount": 1}
            for cat in LINGUISTIC_CATEGORIES
        ],
        "limitations": [
            "பகுப்பாய்வுத் தகவல்களை முழுமையாக மீட்க முடியவில்லை; அடிப்படையான மொழியியல் தகவல்கள் மட்டும் காட்சிப்படுத்தப்படுகின்றன."
        ]
    }
