"""
Automated Test Suite for Tamil Memory Dictionary (தமிழ்ச்சொல் நினைவகம்)
Tests database persistence, NVIDIA API service mocking, structured data contracts,
search, review workflows, duplicate protection, and Flask API endpoints.
"""

import os
import sys
import json
import unittest
import requests
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import dictionary_service
from app import app


class TestDatabaseDictionary(unittest.TestCase):
    """Unit tests for SQLite database operations and schema integrity."""

    def setUp(self):
        # Use an in-memory or isolated test database
        database.init_db()

        # Insert a clean test story
        self.story_id = database.insert_record(
            title="களத்துமேடு பாரம்பரிய உழவு நினைவுகள்",
            source_type="audio",
            transcript="எங்கள் ஊரில் மாடுகளைக் கொண்டு கதிர் அடித்த களத்துமேடு இன்னும் நினைவில் இருக்கிறது. மூட்டு வலிக்கு முடக்கத்தான் கீரை சாப்பிடுவோம்.",
            storyteller="முத்துசாமி பெரியவர்",
            region="பொள்ளாச்சி, கோயம்புத்தூர்",
            topic="பாரம்பரிய விவசாயம்",
            description="பழைய தலைமுறையின் விவசாய முறைகள்"
        )

    def tearDown(self):
        # Clean up test record and associated entries
        database.delete_record(self.story_id)

    def test_schema_and_original_transcript_preservation(self):
        """Verify original_transcript column exists and is preserved upon transcript edits."""
        rec = database.get_record(self.story_id)
        self.assertIsNotNone(rec)
        self.assertIn('original_transcript', rec)
        self.assertEqual(rec['original_transcript'], rec['transcript'])

        # Update the transcript
        updated_text = "திருத்தப்பட்ட தமிழ் உரை: களத்துமேடு மற்றும் முடக்கத்தான் கீரை."
        database.update_record(self.story_id, transcript=updated_text)

        rec_after = database.get_record(self.story_id)
        self.assertEqual(rec_after['transcript'], updated_text)
        # Original transcript MUST remain untouched
        self.assertNotEqual(rec_after['original_transcript'], updated_text)
        self.assertIn("களத்துமேடு இன்னும் நினைவில் இருக்கிறது", rec_after['original_transcript'])

    def test_insert_and_get_dictionary_entry(self):
        """Test inserting a rich dictionary entry with Tamil Unicode."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="களத்துமேடு",
            meaning_ta="அறுத்த நெற்கதிர்களைப் பரப்பி தானியங்களைப் பிரித்தெடுக்கும் திறந்தவெளி இடம்.",
            meaning_en="A traditional open-air threshing floor used to separate grain from harvested stalks.",
            contextual_meaning_ta="முற்காலத்தில் மாடுகளைக் கொண்டு தானியங்களை உதிர்த்த பாரம்பரியத் தளம்.",
            example_sentence="களத்துமேட்டில் நெல் மணிகள் குவித்து வைக்கப்பட்டிருந்தன.",
            category="விவசாயம் & உழவுக் கருவிகள்",
            source_excerpt="எங்கள் ஊரில் மாடுகளைக் கொண்டு கதிர் அடித்த களத்துமேடு இன்னும் நினைவில் இருக்கிறது.",
            start_seconds=None,
            end_seconds=None,
            confidence=0.95,
            review_status="pending_review"
        )
        self.assertIsInstance(entry_id, int)

        entry = database.get_dictionary_entry(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['word'], "களத்துமேடு")
        self.assertEqual(entry['normalized_word'], "களத்துமேடு")
        self.assertEqual(entry['story_id'], self.story_id)
        self.assertIsNone(entry['start_seconds'])  # No fabricated timestamps
        self.assertIsNone(entry['end_seconds'])
        self.assertEqual(entry['review_status'], "pending_review")

    def test_update_and_verify_entry(self):
        """Test updating entry details and marking as verified."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="முடக்கத்தான்",
            meaning_ta="மூட்டுவலி நிவாரணி",
            meaning_en="Herb for joint pain",
            review_status="pending_review"
        )

        success = database.update_dictionary_entry(
            entry_id=entry_id,
            meaning_ta="மூட்டுவலியைப் போக்கும் ஒரு மருத்துவக் கொடி வகை.",
            review_status="verified"
        )
        self.assertTrue(success)

        entry = database.get_dictionary_entry(entry_id)
        self.assertEqual(entry['meaning_ta'], "மூட்டுவலியைப் போக்கும் ஒரு மருத்துவக் கொடி வகை.")
        self.assertEqual(entry['review_status'], "verified")

    def test_upsert_protection_of_verified_entries(self):
        """Ensure repeated generation does NOT overwrite human-verified entries."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="முடக்கத்தான்",
            meaning_ta="மனிதரால் சரிபார்க்கப்பட்ட மிகத் துல்லியமான விளக்கம்.",
            meaning_en="Human verified precise definition.",
            review_status="verified"
        )

        # AI generated batch attempts to redefine the same word
        ai_generated_batch = [
            {
                "word": "முடக்கத்தான்",
                "meaning_ta": "AI உருவாக்கிய புதிய பொதுவான விளக்கம்.",
                "meaning_en": "AI generic definition.",
                "category": "சித்த மருத்துவம்"
            },
            {
                "word": "களத்துமேடு",
                "meaning_ta": "தானியம் பிரிக்கும் தளம்.",
                "meaning_en": "Threshing floor.",
                "category": "விவசாயம்"
            }
        ]

        stats = database.upsert_generated_dictionary_entries(self.story_id, ai_generated_batch)
        self.assertEqual(stats['skipped'], 1)  # "முடக்கத்தான்" was verified and protected!
        self.assertEqual(stats['inserted'], 1)  # "களத்துமேடு" was inserted

        # Check that the human verified meaning was strictly preserved
        entry = database.get_dictionary_entry(entry_id)
        self.assertEqual(entry['meaning_ta'], "மனிதரால் சரிபார்க்கப்பட்ட மிகத் துல்லியமான விளக்கம்.")
        self.assertEqual(entry['review_status'], "verified")

    def test_search_dictionary_entries(self):
        """Test search across Tamil script and English definitions."""
        database.insert_dictionary_entry(
            story_id=self.story_id,
            word="கதிர்",
            meaning_ta="தானியம் நிறைந்த நெல் பகுதி.",
            meaning_en="Ear of grain or paddy spikelet.",
            category="விவசாயம்"
        )

        # Search by Tamil word
        res_ta = database.search_dictionary_entries(query="கதிர்")
        self.assertTrue(any(e['word'] == 'கதிர்' for e in res_ta))

        # Search by English meaning (case-insensitive)
        res_en = database.search_dictionary_entries(query="SPIKELET")
        self.assertTrue(any(e['word'] == 'கதிர்' for e in res_en))

        # Non-matching search
        res_none = database.search_dictionary_entries(query="சொல்இல்லைXYZ")
        self.assertEqual(len(res_none), 0)

    def test_delete_dictionary_entry(self):
        """Test deleting an entry."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="தற்காலிகச் சொல்",
            meaning_ta="நீக்கப்பட வேண்டிய சொல்",
            meaning_en="Temporary word to delete"
        )
        self.assertTrue(database.delete_dictionary_entry(entry_id))
        self.assertIsNone(database.get_dictionary_entry(entry_id))


