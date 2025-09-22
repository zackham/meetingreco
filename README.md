# Meeting Recorder & Transcription TUI

A powerful terminal-based application for recording, transcribing, and managing meeting audio with automatic speaker identification. Built with Python, Textual, and AssemblyAI.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)

## Features

### 🎙️ Audio Recording
- **Dual-channel recording**: Captures both system audio and microphone simultaneously
- **PipeWire/PulseAudio support**: Works with modern Linux audio systems
- **Real-time monitoring**: Shows recording duration and file size during capture
- **Pause/Resume**: Create multiple segments that auto-merge
- **Smart device detection**: Automatically finds and uses appropriate audio devices

### 🤖 AI Transcription
- **AssemblyAI integration**: High-quality automatic transcription
- **Speaker diarization**: Automatically detects and separates different speakers
- **Multiple language support**: Configure language for transcription
- **Reprocessing capability**: Re-transcribe audio if needed

### 💻 Terminal User Interface
- **Beautiful TUI**: Built with Textual for a modern terminal experience
- **Meeting management**: List, view, search, and manage all recordings
- **Interactive speaker assignment**: See transcript while assigning real names
- **Full-text search**: Search within transcripts with highlighting
- **Keyboard-driven**: Efficient navigation without mouse

### 📁 Data Organization
- **Structured storage**: Each meeting in its own folder with audio and transcript
- **Multiple formats**: JSON data, Markdown transcript, and MP3 audio
- **Persistent speaker mapping**: Remember speaker assignments

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│ Meeting Recorder                                            │
├─────────────────────────────────────────────────────────────┤
│ Date        Name              Duration  Speakers  Status    │
│ 2024-01-20  Team Standup      15:32    3         transcribed│
│ 2024-01-19  Client Call       45:10    4         transcribed│
│ 2024-01-18  Design Review     23:45    2         transcribed│
└─────────────────────────────────────────────────────────────┘
[n] New  [Enter] View  [e] Edit Speakers  [d] Delete  [q] Quit
```

## Requirements

### System Requirements
- Linux with PipeWire or PulseAudio
- Python 3.8 or higher
- ffmpeg
- parecord (part of PulseAudio utilities)

### Audio Setup
The application records from your default audio devices. For best results:
- Use a USB conference speaker (like Anker PowerConf) for both input and output
- Ensure meeting audio plays through the same device that's recording
- The app captures what goes TO your speakers (system audio) plus your microphone

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/meetingreco.git
cd meetingreco
```

2. **Install system dependencies**

For Arch Linux:
```bash
sudo pacman -S python python-pip pipewire pipewire-pulse ffmpeg
```

For Ubuntu/Debian:
```bash
sudo apt install python3 python3-pip python3-venv pipewire pipewire-pulse ffmpeg
```

3. **Set up Python environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Configure AssemblyAI**

Get your API key from [AssemblyAI](https://www.assemblyai.com/)

Create `.env` file:
```bash
echo "ASSEMBLYAI_API_KEY=your_api_key_here" > .env
```

## Usage

### Starting the Application

```bash
./run.sh
# or
source venv/bin/activate
python app.py
```

### Recording a Meeting

1. Press `n` to start a new recording
2. Enter a meeting name
3. Click "Start Recording" or press `r`
4. The app shows:
   - Recording status (🔴 Recording...)
   - Duration timer
   - File size in real-time
5. Controls during recording:
   - **Pause/Resume**: Temporarily stop recording
   - **Save & Transcribe**: Stop and process the audio
   - **Discard**: Cancel without saving

### Managing Transcriptions

#### View Meeting Details
- Press `Enter` on any meeting to see the full transcript
- Timestamps and speaker labels for each utterance
- Color-coded speakers for easy reading

#### Search Within Transcripts
- Press `/` to open search
- Type your search term
- `n` - Next match
- `p` - Previous match
- Matching text highlighted in yellow

#### Assign Speaker Names
- Press `e` on a meeting (or after transcription)
- See sample quotes from each speaker
- Live preview updates as you type names
- Names are saved and remembered

### Keyboard Shortcuts

#### Meeting List
- `n` - New recording
- `Enter` - View meeting details
- `e` - Edit speaker names
- `t` - Reprocess transcription
- `d` - Delete meeting
- `r` - Refresh list
- `q` - Quit application

#### Recording Screen
- `r` - Start/Stop recording
- `p` - Pause/Resume
- `s` - Save & transcribe
- `d` - Discard recording
- `Escape` - Back to list

#### Detail View
- `/` - Toggle search
- `n` - Next search match
- `p` - Previous match
- `e` - Edit speakers
- `Escape` - Back to list

## File Structure

Meetings are organized in folders:
```
meetings/
└── 2024-01-20_14-30_TeamMeeting/
    ├── meeting.json       # Complete meeting data
    ├── transcript.md      # Readable transcript
    └── audio.mp3          # Original recording
```

## Troubleshooting

### No Audio Recorded
- Check PipeWire/PulseAudio is running: `systemctl --user status pipewire`
- Verify audio devices: `pactl list sources`
- Ensure audio plays through the recording device

### Transcription Fails
- Verify API key is correct
- Check you have AssemblyAI credits
- Ensure internet connection

### Device-Specific Setup
The app tries to auto-detect audio devices. For specific devices:
1. Run `pactl list sources | grep Name`
2. Edit `recorder.py` to set your device names

## Configuration

Edit `config.py` to customize:
- `MEETINGS_DIR` - Where meetings are stored
- `BITRATE` - Audio quality (default: 192k)
- `SPEAKERS_EXPECTED` - Default number of speakers

## Development

### Project Structure
```
meetingreco/
├── app.py          # Main TUI application
├── recorder.py     # Audio recording logic
├── transcriber.py  # AssemblyAI integration
├── models.py       # Data models and storage
├── config.py       # Configuration settings
├── requirements.txt
└── run.sh          # Launcher script
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the app to test
5. Submit a pull request

## License

MIT License - see LICENSE file

## Credits

Built with:
- [Textual](https://github.com/Textualize/textual) - Terminal User Interface
- [AssemblyAI](https://www.assemblyai.com/) - Speech transcription
- [FFmpeg](https://ffmpeg.org/) - Audio processing
- [PipeWire](https://pipewire.org/) - Audio capture

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Include error messages and system info

---

**Note**: This application records audio from your system. Ensure you have consent from all meeting participants before recording.