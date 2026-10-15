"""
MARAPOLI (மரபொலி) — Tamil Heritage Digital Preservation Platform
Standalone Voice & Oral History Studio Web Application
"""

import sys
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import io
import time
import json
import base64
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response

import database
import speech_service
import region_service
import dictionary_service
import summary_service
import dialect_service
import atlas_service

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload limit

# Upload directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads', 'audio')
try:
    os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)
except OSError:
    AUDIO_UPLOAD_DIR = os.path.join('/tmp', 'uploads', 'audio')
    os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

# Initialize SQLite database and Atlas schema
database.init_db()
atlas_service.init_atlas_schema()

# Universal allowed audio & video extensions
ALLOWED_AUDIO_EXTENSIONS = {
    '.wav', '.mp3', '.m4a', '.webm', '.ogg', '.aac', '.flac',
    '.mpeg', '.mpg', '.mp4', '.3gp', '.3g2', '.amr', '.wma',
    '.opus', '.oga', '.aiff', '.aif', '.mkv', '.avi', '.mov',
    '.wmv', '.m4v', '.caf'
}


# =========================================================================
# PRIMARY APPLICATION ROUTE (Standalone Audio Studio)
# =========================================================================

@app.route('/')
@app.route('/api/index')
@app.route('/api/index.py')
def index():
    """Main and only page of the website: MARAPOLI Tamil Audio Studio."""
    return render_template('audio.html')


@app.route('/atlas')
def voice_atlas():
    """Interactive Voice-to-Village Atlas (ஒவ்வொரு ஊருக்கும் ஒரு குரல்)."""
    google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()
    return render_template('atlas.html', google_maps_api_key=google_maps_key)


# =========================================================================
# VOICE-TO-VILLAGE ATLAS APIS
# =========================================================================

@app.route('/api/atlas/locations', methods=['GET'])
def api_get_atlas_locations():
    """Returns verified locations with story counts, coordinates, and categories."""
    district = request.args.get('district', '').strip()
    category = request.args.get('category', '').strip()
    query = request.args.get('q', '').strip()
    locations = atlas_service.get_atlas_locations(district=district, category=category, query=query)
    districts = atlas_service.get_available_districts()
    categories = atlas_service.get_available_categories()
    return jsonify({
        "success": True,
        "count": len(locations),
        "locations": locations,
        "districts": districts,
        "categories": categories
    })


@app.route('/api/atlas/locations/<int:location_id>/stories', methods=['GET'])
def api_get_location_stories(location_id):
    """Returns all stories preserved for a specific location."""
    category = request.args.get('category', '').strip()
    data = atlas_service.get_location_stories(location_id, category=category)
    if not data:
        return jsonify({"success": False, "error": "Location not found"}), 404
    return jsonify({
        "success": True,
        "location": data["location"],
        "count": data["count"],
        "stories": data["stories"]
    })


