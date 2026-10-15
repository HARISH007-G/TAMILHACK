"""
Automated Test Suite for Dialect DNA (வட்டார மொழி அடையாளம்)
Testing evidence-based Tamil dialect and linguistic analysis service.
"""

import unittest
from unittest.mock import patch, MagicMock
import json

from app import app
import dialect_service


class TestDialectDNAService(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_empty_transcript_service(self):
        """Empty or whitespace-only transcript must return validation failure."""
        res1 = dialect_service.analyze_dialect("")
        self.assertFalse(res1["success"])
        self.assertEqual(res1["status"], "empty_input")
        self.assertIn("தமிழ் உரை தேவை", res1["error"])

        res2 = dialect_service.analyze_dialect("   \n\t  ")
        self.assertFalse(res2["success"])
        self.assertEqual(res2["status"], "empty_input")

        res3 = dialect_service.analyze_dialect(None)
        self.assertFalse(res3["success"])
        self.assertEqual(res3["status"], "empty_input")

    def test_short_transcript_insufficient_evidence(self):
        """Very short inputs must safely return insufficient_evidence without calling upstream API."""
        res = dialect_service.analyze_dialect("வணக்கம் ஐயா")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "insufficient_evidence")
        self.assertIn("குறுகியதாக", res["overallAssessment"])
        self.assertEqual(len(res["radarMetrics"]), 5)
        self.assertTrue(len(res["limitations"]) >= 1)

    def test_empty_transcript_api_endpoint(self):
        """POST /api/dialect-dna with empty payload must return HTTP 400."""
        resp = self.client.post('/api/dialect-dna', json={"transcript": ""})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "empty_input")
        # Ensure no sensitive credentials leak in error response
        self.assertNotIn("Bearer", resp.get_data(as_text=True))
        self.assertNotIn("api_key", resp.get_data(as_text=True))

    def test_alias_endpoint(self):
        """POST /api/dialect/analyze should work as an alias route."""
        resp = self.client.post('/api/dialect/analyze', json={"transcript": "   "})
        self.assertEqual(resp.status_code, 400)

    @patch('dialect_service.requests.post')
    def test_mocked_colloquial_analysis_success(self, mock_post):
        """Test representative colloquial transcript analysis with mocked NVIDIA API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "status": "success",
                        "overallAssessment": "இவ்வுரையில் கொங்கு மண்டலத்திற்குரிய விளிச் சொற்களும் மரியாதைப் பின்னொட்டுகளும் தெளிவாகக் காணப்படுகின்றன.",
                        "regionalIndicators": [{
                            "region": "Kongu Tamil",
                            "region_ta": "கொங்குத் தமிழ்",
                            "assessment": "possible_indicator",
                            "confidenceLabel": "சாத்தியமான அடையாளம்",
                            "evidence": [{
                                "text": "நாங்க ஊருக்கு வாங்கொன்னு சொன்னோம்",
                                "observation": "இரண்டாம் நபர் மரியாதை பன்மை பின்னொட்டு '-ங்கொ' பயன்பாடு.",
                                "interpretation": "கொங்கு வட்டார வழக்கின் பொதுவான உருபனியல் பண்பு.",
                                "limitations": "சில மேற்கு மாவட்டங்களிலும் இவ்வழக்கு காணப்படலாம்."
                            }]
                        }],
                        "linguisticFeatures": [{
                            "category": "morphological_pattern",
                            "label_ta": "மரியாதைப் பின்னொட்டு",
                            "observation": "-ங்கொ விகுதி",
                            "examples": [{"text": "வாங்கொன்னு சொன்னோம்", "explanation": "வழக்கு"}]
                        }],
                        "distinctiveVocabulary": [{
                            "word": "வாங்கொ",
                            "context": "நாங்க ஊருக்கு வாங்கொன்னு சொன்னோம்",
                            "meaning": "வாருங்கள் என்பதன் பேச்சு வழக்கு",
                            "regionalAssociation": "கொங்கு",
                            "evidenceLevel": "observed",
                            "explanation": "மரியாதை விளி"
                        }],
                        "radarMetrics": [
                            {"category": "colloquial_lexicon", "score": 75, "evidenceCount": 3},
                            {"category": "morphological_markers", "score": 85, "evidenceCount": 2},
                            {"category": "discourse_particles", "score": 60, "evidenceCount": 2},
                            {"category": "regional_indicators", "score": 80, "evidenceCount": 2},
                            {"category": "syntactic_patterns", "score": 65, "evidenceCount": 1}
                        ],
                        "limitations": [
                            "ஒலிப்பதிவு இல்லாமல் எழுத்து உரை மூலம் மட்டுமே ஆய்வு செய்யப்பட்டுள்ளது.",
                            "வட்டார எல்லைகளில் பிற மாவட்ட வழக்குகளின் கலப்பு இருக்கலாம்."
                        ]
                    })
                }
            }]
        }
        mock_post.return_value = mock_resp

        transcript = "நாங்க நேற்று ஊருக்குப் போயிருந்தோம். அங்கே எல்லோரும் வாங்கொன்னு அன்பா வரவேற்றாங்க."
        result = dialect_service.analyze_dialect(transcript)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "success")
        self.assertIn("கொங்கு மண்டலத்திற்குரிய", result["overallAssessment"])
        self.assertEqual(len(result["regionalIndicators"]), 1)
        self.assertEqual(result["regionalIndicators"][0]["region"], "Kongu Tamil")
        self.assertEqual(len(result["radarMetrics"]), 5)
        self.assertEqual(len(result["distinctiveVocabulary"]), 1)
        self.assertEqual(result["distinctiveVocabulary"][0]["word"], "வாங்கொ")

    @patch('dialect_service.requests.post')
    def test_mocked_formal_tamil_neutral_assessment(self, mock_post):
        """Formal Tamil passage must not fabricate unsupported regional indicators."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "status": "success",
                        "overallAssessment": "இவ்வுரை செந்தமிழ் மற்றும் பொதுத் தமிழ் உரைநடையில் அமைந்துள்ளது.",
                        "regionalIndicators": [{
                            "region": "Formal / Literary Tamil",
                            "region_ta": "பொதுத் தமிழ் / இலக்கிய நடை",
                            "assessment": "shared_feature",
                            "confidenceLabel": "பொது வழக்கு",
                            "evidence": [{
                                "text": "தமிழ் மொழியின் தொன்மையும் இலக்கியச் சிறப்பும் போற்றத்தக்கவை",
                                "observation": "எழுத்துத் தமிழ் சொற்கள் மற்றும் இலக்கண நடை.",
                                "interpretation": "வட்டாரச் சார்பற்ற பொதுத் தமிழ்.",
                                "limitations": "குறிப்பிட்ட எந்த ஒரு வட்டாரத்தையும் குறிக்கவில்லை."
                            }]
                        }],
                        "linguisticFeatures": [],
                        "distinctiveVocabulary": [],
                        "radarMetrics": [
                            {"category": "colloquial_lexicon", "score": 15, "evidenceCount": 0},
                            {"category": "morphological_markers", "score": 20, "evidenceCount": 0},
                            {"category": "discourse_particles", "score": 10, "evidenceCount": 0},
                            {"category": "regional_indicators", "score": 10, "evidenceCount": 0},
                            {"category": "syntactic_patterns", "score": 70, "evidenceCount": 1}
                        ],
                        "limitations": ["எந்த ஒரு வட்டார வழக்குச் சாயலும் காணப்படவில்லை."]
                    })
                }
            }]
        }
        mock_post.return_value = mock_resp

        transcript = "தமிழ் மொழியின் தொன்மையும் இலக்கியச் சிறப்பும் உலகெங்கும் வாழும் தமிழர்களால் போற்றத்தக்கவை."
        result = dialect_service.analyze_dialect(transcript)

        self.assertTrue(result["success"])
        self.assertEqual(result["regionalIndicators"][0]["region"], "Formal / Literary Tamil")
        self.assertEqual(result["regionalIndicators"][0]["assessment"], "shared_feature")

    @patch('dialect_service.requests.post')
    def test_malformed_json_fallback(self, mock_post):
        """When upstream returns non-JSON or broken text, service must gracefully salvage or fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "இங்கே சில குறிப்புகள் உள்ளன. எந்த முறையான JSON அமைப்பும் இல்லை."
                }
            }]
        }
        mock_post.return_value = mock_resp

        transcript = "நாங்கள் மதுரையில் மீனாட்சி அம்மன் கோவிலுக்கு சென்றோம். அங்கே பல மக்கள் கூடினர்."
        result = dialect_service.analyze_dialect(transcript)

        self.assertTrue(result["success"])
        self.assertTrue(len(result["overallAssessment"]) >= 10)
        self.assertEqual(len(result["radarMetrics"]), 5)

    @patch('dialect_service.requests.post')
    def test_upstream_timeout_error(self, mock_post):
        """Test upstream timeout returns clean user-facing error."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        transcript = "நாங்க சின்ன வயசுல வயக்காட்டுக்கு போவோம். அங்கே நிறைய நெல் விளையும்."
        result = dialect_service.analyze_dialect(transcript)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "network_error")
        self.assertIn("பதில் காலம் முடிந்தது", result["error"])

    @patch('dialect_service.requests.post')
    def test_upstream_401_auth_error(self, mock_post):
        """Test upstream 401 returns clean authentication error without leaking keys."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        transcript = "நாங்க சின்ன வயசுல வயக்காட்டுக்கு போவோம். அங்கே நிறைய நெல் விளையும்."
        result = dialect_service.analyze_dialect(transcript)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "auth_error")
        self.assertIn("அங்கீகாரப் பிழை", result["error"])

    def test_evidence_verification_helper(self):
        """Verify that fuzzy and verbatim phrase matching checks evidence strictly."""
        text = "மதுரை வீதிகளில் அம்புட்டு சனக்கூட்டம் இருந்தது."
        self.assertTrue(dialect_service._fuzzy_phrase_match("அம்புட்டு சனக்கூட்டம்", text))
        self.assertFalse(dialect_service._fuzzy_phrase_match("கொங்கு மாடு", text))


if __name__ == '__main__':
    unittest.main()
