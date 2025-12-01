"""Transcription adapters for STT engines (v0.2.6+).

v0.2.6: Batch transcription with adapter pattern
v0.2.7: Streaming transcription support
"""

from .adapter import TranscriptionAdapter, TranscriptionResult, AudioRequirements
from .whisper import WhisperAdapter
from .vosk import VoskAdapter
from .streaming import (
    StreamingTranscriptionAdapter,
    PartialResult,
    FinalResult,
    PartialCallback,
    FinalCallback,
    ErrorCallback,
)

# Export main types
__all__ = [
    # Base adapter (v0.2.6)
    "TranscriptionAdapter",
    "TranscriptionResult",
    "AudioRequirements",
    "WhisperAdapter",
    "VoskAdapter",
    "get_transcriber",
    # Streaming support (v0.2.7)
    "StreamingTranscriptionAdapter",
    "PartialResult",
    "FinalResult",
    "PartialCallback",
    "FinalCallback",
    "ErrorCallback",
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
        "vosk": VoskAdapter,
        # Future adapters:
        # "google": lambda **kw: OnlineAdapter(provider="google", **kw),
        # "azure": lambda **kw: OnlineAdapter(provider="azure", **kw),
        # "deepgram": lambda **kw: OnlineAdapter(provider="deepgram", **kw),
    }

    if name not in adapters:
        raise ValueError(
            f"Unknown transcriber: {name}. Available: {list(adapters.keys())}"
        )

    return adapters[name](**kwargs)