@app.route('/api/atlas/stories/<int:story_id>', methods=['GET'])
def api_get_atlas_story_details(story_id):
    """Returns detailed story metadata, audio URL, transcript, and vocabulary."""
    story = atlas_service.get_story_details(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story not found"}), 404
    return jsonify({
        "success": True,
        "story": story
    })


@app.route('/api/atlas/stories/<int:story_id>/related', methods=['GET'])
def api_get_atlas_related_stories(story_id):
    """Returns evidence-backed related stories for the Story Constellation."""
    related = atlas_service.get_related_stories(story_id)
    return jsonify({
        "success": True,
        "story_id": story_id,
        "count": len(related),
        "related": related
    })


@app.route('/api/atlas/constellation', methods=['GET'])
def api_get_story_constellation():
    """Returns full story and location graph nodes and links for constellation exploration."""
    location_id = request.args.get('location_id', type=int)
    constellation = atlas_service.get_story_constellation(location_id=location_id)
    return jsonify({
        "success": True,
        "constellation": constellation,
        "nodes": constellation.get("nodes", []),
        "links": constellation.get("links", [])
    })


# =========================================================================
# CORE SPEECH & ENTITY EXTRACTION APIS
# =========================================================================

@app.route('/api/transcribe', methods=['POST'])
def api_transcribe():
    """Transcribes Tamil speech from any audio format and auto-extracts all metadata."""
    if 'audio' not in request.files:
        return jsonify({
            "success": False,
            "error": "ஒலிக்கோப்பு எதுவும் பெறப்படவில்லை (No audio file provided in request)."
        }), 400

    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return jsonify({
            "success": False,
            "error": "வெற்று ஒலிக்கோப்பு பெறப்பட்டது (Empty audio file received)."
        }), 400

    orig_ext = os.path.splitext(audio_file.filename)[1].lower()
    if not orig_ext:
        orig_ext = '.webm'

    if orig_ext not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"ஆதரிக்கப்படாத ஒலிக்கோப்பு வடிவம் ({orig_ext}). தயவுசெய்து வழக்கமான ஒலிக்கோப்பைப் பதிவேற்றவும்."
        }), 400

    safe_name = f"story_rec_{int(time.time() * 1000)}{orig_ext}"
    temp_path = os.path.join(AUDIO_UPLOAD_DIR, safe_name)

    try:
        audio_file.save(temp_path)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"ஒலிக்கோப்பைச் சேமிப்பதில் பிழை: {str(e)}"
        }), 500

    # Call Tamil Speech Transcription engine
    result = speech_service.transcribe_tamil_audio(temp_path)
    result['audio_filename'] = safe_name
    result['audio_url'] = url_for('static', filename=f'uploads/audio/{safe_name}')

    # Automatically extract full metadata and identify region from transcribed speech
    if result.get('success') and result.get('text'):
        try:
            extracted = region_service.extract_full_metadata(result['text'])
            result['extracted_metadata'] = extracted
            result['region_analysis'] = extracted.get('location_details')
        except Exception:
            result['extracted_metadata'] = None
            result['region_analysis'] = None

    return jsonify(result)


@app.route('/api/analyze-region', methods=['POST'])
def api_analyze_region():
    """Extracts all entities (speaker details, location, dates, topic, title, description) from transcript."""
    data = request.get_json(silent=True) or {}
    transcript = data.get('transcript', '') or request.form.get('transcript', '')
    if not transcript or not transcript.strip():
        return jsonify({
            "success": False,
            "error": "பகுப்பாய்வு செய்வதற்குத் தமிழ் உரை தேவை (Tamil transcript text is required)."
        }), 400

    extracted_metadata = region_service.extract_full_metadata(transcript)
    region_data = extracted_metadata.get('location_details')
    return jsonify({
        "success": True,
        "region_data": region_data,
        "extracted_metadata": extracted_metadata
    })


@app.route('/api/stories', methods=['POST'])
def api_save_story():
    """Saves a Tamil oral history record into the SQLite database."""
    title = request.form.get('title', '').strip()
    transcript = request.form.get('transcript', '').strip()
    source_type = request.form.get('source_type', 'audio').strip()
    storyteller = request.form.get('storyteller', 'Anonymous').strip()
    region = request.form.get('region', '').strip()
    ai_suggested_region = request.form.get('ai_suggested_region', '').strip()
    region_metadata = request.form.get('region_metadata', '').strip()
    topic = request.form.get('topic', '').strip()
    record_date = request.form.get('record_date', '').strip()
    description = request.form.get('description', '').strip()

    if not title:
        return jsonify({"success": False, "error": "Story title is required."}), 400
    if not transcript:
        return jsonify({"success": False, "error": "Tamil transcript text is required."}), 400

    audio_path = ''
    image_path = ''

    # Handle Audio upload
    if 'audio_file' in request.files:
        af = request.files['audio_file']
        if af and af.filename:
            ext = os.path.splitext(af.filename)[1].lower() or '.webm'
            safe_af_name = f"story_audio_{int(time.time() * 1000)}{ext}"
            dest = os.path.join(AUDIO_UPLOAD_DIR, safe_af_name)
            af.save(dest)
            audio_path = url_for('static', filename=f'uploads/audio/{safe_af_name}')

    record_id = database.insert_record(
        title=title,
        source_type=source_type,
        transcript=transcript,
        storyteller=storyteller,
        region=region,
        ai_suggested_region=ai_suggested_region,
        region_metadata=region_metadata,
        topic=topic,
        record_date=record_date,
        description=description,
        audio_path=audio_path,
        image_path=image_path
    )

    try:
        atlas_service.link_story_to_location(record_id, region, title=title, transcript=transcript)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "id": record_id,
        "message": "Story successfully saved into Tamil Heritage Archive."
    })


