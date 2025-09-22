#!/usr/bin/env python3

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Input, Label, Static, ListView, ListItem, ProgressBar, DataTable, RichLog
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, Grid
from textual.screen import Screen
from textual.reactive import reactive
from textual.binding import Binding
from textual import work
from rich.text import Text
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
import asyncio
import uuid
from pathlib import Path
import re

from recorder import AudioRecorder
from transcriber import Transcriber
from models import Meeting, MeetingManager, Utterance
from config import APP_NAME

class RecordingScreen(Screen):
    BINDINGS = [
        Binding("r", "toggle_recording", "Start/Stop Recording"),
        Binding("p", "pause_resume", "Pause/Resume"),
        Binding("s", "save", "Save & Transcribe"),
        Binding("d", "discard", "Discard"),
        Binding("escape", "back", "Back to List"),
    ]

    CSS = """
    RecordingScreen {
        align: center middle;
    }

    #recording-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
    }

    #status {
        text-align: center;
        margin-bottom: 1;
        height: 3;
    }

    #timer {
        text-align: center;
        margin: 1;
        text-style: bold;
    }

    #controls {
        margin-top: 2;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }

    #meeting-name {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.recorder = AudioRecorder()
        self.is_recording = False
        self.is_paused = False
        self.start_time = None
        self.update_timer_task = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Ready to Record", id="status"),
            Static("00:00:00", id="timer"),
            Input(placeholder="Enter meeting name...", id="meeting-name"),
            Horizontal(
                Button("Start Recording", id="record", variant="primary"),
                id="controls"
            ),
            Static("", id="info"),
            id="recording-container"
        )
        yield Footer()

    async def on_mount(self) -> None:
        # Set initial focus to meeting name input
        self.query_one("#meeting-name", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "record":
            await self.action_toggle_recording()
        elif event.button.id == "pause":
            await self.action_pause_resume()
        elif event.button.id == "save":
            await self.action_save()
        elif event.button.id == "discard":
            await self.action_discard()

    async def action_toggle_recording(self) -> None:
        controls = self.query_one("#controls", Horizontal)
        status = self.query_one("#status", Static)

        if not self.is_recording:
            if self.recorder.start():
                self.is_recording = True
                self.start_time = datetime.now()

                # Replace button with recording controls
                await controls.remove_children()
                pause_btn = Button("Pause", id="pause", variant="warning")
                save_btn = Button("Save & Transcribe", id="save", variant="success")
                discard_btn = Button("Discard", id="discard", variant="error")
                await controls.mount(pause_btn, save_btn, discard_btn)

                status.update("🔴 Recording...")
                self.update_timer_task = asyncio.create_task(self.update_timer())
        else:
            # This shouldn't happen with new UI, but kept for keyboard shortcut
            await self.action_save()

    async def action_pause_resume(self) -> None:
        pause_btn = self.query_one("#pause", Button)
        status = self.query_one("#status", Static)

        if self.is_recording and not self.is_paused:
            self.recorder.pause()
            self.is_paused = True
            pause_btn.label = "Resume"
            status.update("⏸ Paused")
        elif self.is_paused:
            self.recorder.resume()
            self.is_paused = False
            pause_btn.label = "Pause"
            status.update("🔴 Recording...")

    async def action_save(self) -> None:
        audio_file = self.recorder.stop()
        if audio_file:
            meeting_name = self.query_one("#meeting-name", Input).value or "Untitled Meeting"
            if self.update_timer_task:
                self.update_timer_task.cancel()
            self.app.push_screen(TranscriptionScreen(audio_file, meeting_name))

    async def action_discard(self) -> None:
        self.recorder.stop()
        if self.update_timer_task:
            self.update_timer_task.cancel()
        self.app.pop_screen()

    async def action_back(self) -> None:
        if self.is_recording:
            self.recorder.stop()
        self.app.pop_screen()

    async def update_timer(self) -> None:
        timer = self.query_one("#timer", Static)
        info = self.query_one("#info", Static)

        while self.is_recording or self.is_paused:
            duration = self.recorder.get_duration()
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            timer.update(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            file_size = self.recorder.get_file_size()
            size_mb = file_size / (1024 * 1024)
            info.update(f"File size: {size_mb:.1f} MB")

            await asyncio.sleep(1)

class TranscriptionScreen(Screen):
    CSS = """
    TranscriptionScreen {
        align: center middle;
    }

    #transcription-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
    }

    #progress {
        margin: 2 0;
    }

    #status-text {
        text-align: center;
        margin: 1 0;
    }
    """

    def __init__(self, audio_file: Path, meeting_name: str):
        super().__init__()
        self.audio_file = audio_file
        self.meeting_name = meeting_name
        self.transcriber = Transcriber()
        self.meeting = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"Transcribing: {self.meeting_name}", id="status-text"),
            ProgressBar(id="progress", show_eta=False),
            Static("", id="info"),
            id="transcription-container"
        )
        yield Footer()

    async def on_mount(self) -> None:
        self.transcribe_audio()

    @work(thread=True)
    def transcribe_audio(self) -> None:
        try:
            info = self.query_one("#info", Static)

            def on_progress(msg):
                self.app.call_from_thread(info.update, msg)

            result = self.transcriber.transcribe_audio(
                self.audio_file,
                on_progress=on_progress
            )

            meeting_id = str(uuid.uuid4())
            self.meeting = Meeting(
                id=meeting_id,
                name=self.meeting_name,
                date=datetime.now(),
                duration=result.get('duration'),
                audio_path=self.audio_file,
                transcript_id=result.get('id'),
                status="transcribed"
            )

            for utt_data in result.get('utterances', []):
                utterance = Utterance(
                    speaker=utt_data['speaker'],
                    speaker_name=utt_data['speaker_name'],
                    text=utt_data['text'],
                    start=utt_data['start'],
                    end=utt_data['end'],
                    confidence=utt_data.get('confidence')
                )
                self.meeting.utterances.append(utterance)

            self.meeting.save()
            self.app.call_from_thread(self.complete_transcription)

        except Exception as e:
            self.app.call_from_thread(info.update, f"Error: {str(e)}")
            if not self.meeting:
                self.meeting = Meeting(
                    id=str(uuid.uuid4()),
                    name=self.meeting_name,
                    date=datetime.now(),
                    audio_path=self.audio_file,
                    status="error",
                    error=str(e)
                )
                self.meeting.save()

    def complete_transcription(self) -> None:
        if self.meeting and self.meeting.utterances:
            self.app.pop_screen()
            self.app.push_screen(SpeakerAssignmentScreen(self.meeting))
        else:
            self.app.pop_screen()
            # Refresh the meeting list
            if self.app.screen_stack and isinstance(self.app.screen_stack[-1], MeetingListScreen):
                self.app.screen_stack[-1].refresh_meetings()

class SpeakerAssignmentScreen(Screen):
    BINDINGS = [
        Binding("escape", "save", "Save & Back"),
    ]

    CSS = """
    SpeakerAssignmentScreen {
        align: center middle;
    }

    #assignment-container {
        width: 95%;
        height: 95%;
        border: solid $primary;
        padding: 1;
    }

    #main-grid {
        grid-size: 2 1;
        grid-columns: 1fr 2fr;
        height: 100%;
    }

    #speaker-panel {
        border-right: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    #transcript-panel {
        padding: 1;
        overflow-y: auto;
    }

    .speaker-section {
        margin-bottom: 2;
        padding: 1;
        border: dashed $primary;
    }

    .speaker-header {
        text-style: bold;
        margin-bottom: 1;
    }

    Input {
        width: 100%;
        margin-bottom: 1;
    }

    .sample-text {
        margin: 0 0 1 1;
        color: $text-muted;
    }

    #transcript-preview {
        height: 100%;
        border: none;
    }

    #save-button {
        dock: bottom;
        height: 3;
        margin: 1;
    }
    """

    def __init__(self, meeting: Meeting):
        super().__init__()
        self.meeting = meeting
        self.speaker_inputs = {}
        self.temp_mapping = {}

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="assignment-container"):
            yield Static(f"Assign Speaker Names - {self.meeting.name}", id="title")

            with Grid(id="main-grid"):
                with VerticalScroll(id="speaker-panel"):
                    speakers = self.meeting.get_unique_speakers()

                    for speaker in sorted(speakers):
                        with Container(classes="speaker-section"):
                            yield Static(f"[bold]{speaker}[/bold]", classes="speaker-header")

                            existing_name = self.meeting.speaker_mapping.get(speaker, "")
                            speaker_input = Input(
                                placeholder=f"Enter name for {speaker}",
                                value=existing_name,
                                id=f"speaker_{speaker}"
                            )
                            yield speaker_input
                            self.speaker_inputs[speaker] = speaker_input

                            # Add sample utterances for this speaker
                            sample_utterances = self._get_sample_utterances(speaker, 3)
                            for utt in sample_utterances:
                                time_str = f"{utt.start // 60000:02d}:{(utt.start // 1000) % 60:02d}"
                                sample_text = utt.text[:100] + "..." if len(utt.text) > 100 else utt.text
                                yield Static(f"[dim]{time_str}:[/dim] {sample_text}", classes="sample-text")

                with Container(id="transcript-panel"):
                    yield Static("[bold]Live Preview[/bold]")
                    yield RichLog(id="transcript-preview", highlight=True, markup=True)

            yield Button("Save & Continue", id="save-button", variant="primary")

        yield Footer()

    def _get_sample_utterances(self, speaker: str, count: int = 3):
        """Get sample utterances for a speaker to help identify them"""
        samples = []
        for utt in self.meeting.utterances:
            if utt.speaker == speaker and len(utt.text) > 20:  # Skip very short utterances
                samples.append(utt)
                if len(samples) >= count:
                    break
        return samples

    async def on_mount(self) -> None:
        self.update_preview()
        # Focus the first input
        if self.speaker_inputs:
            first_input = list(self.speaker_inputs.values())[0]
            first_input.focus()

    def update_preview(self) -> None:
        """Update the transcript preview with current speaker names"""
        preview = self.query_one("#transcript-preview", RichLog)
        preview.clear()

        # Show first 20 utterances as preview
        for i, utt in enumerate(self.meeting.utterances[:20]):
            time_str = f"{utt.start // 60000:02d}:{(utt.start // 1000) % 60:02d}"

            # Use temp mapping if available, otherwise original
            speaker_name = self.temp_mapping.get(utt.speaker) or utt.speaker_name

            # Color code speakers
            speaker_color = self._get_speaker_color(utt.speaker)

            preview.write(f"[dim]{time_str}[/dim] [{speaker_color}]{speaker_name}:[/{speaker_color}]")
            preview.write(f"  {utt.text[:200]}..." if len(utt.text) > 200 else f"  {utt.text}")
            preview.write("")

        if len(self.meeting.utterances) > 20:
            preview.write(f"[dim]... and {len(self.meeting.utterances) - 20} more utterances[/dim]")

    def _get_speaker_color(self, speaker: str) -> str:
        colors = ["cyan", "green", "magenta", "yellow", "blue", "red"]
        try:
            speaker_num = int(speaker.replace("Speaker ", "").replace("A", "0").replace("B", "1").replace("C", "2"))
            return colors[speaker_num % len(colors)]
        except:
            return "white"

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Update preview as user types"""
        if event.input.id.startswith("speaker_"):
            speaker = event.input.id.replace("speaker_", "")
            self.temp_mapping[speaker] = event.value.strip() or f"Speaker {speaker}"
            self.update_preview()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            await self.action_save()

    async def action_save(self) -> None:
        mapping = {}
        for speaker, input_widget in self.speaker_inputs.items():
            name = input_widget.value.strip()
            if name:
                mapping[speaker] = name
            else:
                mapping[speaker] = f"Speaker {speaker}"

        self.meeting.update_speaker_names(mapping)
        self.app.pop_screen()
        # Return to meeting list and refresh
        while len(self.app.screen_stack) > 1:
            if isinstance(self.app.screen_stack[-1], MeetingListScreen):
                self.app.screen_stack[-1].refresh_meetings()
                break
            self.app.pop_screen()

class MeetingDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("/", "search", "Search"),
        Binding("n", "next_match", "Next Match"),
        Binding("p", "prev_match", "Previous Match"),
        Binding("e", "edit_speakers", "Edit Speakers"),
    ]

    CSS = """
    MeetingDetailScreen {
        align: center middle;
    }

    #detail-container {
        width: 95%;
        height: 95%;
        border: solid $primary;
        padding: 1;
    }

    #meeting-info {
        height: 5;
        border-bottom: solid $primary;
        padding: 1;
    }

    #search-container {
        height: 3;
        border-bottom: dashed $primary;
        padding: 0 1;
        display: none;
    }

    #search-container.visible {
        display: block;
    }

    #transcript-log {
        height: 1fr;
        border: none;
        padding: 1;
    }

    .search-highlight {
        background: yellow;
        color: black;
    }
    """

    def __init__(self, meeting: Meeting):
        super().__init__()
        self.meeting = meeting
        self.search_active = False
        self.search_term = ""
        self.search_matches = []
        self.current_match_index = -1

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="detail-container"):
            with Horizontal(id="meeting-info"):
                yield Static(self._format_meeting_info())

            with Horizontal(id="search-container"):
                yield Input(placeholder="Search transcript...", id="search-input")
                yield Static("", id="search-status")

            yield RichLog(id="transcript-log", highlight=True, markup=True)
        yield Footer()

    def _format_meeting_info(self) -> str:
        duration_str = f"{self.meeting.duration // 60}:{self.meeting.duration % 60:02d}" if self.meeting.duration else "N/A"
        speakers = len(self.meeting.get_unique_speakers()) if self.meeting.utterances else 0
        return f"[bold]{self.meeting.name}[/bold] | Date: {self.meeting.date.strftime('%Y-%m-%d %H:%M')} | Duration: {duration_str} | Speakers: {speakers}"

    async def on_mount(self) -> None:
        self.display_transcript()

    def display_transcript(self, highlight_term: str = "") -> None:
        log = self.query_one("#transcript-log", RichLog)
        log.clear()

        if not self.meeting.utterances:
            log.write("[dim]No transcript available for this meeting[/dim]")
            return

        console = Console()

        for utt in self.meeting.utterances:
            time_str = f"{utt.start // 60000:02d}:{(utt.start // 1000) % 60:02d}"

            speaker_color = self._get_speaker_color(utt.speaker)
            text = utt.text

            if highlight_term:
                pattern = re.compile(re.escape(highlight_term), re.IGNORECASE)
                text = pattern.sub(lambda m: f"[bold yellow on black]{m.group()}[/bold yellow on black]", text)

            log.write(f"[dim]{time_str}[/dim] [{speaker_color}]{utt.speaker_name}:[/{speaker_color}]")
            log.write(f"  {text}")
            log.write("")

    def _get_speaker_color(self, speaker: str) -> str:
        colors = ["cyan", "green", "magenta", "yellow", "blue", "red"]
        try:
            speaker_num = int(speaker.replace("Speaker ", "").replace("A", "0").replace("B", "1").replace("C", "2"))
            return colors[speaker_num % len(colors)]
        except:
            return "white"

    async def action_search(self) -> None:
        search_container = self.query_one("#search-container")
        search_input = self.query_one("#search-input", Input)

        if not self.search_active:
            search_container.add_class("visible")
            self.search_active = True
            search_input.focus()
        else:
            search_container.remove_class("visible")
            self.search_active = False
            self.search_term = ""
            self.display_transcript()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.search_term = event.value
            self.find_matches()
            self.display_transcript(self.search_term)
            self.update_search_status()

    def find_matches(self) -> None:
        self.search_matches = []
        self.current_match_index = -1

        if not self.search_term:
            return

        for i, utt in enumerate(self.meeting.utterances):
            if self.search_term.lower() in utt.text.lower():
                self.search_matches.append(i)

        if self.search_matches:
            self.current_match_index = 0

    def update_search_status(self) -> None:
        status = self.query_one("#search-status", Static)
        if self.search_matches:
            status.update(f"Found {len(self.search_matches)} matches")
        elif self.search_term:
            status.update("No matches found")
        else:
            status.update("")

    async def action_next_match(self) -> None:
        if self.search_matches and self.current_match_index < len(self.search_matches) - 1:
            self.current_match_index += 1
            self.scroll_to_match()

    async def action_prev_match(self) -> None:
        if self.search_matches and self.current_match_index > 0:
            self.current_match_index -= 1
            self.scroll_to_match()

    def scroll_to_match(self) -> None:
        if self.search_matches and 0 <= self.current_match_index < len(self.search_matches):
            log = self.query_one("#transcript-log", RichLog)
            match_index = self.search_matches[self.current_match_index]
            log.scroll_to(match_index * 3, animate=True)

    async def action_edit_speakers(self) -> None:
        self.app.push_screen(SpeakerAssignmentScreen(self.meeting))

    async def action_back(self) -> None:
        self.app.pop_screen()

