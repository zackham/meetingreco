from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json

class Utterance(BaseModel):
    speaker: str
    speaker_name: str
    text: str
    start: int
    end: int
    confidence: Optional[float] = None

class Meeting(BaseModel):
    id: str
    name: str
    date: datetime
    duration: Optional[int] = None
    audio_path: Optional[Path] = None
    transcript_id: Optional[str] = None
    utterances: List[Utterance] = []
    speaker_mapping: Dict[str, str] = {}
    status: str = "recorded"
    error: Optional[str] = None

    def get_folder_path(self) -> Path:
        from config import MEETINGS_DIR
        timestamp = self.date.strftime("%Y-%m-%d_%H-%M")
        folder_name = f"{timestamp}_{self.name.replace(' ', '_')}"
        return MEETINGS_DIR / folder_name

    def save(self):
        folder = self.get_folder_path()
        folder.mkdir(parents=True, exist_ok=True)

        meeting_data = self.model_dump(exclude={'audio_path'})
        meeting_data['date'] = self.date.isoformat()
        meeting_data['audio_path'] = str(self.audio_path.name) if self.audio_path else None

        json_path = folder / "meeting.json"
        with open(json_path, 'w') as f:
            json.dump(meeting_data, f, indent=2, default=str)

        if self.audio_path and self.audio_path.exists():
            audio_dest = folder / "audio.mp3"
            if not audio_dest.exists():
                import shutil
                shutil.move(str(self.audio_path), str(audio_dest))
                self.audio_path = audio_dest

        self.save_markdown()

    def save_markdown(self):
        folder = self.get_folder_path()
        md_path = folder / "transcript.md"

        with open(md_path, 'w') as f:
            f.write(f"# {self.name}\n\n")
            f.write(f"**Date:** {self.date.strftime('%Y-%m-%d %H:%M')}\n\n")
            if self.duration:
                f.write(f"**Duration:** {self.duration // 60}:{self.duration % 60:02d}\n\n")

            if self.status == "error":
                f.write(f"\n**Error:** {self.error}\n\n")

            if self.utterances:
                f.write("## Transcript\n\n")
                for utt in self.utterances:
                    time_str = f"{utt.start // 60000:02d}:{(utt.start // 1000) % 60:02d}"
                    f.write(f"**[{time_str}] {utt.speaker_name}:** {utt.text}\n\n")

    @classmethod
    def load_from_folder(cls, folder_path: Path) -> Optional['Meeting']:
        json_path = folder_path / "meeting.json"
        if not json_path.exists():
            return None

        with open(json_path, 'r') as f:
            data = json.load(f)

        data['date'] = datetime.fromisoformat(data['date'])

        if data.get('audio_path'):
            audio_path = folder_path / "audio.mp3"
            data['audio_path'] = audio_path if audio_path.exists() else None

        data['utterances'] = [Utterance(**u) for u in data.get('utterances', [])]

        return cls(**data)

    def update_speaker_names(self, mapping: Dict[str, str]):
        self.speaker_mapping.update(mapping)
        for utt in self.utterances:
            if utt.speaker in self.speaker_mapping:
                utt.speaker_name = self.speaker_mapping[utt.speaker]
        self.save()

    def get_unique_speakers(self) -> List[str]:
        return list(set(utt.speaker for utt in self.utterances))

class MeetingManager:
    @staticmethod
    def list_meetings() -> List[Meeting]:
        from config import MEETINGS_DIR
        meetings = []

        if not MEETINGS_DIR.exists():
            return meetings

        for folder in sorted(MEETINGS_DIR.iterdir(), reverse=True):
            if folder.is_dir():
                meeting = Meeting.load_from_folder(folder)
                if meeting:
                    meetings.append(meeting)

        return meetings

    @staticmethod
    def get_meeting(meeting_id: str) -> Optional[Meeting]:
        meetings = MeetingManager.list_meetings()
        for meeting in meetings:
            if meeting.id == meeting_id:
                return meeting
        return None

    @staticmethod
    def delete_meeting(meeting_id: str) -> bool:
        meeting = MeetingManager.get_meeting(meeting_id)
        if meeting:
            folder = meeting.get_folder_path()
            if folder.exists():
                import shutil
                shutil.rmtree(folder)
                return True
        return False