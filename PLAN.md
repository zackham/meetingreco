### Comprehensive Plan for Building the Meeting Transcription TUI App

This plan outlines everything needed to set up and build your passive audio recorder + AssemblyAI transcriber on Arch Linux (Wayland, PipeWire). The app will be a Python-based TUI using the Textual library for a clean, interactive interface. We'll record system audio as MP3 (compressed for uploads; AssemblyAI supports it, though WAV/FLAC is recommended for max accuracy—use 128kbps+ bitrate to minimize quality loss for diarization). After stopping, it uploads to AssemblyAI, fetches the JSON (with diarization labels like "A", "B"), lets you map speakers, name the meeting, and saves to a timestamped folder.

**Assumptions**: You're comfortable with basic terminal commands/Python. Total build time: 2-4 hours. Costs: AssemblyAI free tier (~$50 credits covers 185+ hours from prior context); no other paid deps.

#### 1. Prerequisites & Environment Setup
Install system packages on Arch (run as user, no sudo needed for most). Update your system first: `sudo pacman -Syu`.

| Package | Purpose | Install Command |
|---------|---------|-----------------|
| **pipewire** & tools | System audio capture (default on Arch, but ensure utils) | `sudo pacman -S pipewire pipewire-pulse pipewire-alsa wireplumber pw-cli` (if not installed; restart after). |
| **ffmpeg** | MP3 encoding during record (supports PipeWire input) | `sudo pacman -S ffmpeg` |
| **pavucontrol** | GUI to route/monitor audio sinks (optional, for testing) | `sudo pacman -S pavucontrol` |
| **Python 3.12+** | Core runtime (Arch default) | Already installed; verify: `python --version` |
| **git** | Clone optional examples | `sudo pacman -S git` |

- **Audio Setup Test**:
  1. Open a terminal: `pw-cli list-objects | grep -E 'audio.sink|monitor'` to list sinks. Note your default sink monitor (e.g., `alsa_output.pci-0000_00_1f.3.analog-stereo.monitor`).
  2. Test record: `ffmpeg -f pulse -i <your_sink_monitor> -t 10 -c:a libmp3lame -b:a 128k test.mp3`. Play a sound in browser; stop after 10s. File should capture audio.
  3. For Meet-only: In pavucontrol (run it), go to Recording tab during a test Meet—route browser to a null sink if needed (advanced: `pactl load-module module-null-sink sink_name=meet_sink` then set browser output there).
  - Wayland note: No issues; PipeWire is Wayland-native.