class MeetingListScreen(Screen):
    BINDINGS = [
        Binding("n", "new_recording", "New Recording"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete", "Delete Selected"),
        Binding("e", "edit_speakers", "Edit Speakers"),
        Binding("t", "reprocess", "Reprocess Audio"),
        Binding("enter", "view_details", "View Details"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    MeetingListScreen {
        align: center middle;
    }

    #meetings-table {
        width: 100%;
        height: 80%;
        border: solid $primary;
        margin: 1;
    }

    #no-meetings {
        align: center middle;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(APP_NAME, id="title")
        yield DataTable(id="meetings-table")
        yield Footer()

    async def on_mount(self) -> None:
        self.refresh_meetings()
        # Focus the table for keyboard navigation
        table = self.query_one("#meetings-table", DataTable)
        table.focus()

    def refresh_meetings(self) -> None:
        table = self.query_one("#meetings-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"

        table.add_columns("Date", "Name", "Duration", "Speakers", "Status")

        meetings = MeetingManager.list_meetings()

        if not meetings:
            table.add_row("No meetings", "", "", "", "")
        else:
            for meeting in meetings:
                duration_str = f"{meeting.duration // 60}:{meeting.duration % 60:02d}" if meeting.duration else "N/A"
                speakers = len(meeting.get_unique_speakers()) if meeting.utterances else 0
                table.add_row(
                    meeting.date.strftime("%Y-%m-%d %H:%M"),
                    meeting.name,
                    duration_str,
                    str(speakers),
                    meeting.status,
                    key=meeting.id
                )

    async def action_new_recording(self) -> None:
        self.app.push_screen(RecordingScreen())

    async def action_refresh(self) -> None:
        self.refresh_meetings()

    async def action_delete(self) -> None:
        table = self.query_one("#meetings-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)[0]
            if row_key and row_key != "No meetings":
                meetings = MeetingManager.list_meetings()
                for meeting in meetings:
                    if meeting.date.strftime("%Y-%m-%d %H:%M") == row_key:
                        MeetingManager.delete_meeting(meeting.id)
                        self.refresh_meetings()
                        break

    async def action_edit_speakers(self) -> None:
        table = self.query_one("#meetings-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)[0]
            if row_key and row_key != "No meetings":
                meetings = MeetingManager.list_meetings()
                for meeting in meetings:
                    if meeting.date.strftime("%Y-%m-%d %H:%M") == row_key:
                        self.app.push_screen(SpeakerAssignmentScreen(meeting))
                        break

    async def action_reprocess(self) -> None:
        table = self.query_one("#meetings-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)[0]
            if row_key and row_key != "No meetings":
                meetings = MeetingManager.list_meetings()
                for meeting in meetings:
                    if meeting.date.strftime("%Y-%m-%d %H:%M") == row_key and meeting.audio_path:
                        self.app.push_screen(TranscriptionScreen(meeting.audio_path, meeting.name))
                        break

    async def action_view_details(self) -> None:
        table = self.query_one("#meetings-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)[0]
            if row_key and row_key != "No meetings":
                meetings = MeetingManager.list_meetings()
                for meeting in meetings:
                    if meeting.date.strftime("%Y-%m-%d %H:%M") == row_key:
                        self.app.push_screen(MeetingDetailScreen(meeting))
                        break

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key != "No meetings":
            meetings = MeetingManager.list_meetings()
            for meeting in meetings:
                if meeting.id == event.row_key:
                    self.app.push_screen(MeetingDetailScreen(meeting))
                    break

    async def action_quit(self) -> None:
        self.app.exit()

class MeetingRecorderApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin: 1;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(MeetingListScreen())

if __name__ == "__main__":
    app = MeetingRecorderApp()
    app.run()