class TestDictionaryService(unittest.TestCase):
    """Unit tests for NVIDIA API service parsing, sanitization, and error handling."""

    def test_extract_json_from_markdown_codeblock(self):
        """Test extracting JSON from LLM markdown code blocks."""
        raw_output = """Here are the extracted Tamil words:
```json
[
  {
    "word": "முடக்கத்தான்",
    "meaning_ta": "மூட்டுவலியைப் போக்கும் மூலிகை.",
    "meaning_en": "Medicinal herb for joint pain.",
    "category": "சித்த மருத்துவம்"
  }
]
```
Hope this is helpful."""
        entries = dictionary_service.extract_json_from_model_output(raw_output)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['word'], "முடக்கத்தான்")

    def test_extract_json_from_wrapped_object(self):
        """Test extracting JSON from wrapped object with 'entries' or 'words' key."""
        raw_output = '{"entries": [{"word": "ஏர்க்கலப்பை", "meaning_ta": "உழவுக் கருவி", "meaning_en": "Wooden plow"}]}'
        entries = dictionary_service.extract_json_from_model_output(raw_output)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['word'], "ஏர்க்கலப்பை")

    def test_malformed_json_handling(self):
        """Ensure malformed output doesn't crash the parser."""
        raw_output = "I could not find any specific words. Here is plain text without JSON."
        entries = dictionary_service.extract_json_from_model_output(raw_output)
        self.assertEqual(entries, [])

    def test_sanitize_entry_missing_timestamps(self):
        """Ensure missing timestamps are NOT fabricated."""
        raw_entry = {
            "word": "களத்துமேடு",
            "meaning_ta": "தானியம் அடிக்கும் இடம்",
            "meaning_en": "Threshing floor"
        }
        transcript = "எங்கள் ஊரில் களத்துமேடு இருந்தது."
        san = dictionary_service.sanitize_dictionary_entry(raw_entry, transcript)
        self.assertIsNotNone(san)
        self.assertIsNone(san['start_seconds'])
        self.assertIsNone(san['end_seconds'])
        self.assertEqual(san['source_excerpt'].strip('.'), transcript.strip('.'))

    def test_empty_transcript_handling(self):
        """Ensure empty transcript returns a clean error without calling the API."""
        result = dictionary_service.generate_dictionary_from_transcript("")
        self.assertFalse(result['success'])
        self.assertIn("தமிழ் உரை தேவை", result['error'])

    @patch('requests.post')
    def test_mocked_nvidia_successful_generation(self, mock_post):
        """Test full generation flow with mocked 200 OK from NVIDIA API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps([
                            {
                                "word": "முடக்கத்தான்",
                                "meaning_ta": "மூட்டுவலியைப் போக்கும் மூலிகைக் கொடி.",
                                "meaning_en": "Medicinal herb for joint pain.",
                                "contextual_meaning_ta": "மூட்டு வலிக்கு நிவாரணமாகப் பயன்படுகிறது.",
                                "category": "சித்த மருத்துவம்",
                                "source_excerpt": "மூட்டு வலிக்கு முடக்கத்தான் கீரை சாப்பிடுவோம்."
                            }
                        ])
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Temporarily set API key for test
        with patch.dict(os.environ, {'NVIDIA_API_KEY': 'test_mock_nvapi_key_123'}):
            res = dictionary_service.generate_dictionary_from_transcript(
                "மூட்டு வலிக்கு முடக்கத்தான் கீரை சாப்பிடுவோம்."
            )
            self.assertTrue(res['success'])
            self.assertEqual(res['count'], 1)
            self.assertEqual(res['entries'][0]['word'], "முடக்கத்தான்")

    @patch('requests.post')
    def test_mocked_nvidia_auth_failure(self, mock_post):
        """Test handling of 401 Unauthorized from NVIDIA API."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {'NVIDIA_API_KEY': 'invalid_mock_key'}):
            res = dictionary_service.generate_dictionary_from_transcript("தமிழ் உரை")
            self.assertFalse(res['success'])
            self.assertIn("401", res['error'])

    @patch('requests.post')
    def test_mocked_nvidia_timeout(self, mock_post):
        """Test handling of request timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        with patch.dict(os.environ, {'NVIDIA_API_KEY': 'test_mock_key'}):
            res = dictionary_service.generate_dictionary_from_transcript("தமிழ் உரை")
            self.assertFalse(res['success'])
            self.assertIn("Timeout", res['error'])


class TestFlaskDictionaryEndpoints(unittest.TestCase):
    """Integration tests for Flask Dictionary API endpoints."""

    def setUp(self):
        self.client = app.test_client()
        database.init_db()
        self.story_id = database.insert_record(
            title="சித்த மருத்துவப் பாரம்பரியக் குறிப்புகள்",
            source_type="audio",
            transcript="மூட்டு வலிக்கு முடக்கத்தான் கீரை மற்றும் வாதநாராயணன் இலை நல்லது.",
            storyteller="பாட்டி",
            region="மதுரை",
            topic="சித்த மருத்துவம்"
        )

    def tearDown(self):
        database.delete_record(self.story_id)

    def test_get_story_dictionary_endpoint(self):
        """Test GET /api/stories/<id>/dictionary."""
        # Non-existent story
        resp404 = self.client.get('/api/stories/999999/dictionary')
        self.assertEqual(resp404.status_code, 404)

        # Existing story initially empty
        resp = self.client.get(f'/api/stories/{self.story_id}/dictionary')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 0)

    def test_add_manual_entry_endpoint(self):
        """Test POST /api/stories/<id>/dictionary/entries."""
        payload = {
            "word": "வாதநாராயணன்",
            "meaning_ta": "வாத நோய்களைத் தீர்க்கும் ஒரு மரத்தின் இலை.",
            "meaning_en": "Leaves of Delonix elata used in Siddha medicine for arthritis.",
            "category": "சித்த மருத்துவம் & மூலிகைகள்",
            "source_excerpt": "வாதநாராயணன் இலை நல்லது."
        }
        resp = self.client.post(
            f'/api/stories/{self.story_id}/dictionary/entries',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('id', data)

        # Missing word should fail with 400
        bad_resp = self.client.post(
            f'/api/stories/{self.story_id}/dictionary/entries',
            data=json.dumps({"meaning_ta": "விளக்கம் மட்டும்"}),
            content_type='application/json'
        )
        self.assertEqual(bad_resp.status_code, 400)

    @patch('dictionary_service.generate_dictionary_from_transcript')
    def test_generate_dictionary_endpoint(self, mock_gen):
        """Test POST /api/stories/<id>/dictionary/generate."""
        mock_gen.return_value = {
            "success": True,
            "count": 1,
            "entries": [
                {
                    "word": "முடக்கத்தான்",
                    "meaning_ta": "மூட்டுவலியைப் போக்கும் கீரை.",
                    "meaning_en": "Herb for joint pain.",
                    "category": "சித்த மருத்துவம்",
                    "source_excerpt": "மூட்டு வலிக்கு முடக்கத்தான் கீரை நல்லது."
                }
            ],
            "model": "meta/llama-3.2-11b-vision-instruct",
            "error": None
        }

        resp = self.client.post(f'/api/stories/{self.story_id}/dictionary/generate')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['entries'][0]['word'], "முடக்கத்தான்")

    def test_patch_and_verify_entry_endpoint(self):
        """Test PATCH /api/dictionary/entries/<entry_id>."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="முடக்கத்தான்",
            meaning_ta="ஆரம்ப விளக்கம்",
            meaning_en="Initial definition",
            review_status="pending_review"
        )

        resp = self.client.patch(
            f'/api/dictionary/entries/{entry_id}',
            data=json.dumps({"review_status": "verified"}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['entry']['review_status'], "verified")

    def test_search_endpoint(self):
        """Test GET /api/dictionary/search."""
        database.insert_dictionary_entry(
            story_id=self.story_id,
            word="முடக்கத்தான்",
            meaning_ta="மருத்துவக் கொடி",
            meaning_en="Balloon vine herb",
            category="சித்த மருத்துவம்"
        )

        # Search by Tamil query
        resp_ta = self.client.get('/api/dictionary/search?q=முடக்கத்தான்')
        self.assertEqual(resp_ta.status_code, 200)
        self.assertGreater(resp_ta.get_json()['count'], 0)

        # Search by English query
        resp_en = self.client.get('/api/dictionary/search?q=balloon')
        self.assertEqual(resp_en.status_code, 200)
        self.assertGreater(resp_en.get_json()['count'], 0)

    def test_delete_entry_endpoint(self):
        """Test DELETE /api/dictionary/entries/<entry_id>."""
        entry_id = database.insert_dictionary_entry(
            story_id=self.story_id,
            word="நீக்கப்படவேண்டியது",
            meaning_ta="விளக்கம்",
            meaning_en="Definition"
        )
        del_resp = self.client.delete(f'/api/dictionary/entries/{entry_id}')
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.get_json()['success'])

        # Deleting again should return 404
        del_resp2 = self.client.delete(f'/api/dictionary/entries/{entry_id}')
        self.assertEqual(del_resp2.status_code, 404)

    def test_export_includes_dictionary(self):
        """Verify TXT and JSON exports include dictionary entries."""
        database.insert_dictionary_entry(
            story_id=self.story_id,
            word="முடக்கத்தான்",
            meaning_ta="மூட்டுவலி நிவாரணி",
            meaning_en="Joint pain remedy"
        )

        # JSON Export
        resp_json = self.client.get(f'/api/export/{self.story_id}/json')
        self.assertEqual(resp_json.status_code, 200)
        data = json.loads(resp_json.data.decode('utf-8'))
        self.assertIn('dictionary_entries', data)
        self.assertEqual(len(data['dictionary_entries']), 1)
        self.assertEqual(data['dictionary_entries'][0]['word'], "முடக்கத்தான்")

        # TXT Export
        resp_txt = self.client.get(f'/api/export/{self.story_id}/txt')
        self.assertEqual(resp_txt.status_code, 200)
        txt = resp_txt.data.decode('utf-8')
        self.assertIn("சொல் நினைவகம்", txt)
        self.assertIn("முடக்கத்தான்", txt)


if __name__ == '__main__':
    unittest.main()
