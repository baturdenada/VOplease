#!/usr/bin/env python3
"""
VOplease - Text-to-Speech Dashboard
A comprehensive TTS dashboard supporting multiple providers with voice selection,
speed control, unlimited text length, and audio playback/download.
"""

import asyncio
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pathlib import Path
import json
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.manager import config
from providers import (
    ProviderRegistry, TTSOptions, TTSProvider,
    EdgeTTSProvider, ElevenLabsProvider, AzureTTSProvider, SiliconFlowProvider
)
from utils.audio_player import audio_player
from utils.helpers import (
    sanitize_filename, format_duration, format_file_size,
    get_output_path, estimate_audio_duration
)

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class VOpleaseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("VOplease - Text-to-Speech Dashboard")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        # Initialize variables
        self.current_provider: TTSProvider = None
        self.current_provider_name = ""
        self.voices = []
        self.current_audio_data = None
        self.current_audio_format = None
        self.is_generating = False
        self.loop = asyncio.new_event_loop()
        
        # Load config
        self.load_config()
        
        # Initialize providers
        self.init_providers()
        
        # Setup UI
        self.setup_ui()
        
        # Bind audio player callback
        audio_player.add_callback(self.on_audio_update)
        
        # Start async loop in background
        self.async_thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.async_thread.start()
        
        # Start UI update loop
        self.after(100, self.update_ui)
        
        # Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def load_config(self):
        data = config.load()
        self.last_provider = data.get("last_provider", "edge")
        self.last_voice = data.get("last_voice", "")
        self.speed = data.get("speed", 1.0)
        self.output_format = data.get("output_format", "mp3")
        self.output_directory = data.get(
            "output_directory", str(Path.home() / "Documents" / "VOplease Audio")
        )
        theme = data.get("theme", "dark")
        ctk.set_appearance_mode(theme)
    
    def save_config(self):
        data = config.load()
        data["last_provider"] = self.current_provider_name
        data["last_voice"] = self.voice_var.get() if hasattr(self, 'voice_var') else ""
        data["speed"] = self.speed_var.get() if hasattr(self, 'speed_var') else 1.0
        data["output_format"] = self.format_var.get() if hasattr(self, 'format_var') else "mp3"
        data["output_directory"] = (
            self.output_dir_var.get() if hasattr(self, "output_dir_var") else self.output_directory
        )
        config.save(data)
    
    def init_providers(self):
        """Initialize TTS providers with saved API keys"""
        self.providers = {}
        provider_classes = ProviderRegistry.get_all()
        
        for name, cls in provider_classes.items():
            api_key = config.get_api_key(name)
            if name == "azure":
                provider = cls(api_key=config.get_api_key(name), region="eastus")
            elif name == "siliconflow":
                provider = cls(api_key=config.get_api_key(name))
            else:
                provider = cls(api_key=config.get_api_key(name))
            self.providers[name] = provider
        
        # Auto-select last used provider
        if self.last_provider in self.providers:
            self.select_provider(self.last_provider)
        else:
            # Default to Edge TTS (free)
            self.select_provider("edge")
    
    def setup_ui(self):
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Left sidebar - Provider selection and settings
        self.setup_sidebar()
        
        # Main content area
        self.setup_main_area()
        
        # Bottom bar - Audio player
        self.setup_audio_player()
    
    def setup_sidebar(self):
        self.sidebar = ctk.CTkScrollableFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        # Title
        title_label = ctk.CTkLabel(
            self.sidebar, 
            text="VOplease", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(20, 10))
        
        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Text-to-Speech Dashboard",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle.pack(pady=(0, 20))
        
        # Provider selection
        provider_frame = ctk.CTkFrame(self.sidebar)
        provider_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(provider_frame, text="Provider", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.provider_var = ctk.StringVar(value=self.current_provider_name)
        self.provider_combo = ctk.CTkComboBox(
            provider_frame,
            values=list(ProviderRegistry.get_all().keys()),
            variable=self.provider_var,
            command=self.on_provider_change,
            width=250
        )
        self.provider_combo.pack(fill="x", padx=10, pady=(0, 10))
        
        # API Key section
        self.api_frame = ctk.CTkFrame(provider_frame)
        self.api_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(self.api_frame, text="API Key", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.api_key_var = ctk.StringVar()
        self.api_key_entry = ctk.CTkEntry(
            self.api_frame,
            textvariable=self.api_key_var,
            placeholder_text="Enter API key (leave blank for free providers)",
            show="*",
            width=250
        )
        self.api_key_entry.pack(fill="x", padx=10, pady=(0, 5))
        
        # Show/Hide button
        self.show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self.api_frame,
            text="Show API Key",
            variable=self.show_key_var,
            command=self.toggle_api_key_visibility
        ).pack(anchor="w", padx=10, pady=(0, 10))
        
        # Save API Key button
        ctk.CTkButton(
            self.api_frame,
            text="Save API Key",
            command=self.save_api_key,
            width=250
        ).pack(padx=10, pady=(0, 10))
        
        # Voice selection
        voice_frame = ctk.CTkFrame(self.sidebar)
        voice_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(voice_frame, text="Voice", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.voice_var = ctk.StringVar()
        self.voice_combo = ctk.CTkComboBox(
            voice_frame,
            values=[],
            variable=self.voice_var,
            width=250,
            command=self.on_voice_change
        )
        self.voice_combo.pack(fill="x", padx=10, pady=(0, 10))
        
        # Refresh voices button
        ctk.CTkButton(
            voice_frame,
            text="Refresh Voices",
            command=self.refresh_voices,
            width=250,
            height=30
        ).pack(padx=10, pady=(0, 10))
        
        # Settings frame
        settings_frame = ctk.CTkFrame(self.sidebar)
        settings_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(settings_frame, text="Settings", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        # Speed slider
        speed_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        speed_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(speed_frame, text="Speed: 1.0x", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.speed_var = ctk.DoubleVar(value=1.0)
        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.25,
            to=4.0,
            variable=self.speed_var,
            command=self.on_speed_change,
            number_of_steps=150
        )
        self.speed_slider.pack(fill="x", pady=5)
        self.speed_label = ctk.CTkLabel(speed_frame, text="1.0x", font=ctk.CTkFont(size=12))
        self.speed_label.pack(anchor="e")
        
        # Pitch slider
        pitch_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        pitch_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(pitch_frame, text="Pitch: 0", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.pitch_var = ctk.DoubleVar(value=0.0)
        self.pitch_slider = ctk.CTkSlider(
            pitch_frame,
            from_=-20,
            to=20,
            variable=self.pitch_var,
            command=self.on_pitch_change,
            number_of_steps=40
        )
        self.pitch_slider.pack(fill="x", pady=5)
        self.pitch_label = ctk.CTkLabel(pitch_frame, text="0", font=ctk.CTkFont(size=12))
        self.pitch_label.pack(anchor="e")
        
        # Volume slider
        volume_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        volume_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(volume_frame, text="Volume: 1.0", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.volume_var = ctk.DoubleVar(value=1.0)
        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0.0,
            to=2.0,
            variable=self.volume_var,
            command=self.on_volume_change,
            number_of_steps=40
        )
        self.volume_slider.pack(fill="x", pady=5)
        self.volume_label = ctk.CTkLabel(volume_frame, text="1.0", font=ctk.CTkFont(size=12))
        self.volume_label.pack(anchor="e")
        
        # Output format
        format_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        format_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(format_frame, text="Output Format", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.format_var = ctk.StringVar(value=self.output_format)
        self.format_combo = ctk.CTkComboBox(
            format_frame,
            values=["mp3", "wav", "ogg"],
            variable=self.format_var,
            width=250
        )
        self.format_combo.pack(fill="x", pady=5)

        # Theme toggle
        theme_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=10, pady=10)
        
        self.theme_var = ctk.StringVar(value="dark")
        ctk.CTkSwitch(
            theme_frame,
            text="Dark Mode",
            variable=self.theme_var,
            onvalue="dark",
            offvalue="light",
            command=self.toggle_theme
        ).pack(anchor="w")
    
    def setup_main_area(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Text input area
        text_frame = ctk.CTkFrame(self.main_frame)
        text_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Header with char count
        header_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header_frame, 
            text="Text Input (No Character Limit)", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        
        self.char_count_label = ctk.CTkLabel(
            header_frame, 
            text="Characters: 0 | Estimated Duration: 0:00",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.char_count_label.grid(row=0, column=1, sticky="e")
        
        # Text area
        self.text_area = ctk.CTkTextbox(
            text_frame,
            height=300,
            font=ctk.CTkFont(size=13),
            wrap="word"
        )
        self.monospace_font = ctk.CTkFont(family="Consolas", size=12)
        self.text_area.configure(font=self.monospace_font)
        self.monospace_font = self.text_area.cget("font")
        self.text_area.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.text_area.bind("<KeyRelease>", self.on_text_change)
        
        # Output directory
        output_dir_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        output_dir_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 8))
        output_dir_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output_dir_frame, text="Save to:").grid(row=0, column=0, padx=(0, 8))
        self.output_dir_var = ctk.StringVar(value=self.output_directory)
        self.output_dir_entry = ctk.CTkEntry(
            output_dir_frame, textvariable=self.output_dir_var
        )
        self.output_dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            output_dir_frame,
            text="Choose Folder...",
            command=self.choose_output_directory,
            width=130,
        ).grid(row=0, column=2)

        # Buttons frame
        button_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.generate_btn = ctk.CTkButton(
            button_frame,
            text="🎵 Generate Audio",
            command=self.generate_audio,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.generate_btn.pack(side="left", padx=5, fill="x", expand=True)
        
        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="⏹ Stop",
            command=self.stop_generation,
            height=45,
            font=ctk.CTkFont(size=16),
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5, fill="x", expand=True)
        
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑 Clear",
            command=self.clear_text,
            height=45,
            font=ctk.CTkFont(size=16),
            fg_color="#546E7A",
            hover_color="#455A64"
        )
        self.clear_btn.pack(side="left", padx=5, fill="x", expand=True)
        
        # Status/Progress frame
        status_frame = ctk.CTkFrame(self.main_frame)
        status_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(1, weight=1)
        
        # Progress bar
        self.progress_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.progress_label.grid(row=0, column=0, sticky="w")
        
        self.progress_bar = ctk.CTkProgressBar(status_frame)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()  # Hide initially
        
        # Log area
        ctk.CTkLabel(status_frame, text="Activity Log", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, sticky="w", padx=10, pady=(5, 0)
        )
        
        self.log_text = ctk.CTkTextbox(
            status_frame,
            height=150,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.monospace_font = ctk.CTkFont(family="Consolas", size=11)
        self.log_text.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log_text.configure(state="disabled")
    
    def setup_audio_player(self):
        self.player_frame = ctk.CTkFrame(self, height=100, corner_radius=0)
        self.player_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        self.mplayer_frame = ctk.CTkFrame(self.player_frame, fg_color="transparent")
        self.mplayer_frame.pack(fill="x", padx=20, pady=10)
        
        # Now playing info
        self.now_playing_label = ctk.CTkLabel(
            self.mplayer_frame,
            text="No audio loaded",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.mnow_playing_label = self.now_playing_label
        self.now_playing_label.pack(side="left", padx=10)
        
        # Time labels
        self.time_label = ctk.CTkLabel(
            self.mplayer_frame,
            text="0:00 / 0:00",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.time_label.pack(side="right", padx=10)
        
        # Progress bar
        self.playback_progress = ctk.CTkProgressBar(self.mplayer_frame, width=300)
        self.playback_progress.pack(side="right", padx=10)
        self.playback_progress.set(0)
        
        # Controls
        controls_frame = ctk.CTkFrame(self.mplayer_frame, fg_color="transparent")
        controls_frame.pack(side="right", padx=10)
        
        self.prev_btn = ctk.CTkButton(
            controls_frame, text="⏮", width=40, height=40,
            command=self.prev_audio
        )
        self.prev_btn.pack(side="left", padx=2)
        
        self.play_btn = ctk.CTkButton(
            controls_frame, text="▶", width=40, height=40,
            command=self.toggle_playback
        )
        self.play_btn.pack(side="left", padx=2)
        
        self.next_btn = ctk.CTkButton(
            controls_frame, text="⏭", width=40, height=40,
            command=self.next_audio
        )
        self.next_btn.pack(side="left", padx=2)
        
        # Volume
        volume_frame = ctk.CTkFrame(self.mplayer_frame, fg_color="transparent")
        volume_frame.pack(side="right", padx=10)
        
        ctk.CTkLabel(volume_frame, text="🔊", font=ctk.CTkFont(size=14)).pack(side="left")
        self.volume_slider = ctk.CTkSlider(
            volume_frame, from_=0.0, to=1.0, width=100,
            command=lambda v: audio_player.set_volume(v)
        )
        self.volume_slider.pack(side="left", padx=5)
        self.volume_slider.set(0.7)
        
        # Download button
        self.download_btn = ctk.CTkButton(
            self.mplayer_frame,
            text="💾 Download",
            command=self.download_audio,
            width=120,
            height=40,
            state="disabled"
        )
        self.download_btn.pack(side="right", padx=10)
    
    def on_provider_change(self, value):
        self.select_provider(value)
    
    def select_provider(self, name):
        if name not in self.providers:
            return
        self.current_provider = self.providers[name]
        self.current_provider_name = name
        
        # Update UI if already created
        if hasattr(self, 'provider_var'):
            self.provider_var.set(name)
            
            # Show/hide API key field
            if hasattr(self, 'api_frame'):
                if self.current_provider.requires_api_key:
                    self.api_frame.pack(fill="x", padx=10, pady=(0, 10))
                else:
                    self.api_frame.pack_forget()
            
            # Load API key
            api_key = config.get_api_key(name)
            if hasattr(self, 'api_key_var'):
                self.api_key_var.set(api_key if api_key else "")
            
            # Refresh voices
            self.refresh_voices()
            
            self.log(f"Switched to {self.current_provider.display_name}")
        self.save_config()
    
    def on_voice_change(self, value):
        self.last_voice = value
        self.save_config()
    
    def on_speed_change(self, value):
        self.speed_var.set(round(value, 2))
        self.speed_label.configure(text=f"{self.speed_var.get():.2f}x")
        self.update_duration_estimate()
    
    def on_pitch_change(self, value):
        self.pitch_var.set(round(value, 1))
        self.pitch_label.configure(text=f"{self.pitch_var.get():.1f}")
    
    def on_volume_change(self, value):
        self.volume_var.set(round(value, 2))
        self.volume_label.configure(text=f"{self.volume_var.get():.2f}")
    
    def toggle_api_key_visibility(self):
        if self.show_key_var.get():
            self.api_key_entry.configure(show="")
        else:
            self.api_key_entry.configure(show="*")
    
    def save_api_key(self):
        api_key = self.api_key_var.get().strip()
        if api_key:
            config.set_api_key(self.current_provider_name, api_key)
            # Reinitialize provider with new key
            provider_class = ProviderRegistry.get(self.current_provider_name)
            if self.current_provider_name == "azure":
                self.providers[self.current_provider_name] = provider_class(api_key=api_key, region="eastus")
            else:
                self.providers[self.current_provider_name] = provider_class(api_key=api_key)
            self.current_provider = self.providers[self.current_provider_name]
            self.log(f"API key saved for {self.current_provider.display_name}")
            messagebox.showinfo("Success", "API key saved successfully!")
        else:
            messagebox.showwarning("Warning", "Please enter an API key")
    
    def refresh_voices(self):
        if not self.current_provider:
            return
        
        self.log(f"Fetching voices for {self.current_provider.display_name}...")
        
        async def fetch():
            try:
                voices = await self.current_provider.get_voices()
                self.voices = voices
                voice_names = [f"{v.name} ({v.id})" for v in voices]
                
                # Update combo on main thread
                self.after(0, lambda: self.update_voice_combo(voice_names))
                self.after(0, lambda: self.log(f"Loaded {len(voices)} voices"))
            except Exception as e:
                self.after(0, lambda: self.log(f"Error loading voices: {e}"))
        
        asyncio.run_coroutine_threadsafe(fetch(), self.loop)
    
    def update_voice_combo(self, voice_names):
        # voice_names is a list of "Name (ID)" strings
        # Store mapping for ID lookup
        self._voice_map = {}
        display_names = []
        for name in voice_names:
            if "(" in name and ")" in name:
                display_name = name.split("(")[0].strip()
                voice_id = name.split("(")[-1].rstrip(")")
                self._voice_map[display_name] = voice_id
                display_names.append(display_name)
            else:
                display_names.append(name)
                self._voice_map[name] = name
        
        self.voice_combo.configure(values=display_names)
        if display_names:
            # Try to select last used voice
            if self.last_voice and self.last_voice in display_names:
                self.voice_combo.set(self.last_voice)
            else:
                self.voice_combo.set(display_names[0])
                self.voice_var.set(display_names[0])
    
    def on_text_change(self, event=None):
        text = self.text_area.get("1.0", "end-1c")
        char_count = len(text)
        duration = estimate_audio_duration(text, self.speed_var.get())
        
        self.char_count_label.configure(
            text=f"Characters: {char_count:,} | Estimated Duration: {format_duration(duration)}"
        )
        
        # Warn if text is very long
        if char_count > 5000:
            self.char_count_label.configure(text_color="orange")
        elif char_count > 10000:
            self.char_count_label.configure(text_color="red")
        else:
            self.char_count_label.configure(text_color="gray")
    
    def update_duration_estimate(self):
        text = self.text_area.get("1.0", "end-1c")
        duration = estimate_audio_duration(text, self.speed_var.get())
        self.char_count_label.configure(
            text=f"Characters: {len(text):,} | Estimated Duration: {format_duration(duration)}"
        )
    
    def clear_text(self):
        self.text_area.delete("1.0", "end")
        self.on_text_change()
    
    def log(self, message: str):
        """Add message to log"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def generate_audio(self):
        if self.is_generating:
            return
        
        text = self.text_area.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter some text")
            return
        
        if not self.current_provider:
            messagebox.showwarning("Warning", "Please select a provider")
            return
        
        voice_id = self.get_selected_voice_id()
        if not voice_id:
            messagebox.showwarning("Warning", "Please select a voice")
            return
        
        if self.current_provider.requires_api_key and not self.current_provider.api_key:
            messagebox.showwarning("Warning", f"Please enter API key for {self.current_provider.display_name}")
            return
        
        # Check text length
        if len(text) > self.current_provider.max_text_length:
            if not messagebox.askyesno(
                "Long Text Warning",
                f"Text length ({len(text):,} chars) exceeds recommended limit "
                f"({self.current_provider.max_text_length:,} chars). "
                "This may cause issues. Continue anyway?"
            ):
                return
        
        # Start generation
        self.is_generating = True
        self.generate_btn.configure(state="disabled", text="⏳ Generating...")
        self.stop_btn.configure(state="normal")
        self.progress_bar.grid()
        self.progress_bar.set(0)
        self.progress_label.configure(text="Generating audio...")
        self.progress_bar.set(0.1)
        
        self.log(f"Generating audio with {self.current_provider.display_name}...")
        self.log(f"Voice: {self.voice_var.get()}")
        self.log(f"Speed: {self.speed_var.get():.2f}x, Pitch: {self.pitch_var.get():.1f}")
        
        # Run generation in async thread
        options = TTSOptions(
            text=self.text_area.get("1.0", "end-1c"),
            voice_id=self.get_selected_voice_id(),
            speed=self.speed_var.get(),
            pitch=self.pitch_var.get(),
            volume=self.volume_var.get(),
            output_format=self.format_var.get()
        )
        
        asyncio.run_coroutine_threadsafe(self.generate_audio_async(options), self.loop)
    
    def get_selected_voice_id(self):
        """Extract voice ID from combo selection"""
        selection = self.voice_var.get()
        # Use the voice map if available
        if hasattr(self, '_voice_map') and selection in self._voice_map:
            return self._voice_map[selection]
        # Fallback: extract from parentheses
        if "(" in selection and ")" in selection:
            return selection.split("(")[-1].rstrip(")")
        return selection
    
    async def generate_audio_async(self, options: TTSOptions):
        try:
            self.loop.call_soon_threadsafe(self.update_progress, 0.3, "Synthesizing...")
            audio_data = await self.current_provider.synthesize(options)
            
            self.loop.call_soon_threadsafe(self.update_progress, 0.8, "Processing audio...")
            
            if audio_data:
                self.current_audio_data = audio_data
                self.loop.call_soon_threadsafe(
                    self.on_generation_complete, audio_data, options.output_format
                )
            else:
                self.loop.call_soon_threadsafe(self.on_generation_error, "No audio data returned")
                
        except Exception as e:
            self.loop.call_soon_threadsafe(self.on_generation_error, str(e))
    
    def update_progress(self, progress: float, message: str):
        self.progress_bar.set(progress)
        self.progress_label.configure(text=message)
        self.log(message)
    
    def on_generation_complete(self, audio_data: bytes, audio_format: str):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="🎵 Generate Audio")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="Generation complete!")
        self.progress_bar.grid_remove()
        
        # Load into player
        self.current_audio_format = audio_format
        if audio_player.load(self.current_audio_data, self.current_audio_format):
            self.now_playing_label.configure(text=f"Generated: {len(self.current_audio_data):,} bytes")
            self.download_btn.configure(state="normal")
            self.play_btn.configure(text="▶")
            self.log(f"Audio generated successfully! Duration: {format_duration(audio_player.get_duration())}")
        else:
            self.log("Error: Failed to load audio into player")
            messagebox.showerror(
                "Playback Error",
                "The audio was generated, but it could not be prepared for playback. "
                "You can still download the generated file.",
            )
            self.download_btn.configure(state="normal")
    
    def on_generation_error(self, error: str):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="🎵 Generate Audio")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.grid_remove()
        self.progress_label.configure(text="Error")
        self.log(f"Generation error: {error}")
        messagebox.showerror("Generation Error", error)
    
    def stop_generation(self):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="🎵 Generate Audio")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.grid_remove()
        self.progress_label.configure(text="Cancelled")
        self.log("Generation cancelled by user")
    
    def toggle_playback(self):
        if audio_player.is_playing():
            audio_player.pause()
            self.play_btn.configure(text="▶")
        else:
            audio_player.play()
            self.play_btn.configure(text="⏸")
    
    def prev_audio(self):
        pass
    
    def next_audio(self):
        pass
    
    def on_audio_update(self, is_playing: bool, position: float, duration: float):
        """Callback from audio player"""
        self.after(0, lambda: self.update_playback_ui(is_playing, position, duration))
    
    def update_playback_ui(self, is_playing: bool, position: float, duration: float):
        if is_playing:
            self.play_btn.configure(text="⏸")
        else:
            self.play_btn.configure(text="▶")
        
        if duration > 0:
            self.playback_progress.set(position / duration)
            self.time_label.configure(
                text=f"{format_duration(position)} / {format_duration(duration)}"
            )
    
    def download_audio(self):
        if not self.current_audio_data:
            messagebox.showwarning("Warning", "No audio to download")
            return
        
        text_preview = self.text_area.get("1.0", "end-1c")[:50]
        filename = sanitize_filename(text_preview)
        output_directory = self.output_dir_var.get().strip()
        if not output_directory:
            messagebox.showwarning("Warning", "Please choose an output directory")
            return
        output_format = self.current_audio_format or self.format_var.get()
        output_path = get_output_path(output_directory, filename, output_format)
        
        try:
            with open(output_path, "wb") as f:
                f.write(self.current_audio_data)
            
            file_size = Path(output_path).stat().st_size
            self.log(f"Downloaded: {Path(output_path).name} ({format_file_size(file_size)})")
            messagebox.showinfo(
                "Download Complete", 
                f"Saved to:\n{output_path}\n\nSize: {format_file_size(file_size)}"
            )
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to save: {e}")

    def choose_output_directory(self):
        selected = filedialog.askdirectory(
            title="Choose where VOplease saves generated audio",
            initialdir=self.output_dir_var.get() or str(Path.home()),
        )
        if selected:
            self.output_dir_var.set(selected)
            self.output_directory = selected
            self.save_config()
            self.log(f"Output directory: {selected}")
    
    def toggle_theme(self):
        theme = self.theme_var.get()
        ctk.set_appearance_mode(theme)
        data = config.load()
        data["theme"] = theme
        config.save(data)
    
    def update_ui(self):
        """Periodic UI update"""
        # Update playback progress
        if audio_player.is_playing():
            pos = audio_player.get_position()
            dur = audio_player.get_duration()
            if dur > 0:
                self.playback_progress.set(pos / dur)
                self.time_label.configure(
                    text=f"{format_duration(pos)} / {format_duration(dur)}"
                )
        
        self.after(100, self.update_ui)
    
    def on_closing(self):
        self.save_config()
        audio_player.cleanup()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()
    
    def log(self, message: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

def main():
    # Check if we need to install dependencies
    try:
        import customtkinter
    except ImportError:
        print("Installing dependencies...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        import customtkinter
    
    app = VOpleaseApp()
    app.mainloop()

if __name__ == "__main__":
    main()
