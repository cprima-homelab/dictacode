"""Audio resampler for converting between sample rates.

Converts audio from native device sample rates (e.g., 48kHz) to target rate
(typically 16kHz for Whisper STT).
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class Resampler:
    """Audio resampler for sample rate conversion.

    Converts audio from source sample rate to target sample rate using
    linear interpolation. Optimized for real-time streaming.

    Example:
        >>> resampler = Resampler(target_rate=16000)
        >>> audio_16k = resampler.process(audio_48k_bytes, source_rate=48000)
    """

    def __init__(self, target_rate: int = 16000, dtype: str = "int16"):
        """Initialize resampler.

        Args:
            target_rate: Target sample rate (default: 16000 for Whisper)
            dtype: Audio data type ("int16" or "float32")
        """
        self.target_rate = target_rate
        self.dtype = dtype
        self._last_source_rate: Optional[int] = None

        logger.info(f"Resampler initialized: target_rate={target_rate}Hz, dtype={dtype}")

    def process(self, audio_bytes: bytes, source_rate: int) -> bytes:
        """Resample audio from source rate to target rate.

        Args:
            audio_bytes: Input audio data as bytes
            source_rate: Source sample rate (e.g., 48000)

        Returns:
            Resampled audio as bytes at target_rate

        Raises:
            ValueError: If source_rate is invalid
        """
        if source_rate <= 0:
            raise ValueError(f"Invalid source_rate: {source_rate}")

        # Log rate change
        if self._last_source_rate != source_rate:
            logger.info(f"Resampling {source_rate}Hz → {self.target_rate}Hz")
            self._last_source_rate = source_rate

        # No resampling needed if rates match
        if source_rate == self.target_rate:
            return audio_bytes

        # Convert bytes to numpy array
        if self.dtype == "int16":
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
        elif self.dtype == "float32":
            samples = np.frombuffer(audio_bytes, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported dtype: {self.dtype}")

        # Resample using linear interpolation
        resampled = self._resample_linear(samples, source_rate, self.target_rate)

        # Convert back to bytes
        if self.dtype == "int16":
            # Ensure values are in int16 range
            resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
        elif self.dtype == "float32":
            resampled = resampled.astype(np.float32)

        return resampled.tobytes()

    def _resample_linear(
        self, samples: np.ndarray, source_rate: int, target_rate: int
    ) -> np.ndarray:
        """Resample using linear interpolation.

        Args:
            samples: Input audio samples
            source_rate: Source sample rate
            target_rate: Target sample rate

        Returns:
            Resampled audio samples
        """
        num_samples = len(samples)
        duration = num_samples / source_rate  # Duration in seconds
        num_output_samples = int(duration * target_rate)

        # Create interpolation indices
        # Map each output sample to its position in the input
        input_indices = np.linspace(0, num_samples - 1, num_output_samples)

        # Linear interpolation
        resampled = np.interp(input_indices, np.arange(num_samples), samples)

        return resampled

    def get_output_size(self, input_size: int, source_rate: int) -> int:
        """Calculate output buffer size after resampling.

        Args:
            input_size: Number of input samples
            source_rate: Source sample rate

        Returns:
            Number of output samples
        """
        if source_rate == self.target_rate:
            return input_size

        duration = input_size / source_rate
        return int(duration * self.target_rate)

    def __repr__(self) -> str:
        """String representation of resampler."""
        return f"Resampler(target_rate={self.target_rate}Hz, dtype={self.dtype})"


class ResamplerScipy(Resampler):
    """High-quality resampler using scipy.signal.resample.

    Uses FFT-based resampling for better quality than linear interpolation.
    Requires scipy to be installed.

    Note: This is slower than linear interpolation and may not be suitable
    for real-time streaming. Use Resampler (linear) for real-time use cases.
    """

    def __init__(self, target_rate: int = 16000, dtype: str = "int16"):
        """Initialize scipy-based resampler.

        Args:
            target_rate: Target sample rate
            dtype: Audio data type

        Raises:
            ImportError: If scipy is not installed
        """
        super().__init__(target_rate, dtype)

        try:
            from scipy import signal

            self._scipy_signal = signal
        except ImportError:
            raise ImportError(
                "scipy is required for ResamplerScipy. "
                "Install with: pip install scipy\n"
                "Or use Resampler (linear interpolation) instead."
            )

        logger.info(f"ResamplerScipy initialized (FFT-based, high quality)")

    def _resample_linear(
        self, samples: np.ndarray, source_rate: int, target_rate: int
    ) -> np.ndarray:
        """Resample using scipy's FFT-based resampling.

        Args:
            samples: Input audio samples
            source_rate: Source sample rate
            target_rate: Target sample rate

        Returns:
            Resampled audio samples
        """
        num_samples = len(samples)
        duration = num_samples / source_rate
        num_output_samples = int(duration * target_rate)

        # Use scipy's resample function (FFT-based)
        resampled = self._scipy_signal.resample(samples, num_output_samples)

        return resampled
