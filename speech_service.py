"""
MARAPOLI (மரபொலி) — Speech-to-Text Service for Tamil Oral History
Preserving Tamil oral heritage, regional dialects, and elders' stories.

Supports:
1. Groq Whisper (whisper-large-v3) - High accuracy oral Tamil dialect transcription
2. Google Gemini 1.5 Flash - Multimodal Tamil oral transcription
3. OpenAI Whisper (whisper-1) - Cloud Whisper API
4. Google Speech Recognition (ta-IN) - Built-in zero-configuration provider with FFmpeg conversion
"""

import os
import io
import sys
import wave
import json
import base64
import shutil
import tempfile
import subprocess
import requests

# ---------------------------------------------------------------------------
# 1. Environment Loading (.env support)
# ---------------------------------------------------------------------------
def load_env_file():
    """Load variables from .env file without overwriting existing environment."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
            return
    except ImportError:
        pass

    # Manual fallback parser
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

load_env_file()


# ---------------------------------------------------------------------------
# 2. FFmpeg Executable Discovery
# ---------------------------------------------------------------------------
def get_ffmpeg_executable():
    """
    Locate a functional FFmpeg executable across:
    1. /tmp/ffmpeg (if already staged and executable in serverless)
    2. imageio_ffmpeg bundled binary directly from package directory (staged to /tmp on serverless Linux)
    3. System PATH (ffmpeg / ffmpeg.exe)
    4. Common Windows / Linux install paths
    """
    tmp_ffmpeg = '/tmp/ffmpeg'
    if os.path.exists(tmp_ffmpeg) and os.access(tmp_ffmpeg, os.X_OK):
        return tmp_ffmpeg

    candidate = None
    # 1. Direct discovery from imageio_ffmpeg package directory without triggering _is_valid_exe prematurely
    try:
        import imageio_ffmpeg._utils as u
        bin_dir = u._get_bin_dir()
        plat = u.get_platform()
        fname = u.FNAME_PER_PLATFORM.get(plat, "")
        if fname:
            bundled = os.path.join(bin_dir, fname)
            if os.path.exists(bundled):
                candidate = bundled
    except Exception:
        pass

    if not candidate:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                candidate = exe
        except Exception:
            pass

    if not candidate:
        candidate = shutil.which('ffmpeg')

    if not candidate:
        fallback_paths = [
            r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
            r'C:\ffmpeg\bin\ffmpeg.exe',
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg'
        ]
        for p in fallback_paths:
            if os.path.exists(p):
                candidate = p
                break

    if not candidate:
        return None

    # On Windows, candidate .exe is directly usable
    if sys.platform.startswith('win'):
        return candidate

    # On Linux / macOS / Serverless:
    try:
        if os.access(candidate, os.X_OK):
            res = subprocess.run([candidate, '-version'], capture_output=True, timeout=5)
            if res.returncode == 0:
                return candidate
    except Exception:
        pass

    # If candidate failed execution or lacks permissions (common on serverless /var/task), copy to /tmp and chmod +x
    try:
        if not os.path.exists(tmp_ffmpeg) or os.path.getsize(tmp_ffmpeg) != os.path.getsize(candidate):
            shutil.copy2(candidate, tmp_ffmpeg)
        os.chmod(tmp_ffmpeg, 0o755)
        if os.access(tmp_ffmpeg, os.X_OK):
            return tmp_ffmpeg
    except Exception:
        pass

    return candidate


def patch_speech_recognition_flac():
    """
    Patches speech_recognition.AudioData.get_flac_data to encode FLAC via FFmpeg.
    This resolves:
    1. Windows: [WinError 623] caused by ancient bundled 32-bit flac-win32.exe.
    2. Linux/Serverless: Permission denied caused by non-executable flac-linux-x86_64 in read-only /var/task.
    """
    try:
        import speech_recognition as sr
        ffmpeg_exe = get_ffmpeg_executable()

        def custom_get_flac_data(self, convert_rate=None, convert_width=None):
            wav_bytes = self.get_wav_data(convert_rate, convert_width)
            # 1. Primary: Use FFmpeg directly to encode FLAC from stdin to stdout
            if ffmpeg_exe:
                try:
                    proc = subprocess.run(
                        [ffmpeg_exe, '-y', '-i', '-', '-c:a', 'flac', '-f', 'flac', '-'],
                        input=wav_bytes,
                        capture_output=True,
                        timeout=30
                    )
                    if proc.returncode == 0 and len(proc.stdout) > 0:
                        return proc.stdout
                except Exception:
                    pass

            # 2. Fallback: If on Linux, stage bundled flac to /tmp/flac and chmod +x
            if sys.platform != 'win32':
                try:
                    tmp_flac = '/tmp/flac'
                    if not os.path.exists(tmp_flac):
                        base_path = os.path.dirname(os.path.abspath(sr.__file__))
                        orig_flac = os.path.join(base_path, 'flac-linux-x86_64')
                        if os.path.exists(orig_flac):
                            shutil.copy2(orig_flac, tmp_flac)
                            os.chmod(tmp_flac, 0o755)
                    if os.path.exists(tmp_flac) and os.access(tmp_flac, os.X_OK):
                        proc = subprocess.run(
                            [tmp_flac, '--stdout', '--totally-silent', '--best', '-'],
                            input=wav_bytes,
                            capture_output=True,
                            timeout=30
                        )
                        if proc.returncode == 0 and len(proc.stdout) > 0:
                            return proc.stdout
                except Exception:
                    pass

            # 3. Ultimate fallback: original method
            if hasattr(sr.AudioData, '_original_get_flac_data'):
                return sr.AudioData._original_get_flac_data(self, convert_rate, convert_width)
            raise RuntimeError("Could not convert audio to FLAC for speech recognition.")

        if not hasattr(sr.AudioData, '_original_get_flac_data'):
            sr.AudioData._original_get_flac_data = sr.AudioData.get_flac_data
        sr.AudioData.get_flac_data = custom_get_flac_data
    except Exception:
        pass

# Initialize patch on module load
patch_speech_recognition_flac()


def is_pcm_wav(file_path):
    """Checks if file is a standard PCM WAV readable by wave and SpeechRecognition."""
    try:
        with wave.open(file_path, 'rb') as w:
            comptype = w.getcomptype()
            sampwidth = w.getsampwidth()
            channels = w.getnchannels()
            framerate = w.getframerate()
            return comptype == 'NONE' and sampwidth == 2 and channels in (1, 2) and framerate in (8000, 16000, 22050, 44100, 48000)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 3. Audio Conversion (Any Format -> 16kHz Mono 16-bit PCM WAV)
# ---------------------------------------------------------------------------
def convert_to_pcm_wav(input_audio_path, output_wav_path=None):
    """
    Converts MP3, M4A, WEBM, OGG, AAC, FLAC, or non-PCM WAV into
    16000 Hz, 1-channel, 16-bit PCM WAV for SpeechRecognition.
    Returns: (output_wav_path, error_message or None)
    """
    if not os.path.exists(input_audio_path):
        return None, "Audio file does not exist on disk."

    # If it is already a 16kHz mono 16-bit PCM WAV, return directly
    try:
        with wave.open(input_audio_path, 'rb') as w:
            if w.getcomptype() == 'NONE' and w.getsampwidth() == 2 and w.getnchannels() == 1 and w.getframerate() == 16000:
                return input_audio_path, None
    except Exception:
        pass

    ffmpeg_exe = get_ffmpeg_executable()
    if not ffmpeg_exe:
        # If FFmpeg is unavailable, but input is any readable PCM WAV, SpeechRecognition can still parse it directly
        if is_pcm_wav(input_audio_path):
            return input_audio_path, None
        return None, (
            "FFmpeg executable not found. Please install imageio-ffmpeg or ffmpeg "
            "to convert audio files into WAV format."
        )

    if output_wav_path is None:
        fd, output_wav_path = tempfile.mkstemp(suffix='_pcm16k.wav')
        os.close(fd)

    # Run FFmpeg command: 16kHz, mono, 16-bit pcm_s16le with dynamic audio normalization
    cmd_normalized = [
        ffmpeg_exe,
        '-y',
        '-i', input_audio_path,
        '-vn',
        '-af', 'dynaudnorm=p=0.9:m=100',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_wav_path
    ]

    cmd_basic = [
        ffmpeg_exe,
        '-y',
        '-i', input_audio_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        output_wav_path
    ]

    try:
        proc = subprocess.run(cmd_normalized, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            # Fallback to basic conversion without filter if dynaudnorm fails
            proc = subprocess.run(cmd_basic, capture_output=True, text=True, timeout=90)

        if proc.returncode != 0:
            if is_pcm_wav(input_audio_path):
                return input_audio_path, None
            err_msg = proc.stderr.strip() if proc.stderr else f"FFmpeg exited with code {proc.returncode}"
            return None, f"Audio format conversion failed: {err_msg}"
        if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
            if is_pcm_wav(input_audio_path):
                return input_audio_path, None
            return None, "Conversion produced an empty audio file."
        return output_wav_path, None
    except subprocess.TimeoutExpired:
        if is_pcm_wav(input_audio_path):
            return input_audio_path, None
        return None, "Audio conversion timed out after 90 seconds."
    except Exception as e:
        if is_pcm_wav(input_audio_path):
            return input_audio_path, None
        return None, f"Unexpected error during audio conversion: {str(e)}"


# ---------------------------------------------------------------------------
# 4. Long Audio Slicing (Pure Python wave chunker)
# ---------------------------------------------------------------------------
def split_wav_into_chunks(wav_path, max_seconds_per_chunk=18):
    """
    Splits a PCM WAV file into sequential chunks under max_seconds_per_chunk.
    Uses Python standard library `wave` (no external dependency needed).
    Returns list of chunk filepaths. Caller must clean up generated chunk files.
    """
    chunk_paths = []
    try:
        with wave.open(wav_path, 'rb') as w:
            params = w.getparams()
            framerate = w.getframerate()
            nframes = w.getnframes()
            if framerate <= 0:
                return [wav_path]

            chunk_frames = int(framerate * max_seconds_per_chunk)
            if nframes <= chunk_frames:
                # Audio is short enough; single file is sufficient
                return [wav_path]

            offset = 0
            idx = 0
            while offset < nframes:
                w.setpos(offset)
                frames_to_read = min(chunk_frames, nframes - offset)
                raw_frames = w.readframes(frames_to_read)

                fd, chunk_file = tempfile.mkstemp(suffix=f'_part{idx}.wav')
                os.close(fd)
                with wave.open(chunk_file, 'wb') as cw:
                    cw.setparams(params)
                    cw.writeframes(raw_frames)

                chunk_paths.append(chunk_file)
                offset += frames_to_read
                idx += 1

        return chunk_paths
    except Exception:
        # If splitting fails for any reason, return the original WAV
        return [wav_path]


# ---------------------------------------------------------------------------
# 5. Core Transcription Engine
# ---------------------------------------------------------------------------
def transcribe_tamil_audio(audio_file_path):
    """
    Transcribes a Tamil oral audio file (WAV, MP3, M4A, WEBM, OGG).
    
    Priority Order:
    1. Groq Whisper (whisper-large-v3, if GROQ_API_KEY is configured)
    2. Google Gemini 1.5 Flash (if GEMINI_API_KEY is configured)
    3. OpenAI Whisper (whisper-1, if OPENAI_API_KEY is configured)
    4. Google Speech Recognition (ta-IN, built-in free zero-config fallback)

    Returns: dict {
        "success": bool,
        "text": str,
        "provider": str,
        "error": str or None
    }
    """
    if not os.path.exists(audio_file_path):
        return {
            "success": False,
            "text": "",
            "provider": "none",
            "error": "ஒலிக்கோப்பு சேவையகத்தில் காணப்படவில்லை (Audio file not found on server)."
        }

    file_size = os.path.getsize(audio_file_path)
    if file_size == 0:
        return {
            "success": False,
            "text": "",
            "provider": "none",
            "error": "பதிவேற்றப்பட்ட ஒலிக்கோப்பு காலியாக உள்ளது (Uploaded audio file is empty)."
        }

    # Reload env in case user created or updated .env recently
    load_env_file()

    ext = os.path.splitext(audio_file_path)[1].lower()

    # -----------------------------------------------------------------------
    # PROVIDER 1: Groq Whisper (Whisper-Large-v3 — Outstanding for Tamil dialects)
    # -----------------------------------------------------------------------
    groq_api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if groq_api_key:
        try:
            with open(audio_file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(audio_file_path), f),
                }
                data = {
                    'model': 'whisper-large-v3',
                    'language': 'ta',
                    'response_format': 'json',
                    'prompt': 'தமிழ் நாட்டுப்புற வாய்மொழி வரலாறு, வட்டார வழக்கு, மரபு கதைகள்.'
                }
                headers = {'Authorization': f'Bearer {groq_api_key}'}
                resp = requests.post(
                    'https://api.groq.com/openai/v1/audio/transcriptions',
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=50
                )
                if resp.status_code == 200:
                    result = resp.json()
                    transcription = result.get('text', '').strip()
                    if transcription:
                        return {
                            "success": True,
                            "text": transcription,
                            "provider": "Groq Whisper (whisper-large-v3)",
                            "error": None
                        }
        except Exception:
            # Fall through gracefully to next provider
            pass

    # -----------------------------------------------------------------------
    # PROVIDER 2: Google Gemini API (gemini-1.5-flash Audio Transcription)
    # -----------------------------------------------------------------------
    gemini_api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if gemini_api_key:
        try:
            mime_map = {
                '.wav': 'audio/wav',
                '.mp3': 'audio/mp3',
                '.webm': 'audio/webm',
                '.ogg': 'audio/ogg',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac'
            }
            mime_type = mime_map.get(ext, 'audio/wav')
            with open(audio_file_path, 'rb') as f:
                b64_audio = base64.b64encode(f.read()).decode('utf-8')

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {
                            "text": (
                                "Transcribe this Tamil speech verbatim into standard Tamil script (தமிழ் எழுத்துகள்). "
                                "Preserve regional oral dialect expressions faithfully. Do not add comments or summaries, "
                                "output only the raw transcribed Tamil text."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_audio
                            }
                        }
                    ]
                }]
            }
            headers = {"Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload, timeout=50)
            if resp.status_code == 200:
                data = resp.json()
                parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                if parts and 'text' in parts[0]:
                    gemini_text = parts[0]['text'].strip()
                    if gemini_text:
                        return {
                            "success": True,
                            "text": gemini_text,
                            "provider": "Google Gemini 1.5 Flash (Audio)",
                            "error": None
                        }
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # PROVIDER 3: OpenAI Whisper (whisper-1)
    # -----------------------------------------------------------------------
    openai_api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if openai_api_key:
        try:
            with open(audio_file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(audio_file_path), f),
                }
                data = {
                    'model': 'whisper-1',
                    'language': 'ta',
                    'prompt': 'தமிழ் வாய்மொழி வரலாறு, பாரம்பரிய கதைகள், கிராம நினைவுகள்.'
                }
                headers = {'Authorization': f'Bearer {openai_api_key}'}
                resp = requests.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=50
                )
                if resp.status_code == 200:
                    result = resp.json()
                    transcription = result.get('text', '').strip()
                    if transcription:
                        return {
                            "success": True,
                            "text": transcription,
                            "provider": "OpenAI Whisper (whisper-1)",
                            "error": None
                        }
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # PROVIDER 4: Built-in Google Speech Recognition (ta-IN)
    # Free, zero-configuration engine with local FFmpeg audio conversion.
    # -----------------------------------------------------------------------
    try:
        import speech_recognition as sr
    except ImportError:
        return {
            "success": False,
            "text": "",
            "provider": "none",
            "error": "SpeechRecognition நூலகம் நிறுவப்படவில்லை. 'pip install SpeechRecognition' செய்யவும்."
        }

    # Convert audio format to 16kHz mono WAV if not already compatible PCM WAV
    pcm_wav_path, conv_err = convert_to_pcm_wav(audio_file_path)
    if conv_err:
        return {
            "success": False,
            "text": "",
            "provider": "FFmpeg Converter",
            "error": f"ஒலிக்கோப்பு வடிவ மாற்றம் தோல்வியடைந்தது: {conv_err}"
        }

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 180
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_adjustment_damping = 0.15
    recognizer.dynamic_energy_ratio = 1.5

    # Split into short, high-accuracy chunks (18s) to prevent timeouts
    chunks = split_wav_into_chunks(pcm_wav_path, max_seconds_per_chunk=18)
    transcribed_segments = []
    has_recognized_any = False
    recognition_error_detail = None

    try:
        for chunk_file in chunks:
            try:
                with sr.AudioFile(chunk_file) as source:
                    audio_data = recognizer.record(source)
                seg_text = recognizer.recognize_google(audio_data, language="ta-IN")
                if seg_text and seg_text.strip():
                    transcribed_segments.append(seg_text.strip())
                    has_recognized_any = True
            except sr.UnknownValueError:
                # Silence or unintelligible segment; continue to next chunk
                pass
            except sr.RequestError as req_err:
                recognition_error_detail = f"Google Speech API தொடர்புப் பிழை: {str(req_err)}"
            except Exception as e:
                recognition_error_detail = str(e)
    finally:
        # Clean up chunk files (do not delete the primary converted file yet)
        for chunk_file in chunks:
            if chunk_file != pcm_wav_path and os.path.exists(chunk_file):
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

        # Clean up pcm_wav_path if it was a temporary file
        if pcm_wav_path != audio_file_path and os.path.exists(pcm_wav_path):
            try:
                os.remove(pcm_wav_path)
            except Exception:
                pass

    if has_recognized_any and transcribed_segments:
        full_text = " ".join(transcribed_segments).strip()
        return {
            "success": True,
            "text": full_text,
            "provider": "Google Speech Recognition (தமிழ் ta-IN)",
            "error": None
        }

    # If nothing was recognized
    if recognition_error_detail:
        return {
            "success": False,
            "text": "",
            "provider": "Google Speech Recognition (தமிழ் ta-IN)",
            "error": f"எழுத்தாக்கச் சேவையில் பிழை ஏற்பட்டது: {recognition_error_detail}"
        }

    return {
        "success": False,
        "text": "",
        "provider": "Google Speech Recognition (தமிழ் ta-IN)",
        "error": "ஒலிக்கோப்பில் தெளிவான தமிழ்ப் பேச்சு கண்டறியப்படவில்லை (தெளிவான குரல் பதிவைப் பதிவேற்றவும்)."
    }
