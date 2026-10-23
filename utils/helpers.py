import os
import re
from pathlib import Path
from typing import Optional
import unicodedata

def sanitize_filename(text: str, max_length: int = 100) -> str:
    """Sanitize text for use as filename"""
    # Remove or replace invalid characters
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    # Remove control characters
    text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate
    if len(text) > max_length:
        text = text[:max_length].strip()
    return text or "audio"

def format_duration(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def format_file_size(bytes_size: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def validate_api_key(provider: str, api_key: str) -> bool:
    """Basic API key validation"""
    if not api_key or len(api_key.strip()) < 10:
        return False
    
    provider_patterns = {
        "elevenlabs": r"^sk_[a-zA-Z0-9]{20,}",
        "azure": r"^[a-zA-Z0-9]{32}$",
        "elevenlabs": r"^sk_[a-zA-Z0-9]{20,}",
        "siliconflow": r"^sk-[a-zA-Z0-9]{48}$",
    }
    
    pattern = provider_patterns.get(provider.lower())
    if pattern:
        return bool(re.match(pattern, api_key.strip()))
    return True  # Unknown provider, allow any

def get_output_path(base_dir: str, filename: str, format: str = "mp3") -> str:
    """Get unique output file path"""
    output_dir = Path(base_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = Path(filename).stem
    ext = f".{format}"
    counter = 0
    
    while True:
        if counter == 0:
            path = output_dir / f"{base_name}{ext}"
        else:
            path = output_dir / f"{base_name}_{counter}{ext}"
        
        if not path.exists():
            return str(path)
        counter += 1

def estimate_audio_duration(text: str, speed: float = 1.0) -> float:
    """Estimate audio duration in seconds"""
    words = len(text.split())
    words_per_minute = 150 * speed
    return (words / words_per_minute) * 60
