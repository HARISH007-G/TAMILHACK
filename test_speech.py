"""
Unit and Integration Tests for Speech-to-Text Pipeline, Audio Storage & Serverless Resilience
MARAPOLI (மரபொலி) — Tamil Oral Heritage Platform
"""

import os
import io
import wave
import struct
import unittest
from unittest.mock import patch, MagicMock

import app as flask_app
import speech_service


def create_dummy_wav(duration_seconds=1, sample_rate=16000, num_channels=1):
    """Creates an in-memory 16-bit PCM WAV byte stream for testing."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(num_channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        # Generate silence or simple sine tone
        num_frames = int(sample_rate * duration_seconds)
        data = struct.pack(f'<{num_frames * num_channels}h', *([0] * (num_frames * num_channels)))
        w.writeframes(data)
    buf.seek(0)
    return buf.getvalue()


class TestSpeechPipeline(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        self.client = flask_app.app.test_client()

    def test_get_audio_upload_dir_local(self):
        """Ensure get_audio_upload_dir returns an existing, writable directory."""
        upload_dir = flask_app.get_audio_upload_dir()
        self.assertTrue(os.path.exists(upload_dir))
        self.assertTrue(os.path.isdir(upload_dir))

    @patch.dict(os.environ, {'VERCEL': '1'})
    def test_get_audio_upload_dir_serverless(self):
        """Under serverless env (VERCEL=1), upload directory must point to /tmp or temp dir."""
        upload_dir = flask_app.get_audio_upload_dir()
        self.assertTrue(upload_dir.startswith('/tmp') or 'temp' in upload_dir.lower() or 'tmp' in upload_dir.lower())

    def test_is_pcm_wav_valid(self):
        """is_pcm_wav should return True for standard 16kHz mono 16-bit WAV."""
        wav_bytes = create_dummy_wav(duration_seconds=0.5, sample_rate=16000, num_channels=1)
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            with open(path, 'wb') as f:
                f.write(wav_bytes)
            self.assertTrue(speech_service.is_pcm_wav(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_is_pcm_wav_invalid(self):
        """is_pcm_wav should return False for non-WAV data."""
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        try:
            with open(path, 'wb') as f:
                f.write(b'not a real wave header')
            self.assertFalse(speech_service.is_pcm_wav(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_split_wav_into_chunks(self):
        """split_wav_into_chunks should split audio longer than max_seconds."""
        wav_bytes = create_dummy_wav(duration_seconds=3, sample_rate=16000, num_channels=1)
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            with open(path, 'wb') as f:
                f.write(wav_bytes)
            # Split with 1 second per chunk
            chunks = speech_service.split_wav_into_chunks(path, max_seconds_per_chunk=1)
            self.assertGreater(len(chunks), 1)
            for c in chunks:
                if c != path and os.path.exists(c):
                    os.remove(c)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_api_audio_serving(self):
        """GET /api/audio/<filename> should serve seeded audio file."""
        resp = self.client.get('/api/audio/story_rec_1792078624591.webm')
        self.assertEqual(resp.status_code, 200)

    def test_api_audio_not_found(self):
        """GET /api/audio/<non_existent> should return 404."""
        resp = self.client.get('/api/audio/completely_non_existent_file.webm')
        self.assertEqual(resp.status_code, 404)

    def test_api_transcribe_missing_audio(self):
        """POST /api/transcribe without audio file must return HTTP 400."""
        resp = self.client.post('/api/transcribe', data={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_api_transcribe_empty_file(self):
        """POST /api/transcribe with an empty filename must return HTTP 400."""
        data = {'audio': (io.BytesIO(b''), '')}
        resp = self.client.post('/api/transcribe', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    def test_api_transcribe_unsupported_extension(self):
        """POST /api/transcribe with unsupported extension (.exe) must return HTTP 400."""
        data = {'audio': (io.BytesIO(b'executable content'), 'malicious.exe')}
        resp = self.client.post('/api/transcribe', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ஆதரிக்கப்படாத', resp.get_json()['error'])

    @patch('speech_service.transcribe_tamil_audio')
    def test_api_transcribe_mocked_success(self, mock_transcribe):
        """POST /api/transcribe should return audio_url, text, and extracted metadata on success."""
        mock_transcribe.return_value = {
            "success": True,
            "text": "மதுரை மீனாட்சி அம்மன் கோவிலில் தைப்பொங்கல் விழா சிறப்பாக நடைபெற்றது.",
            "provider": "Google Speech Recognition (தமிழ் ta-IN)",
            "error": None
        }
        wav_bytes = create_dummy_wav(duration_seconds=1)
        data = {'audio': (io.BytesIO(wav_bytes), 'test_sample.wav')}
        resp = self.client.post('/api/transcribe', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        res_json = resp.get_json()
        self.assertTrue(res_json['success'])
        self.assertIn("மதுரை", res_json['text'])
        self.assertIn('/api/audio/', res_json['audio_url'])
        # Extracted metadata should be populated
        self.assertIsNotNone(res_json.get('extracted_metadata'))


if __name__ == '__main__':
    unittest.main()