@app.route('/api/library')
def api_get_library():
    """Returns all preserved records for the live archive section."""
    q = request.args.get('q', '').strip()
    source_type = request.args.get('source', 'all').strip()
    topic = request.args.get('topic', 'all').strip()
    region = request.args.get('region', '').strip()
    storyteller = request.args.get('storyteller', '').strip()

    records = database.search_records(
        query=q,
        source_type=source_type,
        topic=topic,
        region=region,
        storyteller=storyteller
    )
    return jsonify({
        "success": True,
        "count": len(records),
        "records": records
    })


@app.route('/api/stories/<int:story_id>', methods=['GET', 'PUT', 'DELETE'])
def api_single_story(story_id):
    """View, update, or delete a single story."""
    if request.method == 'GET':
        rec = database.get_record(story_id)
        if not rec:
            return jsonify({"success": False, "error": "Record not found."}), 404
        return jsonify({"success": True, "record": rec})

    elif request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        success = database.update_record(
            record_id=story_id,
            title=data.get('title'),
            transcript=data.get('transcript'),
            storyteller=data.get('storyteller'),
            region=data.get('region'),
            ai_suggested_region=data.get('ai_suggested_region'),
            region_metadata=data.get('region_metadata'),
            topic=data.get('topic'),
            record_date=data.get('record_date'),
            description=data.get('description')
        )
        if not success:
            return jsonify({"success": False, "error": "Record not found or update failed."}), 400
        return jsonify({"success": True, "message": "Record successfully updated."})

    elif request.method == 'DELETE':
        success = database.delete_record(story_id)
        if not success:
            return jsonify({"success": False, "error": "Record not found."}), 404
        return jsonify({"success": True, "message": "Record deleted successfully."})


@app.route('/api/export/<int:story_id>/<string:fmt>')
def api_export_story(story_id, fmt):
    """Direct export of a story as JSON or plain TXT."""
    rec = database.get_record(story_id)
    if not rec:
        return "Record not found", 404

    ascii_title = "".join(c for c in rec['title'] if c.isascii() and (c.isalnum() or c in (' ', '_', '-'))).strip().replace(' ', '_')
    if not ascii_title:
        ascii_title = f"tamil_heritage_record_{story_id}"

    # Fetch associated dictionary entries if any
    dict_entries = database.get_dictionary_entries_for_story(story_id)

    if fmt.lower() == 'json':
        export_data = {
            "id": rec['id'],
            "title": rec['title'],
            "source_type": rec['source_type'],
            "storyteller": rec['storyteller'],
            "region": rec['region'],
            "ai_suggested_region": rec.get('ai_suggested_region', ''),
            "topic": rec['topic'],
            "record_date": rec['record_date'],
            "description": rec['description'],
            "transcript": rec['transcript'],
            "original_transcript": rec.get('original_transcript', rec['transcript']),
            "dictionary_entries": dict_entries,
            "created_at": rec['created_at'],
            "archive": "MARAPOLI (மரபொலி) • தமிழ் மரபின் குரல்"
        }
        json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')
        encoded_fn = urllib.parse.quote(f"{rec['title']}.json")
        return Response(
            json_bytes,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{ascii_title}.json"; filename*=UTF-8\'\'{encoded_fn}'}
        )

    # Default: TXT
    dict_text = ""
    if dict_entries:
        dict_text = "\n\n" + "=" * 60 + "\n📖 தமிழ்ச் சொல் நினைவகம் (Dictionary Entries):\n" + "-" * 60 + "\n"
        for de in dict_entries:
            dict_text += f"\n• சொல்: {de['word']}\n"
            dict_text += f"  தமிழ் விளக்கம்: {de['meaning_ta']}\n"
            dict_text += f"  English: {de['meaning_en']}\n"
            if de.get('contextual_meaning_ta'):
                dict_text += f"  சூழல் விளக்கம்: {de['contextual_meaning_ta']}\n"
            if de.get('category'):
                dict_text += f"  வகை: {de['category']}\n"
            if de.get('source_excerpt'):
                dict_text += f"  மேற்கோள்: \"{de['source_excerpt']}\"\n"

    text_content = (
        f"MARAPOLI (மரபொலி) • தமிழ் மரபின் குரல்\n"
        f"{'='*60}\n"
        f"தலைப்பு: {rec['title']}\n"
        f"கூறுபவர்: {rec['storyteller']}\n"
        f"வகை: {rec['topic']}\n"
        f"ஊர்/வட்டாரம்: {rec['region']}\n"
        f"பதிவு தேதி: {rec['record_date']}\n"
        f"மூலம்: {rec['source_type']}\n"
        f"{'-'*60}\n\n"
        f"{rec['transcript']}\n"
        f"{dict_text}"
    )
    encoded_fn = urllib.parse.quote(f"{rec['title']}.txt")
    return Response(
        text_content.encode('utf-8'),
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{ascii_title}.txt"; filename*=UTF-8\'\'{encoded_fn}'}
    )


