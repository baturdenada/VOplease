"""In-app preview for generated WAV and MP3 audio."""

from __future__ import annotations

import os
import tempfile
import time
from typing import Callable

import pygame


class AudioPlayer:
    def __init__(self):
        pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=1024)
        self._current_sound = None
        self._channel = None
        self._is_playing = False
        self._paused = False
        self._position = 0.0
        self._started_at = 0.0
        self._duration = 0.0
        self._volume = 0.7
        self._callbacks: list[Callable] = []
        self._temp_file = None

    def load(self, audio_data: bytes, format: str = "mp3") -> bool:
        """Load provider output through SDL_mixer using its real file format."""
        try:
            self.stop()
            self._remove_temp_file()
            suffix = ".wav" if (format or "mp3").lower() == "wav" else ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
                temp.write(audio_data)
                self._temp_file = temp.name

            self._current_sound = pygame.mixer.Sound(self._temp_file)
            self._current_sound.set_volume(self._volume)
            self._duration = self._current_sound.get_length()
            self._position = 0.0
            return self._duration > 0
        except Exception as exc:
            print(f"Error loading audio: {exc}")
            self._current_sound = None
            self._duration = 0.0
            return False

    def play(self):
        if not self._current_sound:
            return
        if self._paused and self._channel:
            self._channel.unpause()
            self._started_at = time.monotonic() - self._position
        else:
            self._channel = self._current_sound.play()
            self._position = 0.0
            self._started_at = time.monotonic()
        self._paused = False
        self._is_playing = self._channel is not None
        self._notify_callbacks()

    def pause(self):
        if self._is_playing and self._channel:
            self._position = self.get_position()
            self._channel.pause()
            self._paused = True
            self._is_playing = False
            self._notify_callbacks()

    def stop(self):
        if self._channel:
            self._channel.stop()
        self._channel = None
        self._is_playing = False
        self._paused = False
        self._position = 0.0
        self._notify_callbacks()

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._current_sound:
            self._current_sound.set_volume(self._volume)

    def seek(self, position: float):
        pass

    def get_position(self) -> float:
        if self._is_playing and self._channel:
            if not self._channel.get_busy():
                self._position = self._duration
                self._is_playing = False
                self._notify_callbacks()
                return self._position
            self._position = min(time.monotonic() - self._started_at, self._duration)
        return self._position

    def get_duration(self) -> float:
        return self._duration

    def is_playing(self) -> bool:
        self.get_position()
        return self._is_playing

    def is_paused(self) -> bool:
        return self._paused

    def add_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def _notify_callbacks(self):
        for callback in self._callbacks:
            try:
                callback(self._is_playing, self._position, self._duration)
            except Exception:
                pass

    def _remove_temp_file(self):
        if self._temp_file:
            try:
                os.unlink(self._temp_file)
            except OSError:
                pass
            self._temp_file = None

    def cleanup(self):
        self.stop()
        self._remove_temp_file()


audio_player = AudioPlayer()
