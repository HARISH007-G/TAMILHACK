import unittest
from unittest.mock import patch, MagicMock
import json

from app import app
import summary_service


class TestSummaryService(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_summary_service_empty_text(self):
        """Empty transcript to summary service should return failure response."""
        res1 = summary_service.generate_story_summary("")
        self.assertFalse(res1["success"])
        self.assertIn("சுருக்கம் உருவாக்கத் தமிழ் உரை தேவை", res1["error"])

        res2 = summary_service.generate_story_summary("   \n\t ")
        self.assertFalse(res2["success"])
        self.assertIn("சுருக்கம் உருவாக்கத் தமிழ் உரை தேவை", res2["error"])

    def test_parse_summary_response_json(self):
        """Verify parsing of valid JSON output with code fences."""
        raw_json_str = """```json
{
  "summary_ta": "இது ஒரு பாரம்பரிய பொங்கல் கொண்டாட்ட வாய்மொழி வரலாறு.",
  "summary_en": "This is an oral history of traditional Pongal celebrations.",
  "key_points": ["பொங்கல் திருவிழா", "மரபு உணவு"]
}
```"""
        result = summary_service._parse_summary_response(raw_json_str)
        self.assertIn("பொங்கல் கொண்டாட்ட", result["summary_ta"])
        self.assertIn("Pongal celebrations", result["summary_en"])
        self.assertEqual(len(result["key_points"]), 2)

    def test_parse_summary_response_fallback_text(self):
        """Verify fallback parsing when the model provides plain text with language labels."""
        raw_text = """தமிழ் சுருக்கம்:
பழைய தலைமுறையினர் ஆற்றில் மாட்டு வண்டியில் மணல் அள்ளிச் சென்ற நினைவுகள் மற்றும் தற்போதைய மாற்றங்கள் பற்றிய பகிர்வு.

English Summary:
An elderly villager recalls the bygone era of river sand transport by bullock carts and reflects on modern environmental changes."""
        result = summary_service._parse_summary_response(raw_text)
        self.assertTrue(len(result["summary_ta"]) > 10)
        self.assertTrue(len(result["summary_en"]) > 10)
        self.assertIn("மணல்", result["summary_ta"])
        self.assertIn("bullock carts", result["summary_en"])

    def test_parse_summary_response_truncated_json(self):
        """Verify robust parsing when response is cut off mid-JSON (e.g., token limit reached)."""
        truncated_raw = '''{
"summary_ta": "மதுரை என்பது தமிழ் வளர்த்த மாநகரம். அதன் பல பெயர்கள் உள்ளன, மீனாட்சி அம்மனின் கோயில் அதன் மையமாக உள்ளது. அங்கு வைகை ஆற்றங்கரையில் அமைந்துள்ள மதுரை தனது மக்கள் மத்தியில் ஒரு சமத்துவமான சூழலை வலியுறுத்துகிறது.",
"summary_en": "Madurai is a city that nurtured Tamil culture. It has multiple names, with the Meenakshi Amman Temple at its center. Located on the banks of the Vaigai River, Madurai promotes a sense of equality among its people.",
"key_points": [
"மதுரை தமிழ் வளர்த்த மாநகரம்",
"மீனாட்சி அம்மனின் கோயில் மதுரையின் ம'''
        result = summary_service._parse_summary_response(truncated_raw)
        # Must not contain raw JSON artifacts or braces
        self.assertNotIn('{', result["summary_ta"])
        self.assertNotIn('"summary_ta"', result["summary_ta"])
        self.assertIn("மதுரை என்பது தமிழ் வளர்த்த மாநகரம்", result["summary_ta"])
        self.assertIn("Madurai is a city that nurtured Tamil culture", result["summary_en"])
        self.assertEqual(result["key_points"], ["மதுரை தமிழ் வளர்த்த மாநகரம்"])

    @patch('summary_service.requests.post')
    def test_generate_story_summary_mocked_success(self, mock_post):
        """Test full summary generation with mocked NVIDIA API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "summary_ta": "கிராமத்து மூதாட்டி நாட்டுப்புறக் கதைகளை நினைவு கூறுகிறார்.",
                            "summary_en": "A village elder recounts traditional folk tales.",
                            "key_points": ["நாட்டுப்புறக் கலைகள்", "பண்டைய சடங்குகள்"]
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        result = summary_service.generate_story_summary("முன்னொரு காலத்திலே ஒரு பெரிய ஆலமரம் இருந்துச்சாம்...")
        self.assertTrue(result["success"])
        self.assertIn("கிராமத்து மூதாட்டி", result["summary_ta"])
        self.assertIn("village elder", result["summary_en"])
        self.assertEqual(len(result["key_points"]), 2)

    def test_api_summarize_missing_data(self):
        """API should return 400 when transcript is missing or blank."""
        resp = self.app.post('/api/summarize', json={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("சுருக்கம் உருவாக்கத் தமிழ் உரை தேவை", data["error"])

        resp2 = self.app.post('/api/summarize', json={"transcript": "   "})
        self.assertEqual(resp2.status_code, 400)

    @patch('summary_service.generate_story_summary')
    def test_api_summarize_success(self, mock_gen):
        """API should return 200 and formatted summary on success."""
        mock_gen.return_value = {
            "success": True,
            "summary_ta": "பாரம்பரிய விவசாய முறைகள் பற்றிய விளக்கம்.",
            "summary_en": "Explanation of traditional agricultural methods.",
            "key_points": ["ஏர்பூட்டுதல்", "மழைநீர் சேகரிப்பு"]
        }

        resp = self.app.post('/api/summarize', json={
            "transcript": "எங்க காலத்துல ஏர் பூட்டி விவசாயம் செஞ்சோம். மழை வரும்போது வாய்க்கால்களை அடைப்போம்."
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["summary_ta"], "பாரம்பரிய விவசாய முறைகள் பற்றிய விளக்கம்.")
        self.assertEqual(data["summary_en"], "Explanation of traditional agricultural methods.")
        self.assertEqual(len(data["key_points"]), 2)

    @patch('summary_service.generate_story_summary')
    def test_api_summarize_failure(self, mock_gen):
        """API should return 502 with clear error message when summarizer fails."""
        mock_gen.side_effect = RuntimeError("NVIDIA API timeout")

        resp = self.app.post('/api/summarize', json={
            "transcript": "ஏதோ ஒரு உரை"
        })
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("NVIDIA API timeout", data["error"])

    @patch('summary_service.generate_story_summary')
    def test_api_summarize_service_error_flag(self, mock_gen):
        """API should return 502 when summary service returns success: False."""
        mock_gen.return_value = {
            "success": False,
            "error": "NVIDIA API அங்கீகாரப் பிழை (401 Unauthorized)"
        }

        resp = self.app.post('/api/summarize', json={
            "transcript": "ஏதோ ஒரு உரை"
        })
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("401 Unauthorized", data["error"])


if __name__ == '__main__':
    unittest.main()