# =========================================================================
# TAMIL MEMORY DICTIONARY (தமிழ்ச்சொல் நினைவகம்) APIS
# =========================================================================

@app.route('/api/dictionary/explain-text', methods=['POST'])
def api_explain_text():
    """
    Directly extracts and explains Tamil cultural and dialect words from
    recorded or input speech text using NVIDIA AI API directly.
    Does NOT require saving to a database.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    text = (data.get('text') or data.get('transcript') or '').strip()
    if not text:
        return jsonify({
            "success": False,
            "error": "பொருள் அறிவதற்குத் தமிழ் உரை தேவை (Tamil text is required)."
        }), 400

    result = dictionary_service.generate_dictionary_from_transcript(text)
    return jsonify(result)


@app.route('/api/dictionary/lookup-word', methods=['POST'])
def api_lookup_word():
    """
    Directly looks up the cultural and linguistic meaning of a single Tamil word
    using NVIDIA AI API directly.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    word = (data.get('word') or '').strip()
    context = (data.get('context') or '').strip()
    if not word:
        return jsonify({"success": False, "error": "தமிழ்ச் சொல் தேவை (Tamil word is required)."}), 400

    result = dictionary_service.lookup_tamil_word(word, context=context)
    return jsonify(result)


@app.route('/api/summarize', methods=['POST'])
def api_summarize_story():
    """
    Directly generates concise, faithful Tamil and English summaries from a recorded
    or input transcript using NVIDIA's hosted AI API.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    transcript = (data.get('transcript') or data.get('text') or '').strip()
    if not transcript:
        return jsonify({
            "success": False,
            "error": "சுருக்கம் உருவாக்கத் தமிழ் உரை தேவை. தயவுசெய்து ஒலியைப் பதிவு செய்து உரையாக்கவும்."
        }), 400

    try:
        result = summary_service.generate_story_summary(transcript)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"கதைச் சுருக்கம் உருவாக்குவதில் பிழை: {str(e)}"
        }), 502

    status_code = 200 if result.get('success') else 502
    return jsonify(result), status_code


@app.route('/api/dialect-dna', methods=['POST'])
@app.route('/api/dialect/analyze', methods=['POST'])
def api_analyze_dialect():
    """
    Evidence-based Tamil Dialect DNA & linguistic feature analysis from transcript.
    Uses NVIDIA hosted LLM to extract observed colloquial vocabulary, morphological patterns,
    discourse particles, regional indicators, and radar metrics.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    transcript = (data.get('transcript') or data.get('text') or '').strip()
    if not transcript:
        return jsonify({
            "success": False,
            "status": "empty_input",
            "error": "வட்டார மொழிப் பகுப்பாய்வு செய்யத் தமிழ் உரை தேவை (Tamil transcript is required)."
        }), 400

    try:
        result = dialect_service.analyze_dialect(transcript)
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "server_error",
            "error": f"வட்டார மொழிப் பகுப்பாய்வில் பிழை ஏற்பட்டது: {str(e)}"
        }), 500

    status_code = 200 if result.get('success') else 502
    return jsonify(result), status_code


