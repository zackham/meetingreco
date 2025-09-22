import subprocess
import time
from pathlib import Path
from typing import Optional, List
import os
import tempfile
from datetime import datetime
import threading

class AudioRecorder:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.monitor_process: Optional[subprocess.Popen] = None
        self.mic_process: Optional[subprocess.Popen] = None
        self.current_file: Optional[Path] = None
        self.recording_parts: List[Path] = []
        self.is_recording = False
        self.start_time: Optional[float] = None
        self.total_duration = 0.0
        self.monitor_thread: Optional[threading.Thread] = None

    def get_powerconf_devices(self):
        """Get PowerConf devices for microphone and monitor"""
        # These are your PowerConf devices based on the pactl output
        mic = "alsa_input.usb-Anker_PowerConf_S3_A3321-DEV-SN1-01.mono-fallback"
        monitor = "alsa_output.usb-Anker_PowerConf_S3_A3321-DEV-SN1-01.analog-stereo.monitor"

        # Verify they exist
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                check=True
            )

            sources = result.stdout

            # Check if devices are available
            if mic not in sources:
                print(f"Warning: PowerConf mic not found, using default")
                mic = None
            if monitor not in sources:
                print(f"Warning: PowerConf monitor not found, using default")
                monitor = None

        except Exception as e:
            print(f"Error checking devices: {e}")

        return mic, monitor

    def start(self) -> bool:
        if self.is_recording:
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = Path(tempfile.gettempdir()) / f"temp_audio_{timestamp}_{len(self.recording_parts)}.mp3"
        self.recording_parts.append(self.current_file)

        mic, monitor = self.get_powerconf_devices()

        print(f"Recording from PowerConf - Mic: {mic}, Monitor: {monitor}")

        # Create temporary WAV files for each source
        monitor_wav = Path(tempfile.gettempdir()) / f"monitor_{timestamp}.wav"
        mic_wav = Path(tempfile.gettempdir()) / f"mic_{timestamp}.wav"

        try:
            # Record system audio from PowerConf monitor
            if monitor:
                self.monitor_process = subprocess.Popen(
                    ["parecord", "--device", monitor, "--file-format=wav", str(monitor_wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Fallback to default monitor
                self.monitor_process = subprocess.Popen(
                    ["parecord", "--file-format=wav", str(monitor_wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # Record microphone from PowerConf
            if mic:
                self.mic_process = subprocess.Popen(
                    ["parecord", "--device", mic, "--file-format=wav", str(mic_wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Fallback to default source
                self.mic_process = subprocess.Popen(
                    ["parecord", "--file-format=wav", str(mic_wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            self.is_recording = True
            self.start_time = time.time()

            # Store temp files for later mixing
            self.monitor_wav = monitor_wav
            self.mic_wav = mic_wav

            # Quick check that processes started
            time.sleep(0.1)
            if self.monitor_process.poll() is not None or self.mic_process.poll() is not None:
                print("Warning: One of the recording processes died immediately")
                # Continue anyway, one source is better than none

            return True
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def pause(self) -> bool:
        if not self.is_recording:
            return False

        # Stop both recordings
        if self.monitor_process:
            self.monitor_process.terminate()
            self.monitor_process.wait()

        if self.mic_process:
            self.mic_process.terminate()
            self.mic_process.wait()

        if self.start_time:
            self.total_duration += time.time() - self.start_time

        # Mix the two WAV files into MP3
        if hasattr(self, 'monitor_wav') and hasattr(self, 'mic_wav'):
            monitor_exists = self.monitor_wav.exists() and self.monitor_wav.stat().st_size > 1000
            mic_exists = self.mic_wav.exists() and self.mic_wav.stat().st_size > 1000

            if monitor_exists and mic_exists:
                # Both files exist, mix them
                cmd = [
                    "ffmpeg",
                    "-i", str(self.monitor_wav),
                    "-i", str(self.mic_wav),
                    "-filter_complex",
                    "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=longest:dropout_transition=2,loudnorm",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    "-y",
                    str(self.current_file)
                ]
            elif monitor_exists:
                # Only monitor exists
                print("Note: Only system audio was captured")
                cmd = [
                    "ffmpeg", "-i", str(self.monitor_wav),
                    "-af", "loudnorm",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    "-y", str(self.current_file)
                ]
            elif mic_exists:
                # Only mic exists
                print("Note: Only microphone was captured")
                cmd = [
                    "ffmpeg", "-i", str(self.mic_wav),
                    "-af", "loudnorm",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    "-y", str(self.current_file)
                ]
            else:
                print("Error: No audio was captured")
                self.is_recording = False
                return False

            try:
                result = subprocess.run(cmd, capture_output=True, check=True)
                # Clean up WAV files
                self.monitor_wav.unlink(missing_ok=True)
                self.mic_wav.unlink(missing_ok=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to process audio: {e.stderr.decode()[:500]}")

        self.is_recording = False
        self.monitor_process = None
        self.mic_process = None
        return True

    def resume(self) -> bool:
        return self.start()

    def stop(self) -> Optional[Path]:
        if self.is_recording:
            self.pause()

        if not self.recording_parts:
            return None

        # Remove any empty parts
        self.recording_parts = [p for p in self.recording_parts if p.exists() and p.stat().st_size > 1000]

        if not self.recording_parts:
            print("No valid audio recordings found")
            return None

        if len(self.recording_parts) == 1:
            return self.recording_parts[0]

        # Merge multiple parts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(tempfile.gettempdir()) / f"meeting_audio_{timestamp}.mp3"

        concat_file = Path(tempfile.gettempdir()) / f"concat_{timestamp}.txt"
        with open(concat_file, 'w') as f:
            for part in self.recording_parts:
                if part.exists():
                    f.write(f"file '{part}'\n")

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-y",
            str(output_file)
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)

            # Clean up part files
            for part in self.recording_parts:
                part.unlink(missing_ok=True)
            concat_file.unlink(missing_ok=True)

            self.recording_parts = []
            self.total_duration = 0.0
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"Failed to merge audio files: {e}")
            return self.recording_parts[0] if self.recording_parts else None

    def get_duration(self) -> float:
        if self.is_recording and self.start_time:
            return self.total_duration + (time.time() - self.start_time)
        return self.total_duration

    def get_file_size(self) -> int:
        total_size = 0
        for part in self.recording_parts:
            if part.exists():
                total_size += part.stat().st_size

        # Also count temporary WAV files if recording
        if self.is_recording:
            if hasattr(self, 'monitor_wav') and self.monitor_wav.exists():
                total_size += self.monitor_wav.stat().st_size
            if hasattr(self, 'mic_wav') and self.mic_wav.exists():
                total_size += self.mic_wav.stat().st_size

        return total_size