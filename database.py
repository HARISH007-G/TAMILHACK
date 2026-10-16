import os
import shutil
import sqlite3
from datetime import datetime

# Determine SQLite DB Path (use /tmp on Vercel or read-only serverless environments)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, 'tamil_heritage.db')

import tempfile

if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    base_tmp = '/tmp' if os.name != 'nt' else tempfile.gettempdir()
    TMP_DB = os.path.join(base_tmp, 'tamil_heritage.db')
    if not os.path.exists(TMP_DB) and os.path.exists(DEFAULT_DB):
        try:
            shutil.copy2(DEFAULT_DB, TMP_DB)
        except Exception:
            pass
    DB_PATH = TMP_DB if os.path.exists(TMP_DB) else DEFAULT_DB
else:
    DB_PATH = DEFAULT_DB


def get_db_connection():
    """Establish connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


import re

def init_db():
    """Initialize SQLite database schema for Tamil Heritage records and Dictionary entries."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS heritage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL, -- 'audio' or 'manuscript'
            storyteller TEXT DEFAULT 'Anonymous',
            region TEXT DEFAULT '',
            ai_suggested_region TEXT DEFAULT '',
            region_metadata TEXT DEFAULT '',
            topic TEXT DEFAULT '',
            record_date TEXT DEFAULT '',
            description TEXT DEFAULT '',
            transcript TEXT NOT NULL,
            original_transcript TEXT DEFAULT '',
            audio_path TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            normalized_word TEXT NOT NULL,
            meaning_ta TEXT NOT NULL,
            meaning_en TEXT NOT NULL,
            contextual_meaning_ta TEXT DEFAULT '',
            example_sentence TEXT DEFAULT '',
            category TEXT DEFAULT 'பாரம்பரிய அறிவு',
            source_excerpt TEXT DEFAULT '',
            start_seconds REAL DEFAULT NULL,
            end_seconds REAL DEFAULT NULL,
            confidence REAL DEFAULT NULL,
            review_status TEXT DEFAULT 'pending_review',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES heritage_records(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dict_story_id ON dictionary_entries(story_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dict_norm_word ON dictionary_entries(normalized_word)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dict_status ON dictionary_entries(review_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dict_category ON dictionary_entries(category)")

    conn.commit()

    # Automatic non-destructive schema migration for existing databases
    cursor.execute("PRAGMA table_info(heritage_records)")
    columns = [row['name'] for row in cursor.fetchall()]
    if 'ai_suggested_region' not in columns:
        cursor.execute("ALTER TABLE heritage_records ADD COLUMN ai_suggested_region TEXT DEFAULT ''")
    if 'region_metadata' not in columns:
        cursor.execute("ALTER TABLE heritage_records ADD COLUMN region_metadata TEXT DEFAULT ''")
    if 'original_transcript' not in columns:
        cursor.execute("ALTER TABLE heritage_records ADD COLUMN original_transcript TEXT DEFAULT ''")
        cursor.execute("UPDATE heritage_records SET original_transcript = transcript WHERE original_transcript = '' OR original_transcript IS NULL")

    conn.commit()
    conn.close()


def insert_record(title, source_type, transcript, storyteller='Anonymous',
                  region='', topic='', record_date='', description='',
                  audio_path='', image_path='', ai_suggested_region='',
                  region_metadata='', original_transcript=''):
    """Insert a new Tamil oral history or manuscript record."""
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if not record_date:
        record_date = datetime.now().strftime('%Y-%m-%d')
    if not storyteller or not storyteller.strip():
        storyteller = 'Anonymous'

    orig_tr = original_transcript.strip() if original_transcript and original_transcript.strip() else transcript.strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO heritage_records (
            title, source_type, storyteller, region, ai_suggested_region, region_metadata,
            topic, record_date, description, transcript, original_transcript,
            audio_path, image_path, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        title.strip(),
        source_type.strip(),
        storyteller.strip(),
        region.strip(),
        ai_suggested_region.strip() if ai_suggested_region else '',
        region_metadata.strip() if region_metadata else '',
        topic.strip(),
        record_date.strip(),
        description.strip(),
        transcript.strip(),
        orig_tr,
        audio_path.strip() if audio_path else '',
        image_path.strip() if image_path else '',
        now_iso,
        now_iso
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def search_records(query=None, source_type=None, topic=None, region=None, storyteller=None):
    """Search and filter records across Tamil text, metadata, and categories."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM heritage_records WHERE 1=1"
    params = []

    if query and query.strip():
        q_term = f"%{query.strip()}%"
        sql += " AND (title LIKE ? OR transcript LIKE ? OR description LIKE ? OR storyteller LIKE ? OR region LIKE ?)"
        params.extend([q_term, q_term, q_term, q_term, q_term])

    if source_type and source_type.strip() and source_type.lower() != 'all':
        sql += " AND source_type = ?"
        params.append(source_type.strip().lower())

    if topic and topic.strip() and topic.lower() != 'all':
        sql += " AND topic = ?"
        params.append(topic.strip())

    if region and region.strip():
        sql += " AND region LIKE ?"
        params.append(f"%{region.strip()}%")

    if storyteller and storyteller.strip():
        sql += " AND storyteller LIKE ?"
        params.append(f"%{storyteller.strip()}%")

    sql += " ORDER BY id DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_record(record_id):
    """Retrieve a single record by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM heritage_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_record(record_id, title=None, transcript=None, storyteller=None,
                  region=None, topic=None, record_date=None, description=None,
                  ai_suggested_region=None, region_metadata=None):
    """Update an existing record."""
    conn = get_db_connection()
    cursor = conn.cursor()

    existing = get_record(record_id)
    if not existing:
        conn.close()
        return False

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    new_title = title if title is not None else existing['title']
    new_transcript = transcript if transcript is not None else existing['transcript']
    new_storyteller = storyteller if storyteller is not None else existing['storyteller']
    new_region = region if region is not None else existing['region']
    new_ai_suggested = ai_suggested_region if ai_suggested_region is not None else existing.get('ai_suggested_region', '')
    new_meta = region_metadata if region_metadata is not None else existing.get('region_metadata', '')
    new_topic = topic if topic is not None else existing['topic']
    new_record_date = record_date if record_date is not None else existing['record_date']
    new_description = description if description is not None else existing['description']

    cursor.execute('''
        UPDATE heritage_records
        SET title = ?, transcript = ?, storyteller = ?, region = ?,
            ai_suggested_region = ?, region_metadata = ?,
            topic = ?, record_date = ?, description = ?, updated_at = ?
        WHERE id = ?
    ''', (
        new_title.strip(),
        new_transcript.strip(),
        new_storyteller.strip() if new_storyteller else 'Anonymous',
        new_region.strip(),
        new_ai_suggested.strip() if new_ai_suggested else '',
        new_meta.strip() if new_meta else '',
        new_topic.strip(),
        new_record_date.strip(),
        new_description.strip(),
        now_iso,
        record_id
    ))
    conn.commit()
    conn.close()
    return True


def delete_record(record_id):
    """Delete a record by ID and remove associated media if needed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM heritage_records WHERE id = ?", (record_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_all_topics():
    """Return distinct topics saved in the library."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM heritage_records WHERE topic != '' ORDER BY topic")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_all_regions():
    """Return distinct regions saved in the library."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT region FROM heritage_records WHERE region != '' ORDER BY region")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


# =========================================================================
# TAMIL MEMORY DICTIONARY (தமிழ்ச்சொல் நினைவகம்) DATABASE OPERATIONS
# =========================================================================

def normalize_tamil_word(word):
    """Normalize Tamil and mixed words for uniform indexing and search."""
    if not word:
        return ''
    w = str(word).strip().lower()
    # Strip common enclosing punctuation while keeping Tamil Unicode characters intact
    w = re.sub(r'[\s\.\,\;\:\!\?\"\'\(\)\[\]\{\}\<\>\-\_\/\\]+', ' ', w).strip()
    return w


def insert_dictionary_entry(story_id, word, meaning_ta, meaning_en,
                            contextual_meaning_ta='', example_sentence='',
                            category='பாரம்பரிய அறிவு', source_excerpt='',
                            start_seconds=None, end_seconds=None, confidence=None,
                            review_status='pending_review'):
    """Insert a new dictionary entry associated with a heritage story."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    norm_word = normalize_tamil_word(word)
    clean_cat = category.strip() if category and category.strip() else 'பாரம்பரிய அறிவு'

    # Sanitize seconds & confidence
    st_sec = float(start_seconds) if start_seconds is not None and str(start_seconds).strip() != '' else None
    en_sec = float(end_seconds) if end_seconds is not None and str(end_seconds).strip() != '' else None
    conf = float(confidence) if confidence is not None and str(confidence).strip() != '' else None

    # Status check
    status = review_status if review_status in ('pending_review', 'verified', 'flagged') else 'pending_review'

    cursor.execute('''
        INSERT INTO dictionary_entries (
            story_id, word, normalized_word, meaning_ta, meaning_en,
            contextual_meaning_ta, example_sentence, category, source_excerpt,
            start_seconds, end_seconds, confidence, review_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        story_id,
        word.strip(),
        norm_word,
        meaning_ta.strip(),
        meaning_en.strip(),
        contextual_meaning_ta.strip() if contextual_meaning_ta else '',
        example_sentence.strip() if example_sentence else '',
        clean_cat,
        source_excerpt.strip() if source_excerpt else '',
        st_sec,
        en_sec,
        conf,
        status,
        now_iso,
        now_iso
    ))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_dictionary_entry(entry_id):
    """Retrieve a single dictionary entry by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, h.title as story_title, h.storyteller, h.region as story_region, h.audio_path
        FROM dictionary_entries d
        JOIN heritage_records h ON d.story_id = h.id
        WHERE d.id = ?
    ''', (entry_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_dictionary_entries_for_story(story_id, category=None, review_status=None, query=None):
    """Retrieve all dictionary entries for a specific story with optional filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM dictionary_entries WHERE story_id = ?"
    params = [story_id]

    if category and category.strip() and category.lower() != 'all':
        sql += " AND category = ?"
        params.append(category.strip())

    if review_status and review_status.strip() and review_status.lower() != 'all':
        sql += " AND review_status = ?"
        params.append(review_status.strip())

    if query and query.strip():
        q_term = f"%{query.strip()}%"
        sql += " AND (word LIKE ? OR normalized_word LIKE ? OR meaning_ta LIKE ? OR meaning_en LIKE ? OR contextual_meaning_ta LIKE ?)"
        params.extend([q_term, q_term, q_term, q_term, q_term])

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def search_dictionary_entries(query=None, story_id=None, category=None, review_status=None, limit=100, offset=0):
    """Global or story-scoped search across dictionary words and definitions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = '''
        SELECT d.*, 
               COALESCE(h.title, 'மரபு ஆவணம்') as story_title, 
               COALESCE(h.storyteller, 'பாரம்பரிய அறிஞர்') as storyteller, 
               COALESCE(h.region, 'தமிழ்நாடு') as story_region, 
               COALESCE(h.audio_path, '') as audio_path
        FROM dictionary_entries d
        LEFT JOIN heritage_records h ON d.story_id = h.id
        WHERE 1=1
    '''
    params = []

    if story_id:
        sql += " AND d.story_id = ?"
        params.append(story_id)

    if category and category.strip() and category.lower() != 'all':
        sql += " AND d.category = ?"
        params.append(category.strip())

    if review_status and review_status.strip() and review_status.lower() != 'all':
        sql += " AND d.review_status = ?"
        params.append(review_status.strip())

    if query and query.strip():
        q_term = f"%{query.strip()}%"
        sql += ''' AND (
            d.word LIKE ? OR
            d.normalized_word LIKE ? OR
            d.meaning_ta LIKE ? OR
            d.meaning_en LIKE ? OR
            d.contextual_meaning_ta LIKE ? OR
            d.example_sentence LIKE ? OR
            COALESCE(h.title, '') LIKE ?
        )'''
        params.extend([q_term, q_term, q_term, q_term, q_term, q_term, q_term])

    sql += " ORDER BY d.id DESC LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def update_dictionary_entry(entry_id, word=None, meaning_ta=None, meaning_en=None,
                            contextual_meaning_ta=None, example_sentence=None,
                            category=None, source_excerpt=None, start_seconds=None,
                            end_seconds=None, confidence=None, review_status=None):
    """Update fields of an existing dictionary entry."""
    existing = get_dictionary_entry(entry_id)
    if not existing:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    new_word = word.strip() if word is not None else existing['word']
    new_norm = normalize_tamil_word(new_word)
    new_m_ta = meaning_ta.strip() if meaning_ta is not None else existing['meaning_ta']
    new_m_en = meaning_en.strip() if meaning_en is not None else existing['meaning_en']
    new_ctx = contextual_meaning_ta.strip() if contextual_meaning_ta is not None else existing.get('contextual_meaning_ta', '')
    new_ex = example_sentence.strip() if example_sentence is not None else existing.get('example_sentence', '')
    new_cat = category.strip() if category is not None else existing.get('category', 'பாரம்பரிய அறிவு')
    new_src = source_excerpt.strip() if source_excerpt is not None else existing.get('source_excerpt', '')

    new_st = existing.get('start_seconds')
    if start_seconds is not None:
        new_st = float(start_seconds) if str(start_seconds).strip() != '' else None

    new_en = existing.get('end_seconds')
    if end_seconds is not None:
        new_en = float(end_seconds) if str(end_seconds).strip() != '' else None

    new_conf = existing.get('confidence')
    if confidence is not None:
        new_conf = float(confidence) if str(confidence).strip() != '' else None

    new_status = existing.get('review_status', 'pending_review')
    if review_status is not None:
        new_status = review_status if review_status in ('pending_review', 'verified', 'flagged') else new_status

    cursor.execute('''
        UPDATE dictionary_entries
        SET word = ?, normalized_word = ?, meaning_ta = ?, meaning_en = ?,
            contextual_meaning_ta = ?, example_sentence = ?, category = ?,
            source_excerpt = ?, start_seconds = ?, end_seconds = ?,
            confidence = ?, review_status = ?, updated_at = ?
        WHERE id = ?
    ''', (
        new_word, new_norm, new_m_ta, new_m_en,
        new_ctx, new_ex, new_cat,
        new_src, new_st, new_en,
        new_conf, new_status, now_iso,
        entry_id
    ))
    conn.commit()
    conn.close()
    return True


def delete_dictionary_entry(entry_id):
    """Delete a dictionary entry by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dictionary_entries WHERE id = ?", (entry_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def upsert_generated_dictionary_entries(story_id, entries):
    """
    Persist generated dictionary entries for a story.
    Protection rules:
    - Never overwrite human-reviewed entries (review_status == 'verified').
    - If entry already exists and is pending_review, update only empty fields or keep existing.
    - If entry does not exist, insert new.
    Returns: dict with counts {'inserted': N, 'updated': N, 'skipped': N}
    """
    if not entries:
        return {'inserted': 0, 'updated': 0, 'skipped': 0}

    # Fetch existing entries for this story
    existing_list = get_dictionary_entries_for_story(story_id)
    existing_by_norm = {e['normalized_word']: e for e in existing_list}

    inserted = 0
    updated = 0
    skipped = 0

    for item in entries:
        word = (item.get('word') or '').strip()
        if not word:
            continue

        norm = normalize_tamil_word(word)
        if not norm:
            continue

        meaning_ta = (item.get('meaning_ta') or '').strip()
        meaning_en = (item.get('meaning_en') or '').strip()
        ctx_ta = (item.get('contextual_meaning_ta') or '').strip()
        example = (item.get('example_sentence') or '').strip()
        category = (item.get('category') or 'பாரம்பரிய அறிவு').strip()
        excerpt = (item.get('source_excerpt') or '').strip()
        start_sec = item.get('start_seconds')
        end_sec = item.get('end_seconds')
        conf = item.get('confidence')

        if norm in existing_by_norm:
            rec = existing_by_norm[norm]
            if rec.get('review_status') == 'verified':
                # Human verified: strictly preserve, do not overwrite!
                skipped += 1
                continue
            else:
                # Update pending entry if new data provides better meanings
                update_dictionary_entry(
                    entry_id=rec['id'],
                    meaning_ta=meaning_ta or rec['meaning_ta'],
                    meaning_en=meaning_en or rec['meaning_en'],
                    contextual_meaning_ta=ctx_ta or rec.get('contextual_meaning_ta', ''),
                    example_sentence=example or rec.get('example_sentence', ''),
                    category=category or rec.get('category', 'பாரம்பரிய அறிவு'),
                    source_excerpt=excerpt or rec.get('source_excerpt', '')
                )
                updated += 1
        else:
            insert_dictionary_entry(
                story_id=story_id,
                word=word,
                meaning_ta=meaning_ta,
                meaning_en=meaning_en,
                contextual_meaning_ta=ctx_ta,
                example_sentence=example,
                category=category,
                source_excerpt=excerpt,
                start_seconds=start_sec,
                end_seconds=end_sec,
                confidence=conf,
                review_status='pending_review'
            )
            inserted += 1

    return {'inserted': inserted, 'updated': updated, 'skipped': skipped}


def get_dictionary_categories(story_id=None):
    """Return distinct categories present in the dictionary."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if story_id:
        cursor.execute("SELECT DISTINCT category FROM dictionary_entries WHERE story_id = ? AND category != '' ORDER BY category", (story_id,))
    else:
        cursor.execute("SELECT DISTINCT category FROM dictionary_entries WHERE category != '' ORDER BY category")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