@app.route('/api/stories/<int:story_id>/dictionary/generate', methods=['POST'])
def api_generate_story_dictionary(story_id):
    """
    Generate rich Tamil Memory Dictionary entries from a saved story's transcript using NVIDIA hosted API.
    Uses corrected transcript when available, preserves original transcript and recording.
    """
    story = database.get_record(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story record not found."}), 404

    # Use corrected transcript if available, fallback to original_transcript
    transcript = (story.get('transcript') or '').strip()
    if not transcript:
        transcript = (story.get('original_transcript') or '').strip()

    if not transcript:
        return jsonify({
            "success": False,
            "error": "இக்கதையில் உரை எதுவும் இல்லை. அகராதி உருவாக்கத் தமிழ் உரை தேவை (Transcript is empty)."
        }), 400

    # Call NVIDIA hosted LLM service
    result = dictionary_service.generate_dictionary_from_transcript(transcript, story_metadata=story)
    if not result.get('success'):
        return jsonify({
            "success": False,
            "error": result.get('error', 'அகராதி உருவாக்கத்தில் பிழை ஏற்பட்டது.')
        }), 502

    generated_entries = result.get('entries', [])
    if not generated_entries:
        return jsonify({
            "success": True,
            "message": "குறிப்பிடத்தக்க வட்டார அல்லது பாரம்பரியச் சொற்கள் கண்டறியப்படவில்லை.",
            "entries": [],
            "count": 0,
            "stats": {"inserted": 0, "updated": 0, "skipped": 0}
        })

    # Non-destructively upsert entries (preserves human-reviewed and verified entries)
    stats = database.upsert_generated_dictionary_entries(story_id, generated_entries)
    all_entries = database.get_dictionary_entries_for_story(story_id)

    return jsonify({
        "success": True,
        "message": f"{stats['inserted']} புதிய சொற்கள் நினைவகத்தில் சேர்க்கப்பட்டன.",
        "entries": all_entries,
        "count": len(all_entries),
        "stats": stats,
        "model": result.get('model')
    })


@app.route('/api/stories/<int:story_id>/dictionary', methods=['GET'])
def api_get_story_dictionary(story_id):
    """Retrieve all dictionary entries for a specific story with optional filtering."""
    story = database.get_record(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story record not found."}), 404

    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()
    query = request.args.get('q', '').strip()

    entries = database.get_dictionary_entries_for_story(
        story_id=story_id,
        category=category,
        review_status=status,
        query=query
    )
    categories = database.get_dictionary_categories(story_id=story_id)

    return jsonify({
        "success": True,
        "story_id": story_id,
        "story_title": story.get('title'),
        "count": len(entries),
        "entries": entries,
        "categories": categories
    })


@app.route('/api/stories/<int:story_id>/dictionary/entries', methods=['POST'])
def api_add_dictionary_entry(story_id):
    """Manually add a new dictionary entry to a story."""
    story = database.get_record(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story record not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    word = (data.get('word') or '').strip()
    meaning_ta = (data.get('meaning_ta') or '').strip()
    meaning_en = (data.get('meaning_en') or '').strip()

    if not word:
        return jsonify({"success": False, "error": "தமிழ்ச் சொல் அவசியம் (Word is required)."}), 400
    if not meaning_ta and not meaning_en:
        return jsonify({"success": False, "error": "பொருள் விளக்கம் அவசியம் (Meaning in Tamil or English is required)."}), 400

    # Ensure timestamps, if passed, are valid numbers and within reasonable bounds
    start_sec = data.get('start_seconds')
    end_sec = data.get('end_seconds')
    try:
        start_sec = float(start_sec) if start_sec is not None and str(start_sec).strip() != '' else None
        end_sec = float(end_sec) if end_sec is not None and str(end_sec).strip() != '' else None
    except (ValueError, TypeError):
        start_sec = None
        end_sec = None

    entry_id = database.insert_dictionary_entry(
        story_id=story_id,
        word=word,
        meaning_ta=meaning_ta or f"{word} என்பதன் விளக்கம்.",
        meaning_en=meaning_en or f"Definition of {word}.",
        contextual_meaning_ta=(data.get('contextual_meaning_ta') or '').strip(),
        example_sentence=(data.get('example_sentence') or '').strip(),
        category=(data.get('category') or 'பாரம்பரிய அறிவு').strip(),
        source_excerpt=(data.get('source_excerpt') or '').strip(),
        start_seconds=start_sec,
        end_seconds=end_sec,
        confidence=float(data.get('confidence', 1.0)),
        review_status=data.get('review_status', 'verified')
    )

    new_entry = database.get_dictionary_entry(entry_id)
    return jsonify({
        "success": True,
        "id": entry_id,
        "entry": new_entry,
        "message": "புதிய சொல் தமிழ்ச் சொல் நினைவகத்தில் சேர்க்கப்பட்டது."
    }), 201


@app.route('/api/dictionary/search', methods=['GET'])
def api_search_dictionary():
    """Global or story-scoped search across all dictionary entries and stories."""
    query = request.args.get('q', '').strip()
    story_id = request.args.get('story_id', type=int)
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()
    limit = request.args.get('limit', default=100, type=int)
    offset = request.args.get('offset', default=0, type=int)

    results = database.search_dictionary_entries(
        query=query,
        story_id=story_id,
        category=category,
        review_status=status,
        limit=limit,
        offset=offset
    )
    categories = database.get_dictionary_categories(story_id=story_id)

    return jsonify({
        "success": True,
        "count": len(results),
        "entries": results,
        "categories": categories
    })


@app.route('/api/dictionary/entries/<int:entry_id>', methods=['GET'])
def api_get_single_entry(entry_id):
    """Retrieve a single dictionary entry."""
    entry = database.get_dictionary_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Dictionary entry not found."}), 404
    return jsonify({"success": True, "entry": entry})


@app.route('/api/dictionary/entries/<int:entry_id>', methods=['PATCH', 'PUT'])
def api_update_dictionary_entry(entry_id):
    """Update or verify an existing dictionary entry."""
    entry = database.get_dictionary_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Dictionary entry not found."}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    success = database.update_dictionary_entry(
        entry_id=entry_id,
        word=data.get('word'),
        meaning_ta=data.get('meaning_ta'),
        meaning_en=data.get('meaning_en'),
        contextual_meaning_ta=data.get('contextual_meaning_ta'),
        example_sentence=data.get('example_sentence'),
        category=data.get('category'),
        source_excerpt=data.get('source_excerpt'),
        start_seconds=data.get('start_seconds'),
        end_seconds=data.get('end_seconds'),
        confidence=data.get('confidence'),
        review_status=data.get('review_status')
    )

    if not success:
        return jsonify({"success": False, "error": "Update failed."}), 400

    updated = database.get_dictionary_entry(entry_id)
    return jsonify({
        "success": True,
        "message": "சொல் விவரங்கள் புதுப்பிக்கப்பட்டன.",
        "entry": updated
    })


@app.route('/api/dictionary/entries/<int:entry_id>', methods=['DELETE'])
def api_delete_dictionary_entry(entry_id):
    """Delete a dictionary entry."""
    entry = database.get_dictionary_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Dictionary entry not found."}), 404

    deleted = database.delete_dictionary_entry(entry_id)
    if not deleted:
        return jsonify({"success": False, "error": "Delete failed."}), 400

    return jsonify({"success": True, "message": "சொல் அகராதியிலிருந்து நீக்கப்பட்டது."})



# =========================================================================
# REDIRECTS FOR ANY PREVIOUS URLS (All lead to main Audio Studio)
# =========================================================================

@app.route('/login', methods=['GET', 'POST'])
@app.route('/library')
@app.route('/characters', methods=['GET', 'POST'])
@app.route('/numerals', methods=['GET', 'POST'])
@app.route('/dashboard')
@app.route('/review')
@app.route('/original_characters', methods=['GET', 'POST'])
def legacy_redirect():
    """All previous pages redirect directly to the main Audio Studio."""
    return redirect(url_for('index'))


# Endpoint aliases for url_for compatibility
app.add_url_rule('/library', endpoint='library', view_func=legacy_redirect)
app.add_url_rule('/login', endpoint='login', view_func=legacy_redirect)
app.add_url_rule('/characters', endpoint='characters_upload', view_func=legacy_redirect)
app.add_url_rule('/numerals', endpoint='numerals_upload', view_func=legacy_redirect)
app.add_url_rule('/dashboard', endpoint='dashboard', view_func=legacy_redirect)
app.add_url_rule('/review', endpoint='review_queue_page', view_func=legacy_redirect)
app.add_url_rule('/original_characters', endpoint='original_characters_upload', view_func=legacy_redirect)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
