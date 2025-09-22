import assemblyai as aai
from pathlib import Path
from typing import Optional, Dict, List, Any
from config import API_KEY, SPEAKERS_EXPECTED
import time

aai.settings.api_key = API_KEY

class Transcriber:
    def __init__(self):
        self.client = aai.Transcriber()
        self.last_transcript = None

    def transcribe_audio(
        self,
        audio_path: Path,
        speakers_expected: Optional[int] = None,
        language_code: str = "en",
        on_progress: Optional[callable] = None
    ) -> Dict[str, Any]:

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        config = aai.TranscriptionConfig(
            speaker_labels=True,
            speakers_expected=speakers_expected or SPEAKERS_EXPECTED,
            language_code=language_code,
            punctuate=True,
            format_text=True
        )

        try:
            if on_progress:
                on_progress("Uploading audio file...")

            transcript = self.client.transcribe(str(audio_path), config)

            if on_progress:
                on_progress("Processing transcription...")

            while transcript.status not in ['completed', 'error']:
                time.sleep(2)
                transcript = self.client.get_transcript(transcript.id)
                if on_progress and transcript.status == 'processing':
                    on_progress(f"Processing... (Status: {transcript.status})")

            if transcript.error:
                raise ValueError(f"Transcription failed: {transcript.error}")

            self.last_transcript = transcript

            utterances = []
            if hasattr(transcript, 'utterances') and transcript.utterances:
                for utt in transcript.utterances:
                    utterances.append({
                        'speaker': utt.speaker,
                        'text': utt.text,
                        'start': utt.start,
                        'end': utt.end,
                        'confidence': utt.confidence if hasattr(utt, 'confidence') else None,
                        'speaker_name': utt.speaker
                    })

            result = {
                'id': transcript.id,
                'status': transcript.status,
                'utterances': utterances,
                'text': transcript.text,
                'duration': transcript.audio_duration if hasattr(transcript, 'audio_duration') else None,
                'language': transcript.language_code if hasattr(transcript, 'language_code') else language_code,
                'confidence': transcript.confidence if hasattr(transcript, 'confidence') else None
            }

            return result

        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")

    def get_transcript_by_id(self, transcript_id: str) -> Dict[str, Any]:
        try:
            transcript = self.client.get_transcript(transcript_id)

            utterances = []
            if hasattr(transcript, 'utterances') and transcript.utterances:
                for utt in transcript.utterances:
                    utterances.append({
                        'speaker': utt.speaker,
                        'text': utt.text,
                        'start': utt.start,
                        'end': utt.end,
                        'confidence': utt.confidence if hasattr(utt, 'confidence') else None,
                        'speaker_name': utt.speaker
                    })

            return {
                'id': transcript.id,
                'status': transcript.status,
                'utterances': utterances,
                'text': transcript.text,
                'duration': transcript.audio_duration if hasattr(transcript, 'audio_duration') else None,
                'confidence': transcript.confidence if hasattr(transcript, 'confidence') else None
            }
        except Exception as e:
            raise Exception(f"Failed to retrieve transcript: {str(e)}")