- **AssemblyAI Account**:
  1. Sign up at [assemblyai.com](https://www.assemblyai.com) (free).
  2. Get API key from dashboard (under "API Keys").
  3. File size limits: Up to 5GB/audio file, no hard duration limit (but ~4hr practical for MP3).

#### 2. Project Structure
Create a dedicated folder: `mkdir ~/meeting-tui && cd ~/meeting-tui`. Use this layout for modularity:

```
meeting-tui/
├── app.py              # Main TUI entrypoint (runs the app)
├── recorder.py         # Audio recording logic (start/stop/pause via ffmpeg subprocess)
├── transcriber.py      # AssemblyAI upload & fetch
├── editor.py           # Speaker assignment & naming UI logic
├── storage.py          # Folder creation & saving (JSON + MD)
├── config.py           # API key & constants (e.g., sink name)
├── requirements.txt    # Python deps
└── meetings/           # Output folder (auto-created)
    └── 2025-09-21_14-30-FooBar/
        ├── transcript.json
        ├── transcript.md
        └── audio.mp3  # Optional: keep raw for re-process
```

#### 3. Python Dependencies
Create `requirements.txt`:
```
textual==0.80.0  # TUI framework (latest as of 2025; pip install)
assemblyai==0.22.0  # API SDK
requests==2.32.3  # For any extras (already in assemblyai, but safe)
rich==13.7.1  # For pretty prints in TUI
```

Install: `pip install -r requirements.txt` (use venv: `python -m venv .venv && source .venv/bin/activate` for isolation).

#### 4. Core Modules (Code Snippets)
Implement each file step-by-step. All code is async-friendly for Textual.

- **config.py** (Settings):
  ```python
  import os

  API_KEY = os.getenv("ASSEMBLYAI_API_KEY")  # Set via export ASSEMBLYAI_API_KEY=your_key
  AUDIO_SINK = "default"  # Or your monitor name, e.g., "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"
  BITRATE = "128k"  # MP3 quality
  SPEAKERS_EXPECTED = 4  # Tune for better diarization
  MEETINGS_DIR = os.path.expanduser("~/meeting-tui/meetings")
  ```

- **recorder.py** (Handles recording; uses ffmpeg subprocess for pause/resume via signals):
  ```python
  import subprocess
  import signal
  import os
  from pathlib import Path
  from config import AUDIO_SINK, BITRATE

  class Recorder:
      def __init__(self):
          self.process = None
          self.output_path = None
          self.is_paused = False

      def start(self, output_path: str):
          self.output_path = Path(output_path)
          cmd = [
              "ffmpeg", "-f", "pulse", "-i", AUDIO_SINK,
              "-c:a", "libmp3lame", "-b:a", BITRATE,
              str(self.output_path), "-y"  # Overwrite
          ]
          self.process = subprocess.Popen(cmd)
          print(f"Started recording to {self.output_path}")

      def pause(self):
          if self.process and not self.is_paused:
              self.process.send_signal(signal.SIGSTOP)
              self.is_paused = True
              print("Paused")

      def resume(self):
          if self.process and self.is_paused:
              self.process.send_signal(signal.SIGCONT)
              self.is_paused = False
              print("Resumed")

      def stop(self):
          if self.process:
              self.process.terminate()
              self.process.wait()
              print(f"Stopped. File: {self.output_path}")
              return self.output_path
          return None
  ```

- **transcriber.py** (Upload & get JSON):
  ```python
  import assemblyai as aai
  from config import API_KEY, SPEAKERS_EXPECTED

  aai.settings.api_key = API_KEY

  def transcribe_audio(audio_path: str):
      config = aai.TranscriptionConfig(
          speaker_labels=True,
          speakers_expected=SPEAKERS_EXPECTED,
          language_code="en"  # Adjust if needed
      )
      transcriber = aai.Transcriber()
      transcript = transcriber.transcribe(audio_path, config)
      if transcript.error:
          raise ValueError(f"Transcription error: {transcript.error}")
      return transcript  # .utterances: list of dicts with 'speaker', 'text', 'start', 'end'
  ```

- **editor.py** (Speaker mapping logic; returns edited utterances):
  ```python
  from typing import List, Dict

  def assign_speakers(utterances: List[Dict], speakers: Dict[str, str]) -> List[Dict]:
      # speakers: {'A': 'Alice', 'B': 'Bob', ...} from TUI input
      for utt in utterances:
          utt['speaker_name'] = speakers.get(utt['speaker'], utt['speaker'])  # Fallback to label
      return utterances

  def get_unique_speakers(utterances: List[Dict]) -> set:
      return {utt['speaker'] for utt in utterances}
  ```

- **storage.py** (Save files):
  ```python
  import json
  import os
  from datetime import datetime
  from pathlib import Path
  from config import MEETINGS_DIR

  def save_transcript(utterances: List[Dict], meeting_name: str, audio_path: str = None):
      timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
      folder = Path(MEETINGS_DIR) / f"{timestamp}-{meeting_name.replace(' ', '')}"
      folder.mkdir(parents=True, exist_ok=True)

      # JSON
      json_path = folder / "transcript.json"
      with open(json_path, 'w') as f:
          json.dump({'utterances': utterances}, f, indent=2)

      # Markdown
      md_path = folder / "transcript.md"
      with open(md_path, 'w') as f:
          f.write(f"# Meeting: {meeting_name} - {timestamp}\n\n")
          for utt in utterances:
              time_str = f"[{utt['start']/1000//60:02d}:{utt['start']/1000%60:02d}]"
              f.write(f"{time_str} {utt['speaker_name']}: {utt['text']}\n\n")

      # Optional audio
      if audio_path:
          Path(audio_path).rename(folder / "audio.mp3")

      print(f"Saved to {folder}")
  ```

- **app.py** (Main TUI; orchestrates everything):
  ```python
  from textual.app import App, ComposeResult
  from textual.widgets import Button, Input, Label, Static, Header, Footer
  from textual.containers import Container, Vertical
  from textual.reactive import reactive
  from recorder import Recorder
  from transcriber import transcribe_audio
  from editor import assign_speakers, get_unique_speakers
  from storage import save_transcript
  import os

  class MeetingApp(App):
      recording = reactive(False)
      paused = reactive(False)
      transcript = reactive(None)
      speakers_input = reactive({})  # e.g., {'A': ''}

      def compose(self) -> ComposeResult:
          yield Header()
          yield Footer()
          yield Container(
              Label("Meeting Transcription TUI"),
              Button("Start Recording", id="start"),
              Button("Pause/Resume", id="pause"),
              Button("Stop & Transcribe", id="stop", disabled=True),
              Input(placeholder="Meeting Name", id="name"),
              id="controls"
          )
          yield Static("Transcript Preview", id="preview")

      def on_button_pressed(self, event: Button.Pressed) -> None:
          if event.button.id == "start":
              output = f"recording_{os.getpid()}.mp3"  # Temp file
              self.recorder.start(output)
              self.recording = True
              event.button.label = "Recording..."
              self.query_one("#stop").disabled = False
          elif event.button.id == "pause":
              if self.paused:
                  self.recorder.resume()
                  self.paused = False
                  event.button.label = "Pause"
              else:
                  self.recorder.pause()
                  self.paused = True
                  event.button.label = "Resume"
          elif event.button.id == "stop":
              audio_path = self.recorder.stop()
              self.recording = False
              self.query_one("#start").label = "Start Recording"
              self.query_one("#stop").disabled = True
              if audio_path:
                  self.transcript = transcribe_audio(audio_path)
                  unique_spks = get_unique_speakers(self.transcript.utterances)
                  # Simple input loop for speakers (enhance with dynamic Inputs)
                  self.speakers_input = {spk: input(f"Name for {spk}: ") for spk in unique_spks}
                  edited = assign_speakers(self.transcript.utterances, self.speakers_input)
                  name = self.query_one(Input).value or "Untitled"
                  save_transcript(edited, name, audio_path)
                  self.query_one("#preview").update("Saved! Preview:\n" + str(edited[:3]))  # Snippet

      def on_mount(self) -> None:
          self.recorder = Recorder()

  if __name__ == "__main__":
      app = MeetingApp()
      app.run()
  ```

#### 5. Integration & Workflow
1. Set env: `export ASSEMBLYAI_API_KEY=your_key` (add to ~/.bashrc for persistence).
2. Run: `python app.py`—TUI launches.
3. Workflow:
   - Click "Start" → Records MP3 passively (ensure Meet audio is playing).
   - Pause/Resume as needed.
   - "Stop" → Uploads, processes (~1-2min for 1hr audio), prompts for speaker names (console inputs for simplicity; upgrade to TUI forms).
   - Enter meeting name → Saves folder.
4. Post-run: Browse `~/meeting-tui/meetings/` for files. Search MD with grep or Obsidian.

#### 6. Enhancements & Testing
- **Upgrades**: Add progress bar for upload (Textual Progress); auto-detect speakers from Calendar (Google API); delete temp audio.
- **Error Handling**: Wrap uploads in try/except; log to file.
- **Testing**:
  1. Short test: Run app, play YouTube audio, record 30s, stop—check MP3 size (~0.5MB vs. 5MB WAV).
  2. AssemblyAI: Upload sample, verify JSON has `speaker_labels`.
  3. Edge: Noisy audio? Test diarization accuracy; manual edit fixes.
  4. Debug: `ffmpeg -loglevel debug` for audio issues; Arch wiki PipeWire page for quirks.
- **Perf**: On 8GB GPU (irrelevant here, all CPU/cloud), handles 2hr+ fine. Uploads bandwidth-friendly (~1MB/min at 128kbps).

This is production-ready with tweaks—fork from GitHub if you want a starter repo (search "pipewire meeting recorder python"). Ping for bugfixes!
