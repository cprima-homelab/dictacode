"""Transcription adapters for STT engines (v0.2.6)."""

from .adapter import TranscriptionAdapter, TranscriptionResult, AudioRequirements
from .whisper import WhisperAdapter

# Export main types
__all__ = [
    "TranscriptionAdapter",
    "TranscriptionResult",
    "AudioRequirements",
    "WhisperAdapter",
    "get_transcriber",
]


def get_transcriber(name: str, **kwargs) -> TranscriptionAdapter:
    """Factory function to get transcription adapter by name.

    Args:
        name: Engine name ('whisper', 'vosk', 'google', 'azure', 'deepgram')
        **kwargs: Engine-specific configuration

    Returns:
        TranscriptionAdapter instance

    Raises:
        ValueError: If engine name is unknown

    Examples:
        # Get Whisper adapter (default paths)
        transcriber = get_transcriber("whisper")

        # Get Whisper with custom paths
        transcriber = get_transcriber(
            "whisper",
            binary_path=Path("/opt/whisper/whisper-cli"),
            model_path=Path("/opt/whisper/models/ggml-tiny.bin"),
        )

        # Get Vosk adapter (when implemented)
        transcriber = get_transcriber("vosk", model_path=Path("~/.vosk/model"))
    """
    adapters = {
        "whisper": WhisperAdapter,
        # Future adapters:
        # "vosk": VoskAdapter,
        # "google": lambda **kw: OnlineAdapter(provider="google", **kw),
        # "azure": lambda **kw: OnlineAdapter(provider="azure", **kw),
        # "deepgram": lambda **kw: OnlineAdapter(provider="deepgram", **kw),
    }

    if name not in adapters:
        raise ValueError(
            f"Unknown transcriber: {name}. Available: {list(adapters.keys())}"
        )

    return adapters[name](**kwargs)
