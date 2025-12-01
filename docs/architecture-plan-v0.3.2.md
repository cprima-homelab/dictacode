# dictacode Architecture Plan v0.2.14 - LLM Post-Processing & Command Detection

## Status

### Phase 1: LLM Adapter Interface
- [ ] Create `llm/` package
- [ ] Define `LlmAdapter` ABC
- [ ] Define `LlmRequest`, `LlmResponse` types
- [ ] Define `ProcessingProfile` for prompt templates
- [ ] Unit tests for adapter interface

### Phase 2: LLM Implementations
- [ ] Implement `OllamaAdapter` (local Llama)
- [ ] Implement `OpenAiAdapter` (OpenAI API)
- [ ] Implement `OpenRouterAdapter` (OpenRouter)
- [ ] Factory function `get_llm_adapter(name)`
- [ ] Unit tests with mock responses

### Phase 3: Processing Profiles
- [ ] Define profile schema (system prompt, user template)
- [ ] Implement profile loading from config
- [ ] Built-in profiles: grammar, punctuation, formal, casual
- [ ] Profile selection via CLI/config
- [ ] Unit tests for profile application

### Phase 4: Pipeline Integration
- [ ] Create `PostProcessor` class
- [ ] Integrate into `SttService` pipeline
- [ ] Optional bypass (passthrough mode)
- [ ] Async processing with timeout
- [ ] Error handling (fallback to raw text)

### Phase 5: Command Detection (Stub)
- [ ] Define `CommandDetector` interface
- [ ] Implement wake word detection stub
- [ ] Define `Command` types (wake, action, cancel)
- [ ] Prepare hooks for future voice command system
- [ ] Document extension points

### Phase 6: CLI & Config Integration
- [ ] Add `--llm` flag for LLM selection
- [ ] Add `--profile` flag for processing profile
- [ ] Add `--no-llm` to bypass processing
- [ ] Config file support
- [ ] API endpoint for profile switching

**v0.2.14 NOT STARTED**

---

## Prerequisites

v0.2.14 builds on top of:
- ✅ v0.2.6: TranscriptionAdapter pattern
- ✅ v0.2.7: Streaming transcription

---

## Problem Statement

### Current Transcription Quality

Raw transcription output has issues:
- Missing or incorrect punctuation
- No capitalization consistency
- Filler words ("um", "uh", "like")
- No formatting (numbers, dates, code)
- Spoken vs written style mismatch

### LLM Post-Processing Goals

1. **Grammar correction** - Fix errors, improve structure
2. **Punctuation** - Add proper punctuation and capitalization
3. **Style adaptation** - Formal, casual, technical profiles
4. **Format conversion** - Numbers, dates, code blocks
5. **Filler removal** - Clean up speech artifacts

### Command Detection Goals

Prepare for future voice command system:
- Wake word detection ("Hey Dictacode", custom)
- Action commands ("stop typing", "new paragraph")
- Cancel/abort commands
- Mode switching ("code mode", "prose mode")

---

## Design

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         STT Pipeline                                 │
│                                                                      │
│  Audio → Transcription → [Command Detection] → [LLM Processing] → HID│
│            ↓                    ↓                    ↓               │
│      TranscriptionAdapter  CommandDetector    PostProcessor         │
│      (Whisper/Vosk)        (wake words)       (LLM profiles)        │
│                                                                      │
│  Optional stages in brackets - can be bypassed                       │
└─────────────────────────────────────────────────────────────────────┘
```

### LLM Adapter Interface

```python
# llm/adapter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class LlmProvider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENROUTER = "openrouter"

@dataclass
class LlmMessage:
    """A message in the conversation."""
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class LlmRequest:
    """Request to LLM."""
    messages: List[LlmMessage]
    model: str
    temperature: float = 0.3
    max_tokens: int = 500
    timeout_seconds: float = 10.0

@dataclass
class LlmResponse:
    """Response from LLM."""
    text: str
    model: str
    usage: Optional[Dict[str, int]] = None  # tokens used
    latency_ms: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.text) > 0

@dataclass
class LlmConfig:
    """Configuration for LLM adapter."""
    provider: LlmProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: float = 10.0
    temperature: float = 0.3
    max_tokens: int = 500

class LlmAdapter(ABC):
    """Abstract LLM adapter for text post-processing."""

    @abstractmethod
    def get_provider(self) -> LlmProvider:
        """Return provider type."""
        pass

    @abstractmethod
    def get_model(self) -> str:
        """Return model name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if LLM service is reachable."""
        pass

    @abstractmethod
    async def complete(self, request: LlmRequest) -> LlmResponse:
        """
        Send completion request to LLM.

        Args:
            request: LLM request with messages

        Returns:
            LlmResponse with generated text or error
        """
        pass

    def get_config(self) -> LlmConfig:
        """Return current configuration."""
        return self._config
```

### Ollama Adapter (Local Llama)

```python
# llm/ollama.py

import aiohttp
from typing import Optional

class OllamaAdapter(LlmAdapter):
    """Local Llama via Ollama."""

    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.2:3b"  # Good balance of speed/quality

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_URL,
        timeout_seconds: float = 10.0,
        temperature: float = 0.3,
    ):
        self._config = LlmConfig(
            provider=LlmProvider.OLLAMA,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def get_provider(self) -> LlmProvider:
        return LlmProvider.OLLAMA

    def get_model(self) -> str:
        return self._config.model

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        import requests
        try:
            response = requests.get(
                f"{self._config.base_url}/api/tags",
                timeout=2,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Send request to Ollama."""
        import time
        start = time.monotonic()

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": request.model or self._config.model,
                    "messages": [
                        {"role": m.role, "content": m.content}
                        for m in request.messages
                    ],
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens,
                    },
                }

                async with session.post(
                    f"{self._config.base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=request.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        return LlmResponse(
                            text="",
                            model=self._config.model,
                            error=f"Ollama error: {response.status}",
                        )

                    data = await response.json()
                    latency_ms = int((time.monotonic() - start) * 1000)

                    return LlmResponse(
                        text=data["message"]["content"],
                        model=data.get("model", self._config.model),
                        latency_ms=latency_ms,
                        usage={
                            "prompt_tokens": data.get("prompt_eval_count", 0),
                            "completion_tokens": data.get("eval_count", 0),
                        },
                    )

        except asyncio.TimeoutError:
            return LlmResponse(
                text="",
                model=self._config.model,
                error="Timeout",
                latency_ms=int(request.timeout_seconds * 1000),
            )
        except Exception as e:
            return LlmResponse(
                text="",
                model=self._config.model,
                error=str(e),
            )
```

### OpenAI Adapter

```python
# llm/openai.py

import os
import aiohttp
from typing import Optional

class OpenAiAdapter(LlmAdapter):
    """OpenAI API adapter."""

    DEFAULT_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"  # Fast and cost-effective

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_URL,
        timeout_seconds: float = 10.0,
        temperature: float = 0.3,
    ):
        self._config = LlmConfig(
            provider=LlmProvider.OPENAI,
            model=model,
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def get_provider(self) -> LlmProvider:
        return LlmProvider.OPENAI

    def get_model(self) -> str:
        return self._config.model

    def is_available(self) -> bool:
        """Check if API key is configured."""
        return self._config.api_key is not None

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Send request to OpenAI."""
        import time
        start = time.monotonic()

        if not self._config.api_key:
            return LlmResponse(
                text="",
                model=self._config.model,
                error="OPENAI_API_KEY not set",
            )

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": request.model or self._config.model,
                    "messages": [
                        {"role": m.role, "content": m.content}
                        for m in request.messages
                    ],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                }

                async with session.post(
                    f"{self._config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=request.timeout_seconds),
                ) as response:
                    data = await response.json()
                    latency_ms = int((time.monotonic() - start) * 1000)

                    if response.status != 200:
                        return LlmResponse(
                            text="",
                            model=self._config.model,
                            error=data.get("error", {}).get("message", "Unknown error"),
                            latency_ms=latency_ms,
                        )

                    return LlmResponse(
                        text=data["choices"][0]["message"]["content"],
                        model=data["model"],
                        latency_ms=latency_ms,
                        usage=data.get("usage"),
                    )

        except asyncio.TimeoutError:
            return LlmResponse(
                text="",
                model=self._config.model,
                error="Timeout",
            )
        except Exception as e:
            return LlmResponse(
                text="",
                model=self._config.model,
                error=str(e),
            )
```

### OpenRouter Adapter

```python
# llm/openrouter.py

import os
import aiohttp

class OpenRouterAdapter(LlmAdapter):
    """OpenRouter API adapter - access to multiple providers."""

    DEFAULT_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "meta-llama/llama-3.2-3b-instruct"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        timeout_seconds: float = 10.0,
        temperature: float = 0.3,
    ):
        self._config = LlmConfig(
            provider=LlmProvider.OPENROUTER,
            model=model,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            base_url=self.DEFAULT_URL,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def get_provider(self) -> LlmProvider:
        return LlmProvider.OPENROUTER

    def get_model(self) -> str:
        return self._config.model

    def is_available(self) -> bool:
        return self._config.api_key is not None

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Send request to OpenRouter."""
        # Similar to OpenAI, with OpenRouter-specific headers
        import time
        start = time.monotonic()

        if not self._config.api_key:
            return LlmResponse(
                text="",
                model=self._config.model,
                error="OPENROUTER_API_KEY not set",
            )

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/cprima-homelab/dictacode",
                    "X-Title": "Dictacode STT",
                }
                payload = {
                    "model": request.model or self._config.model,
                    "messages": [
                        {"role": m.role, "content": m.content}
                        for m in request.messages
                    ],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                }

                async with session.post(
                    f"{self._config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=request.timeout_seconds),
                ) as response:
                    data = await response.json()
                    latency_ms = int((time.monotonic() - start) * 1000)

                    if response.status != 200:
                        return LlmResponse(
                            text="",
                            model=self._config.model,
                            error=data.get("error", {}).get("message", "Unknown error"),
                            latency_ms=latency_ms,
                        )

                    return LlmResponse(
                        text=data["choices"][0]["message"]["content"],
                        model=data["model"],
                        latency_ms=latency_ms,
                        usage=data.get("usage"),
                    )

        except Exception as e:
            return LlmResponse(
                text="",
                model=self._config.model,
                error=str(e),
            )
```

### LLM Factory

```python
# llm/__init__.py

def get_llm_adapter(
    provider: str,
    **kwargs,
) -> LlmAdapter:
    """
    Factory function to get LLM adapter by provider name.

    Args:
        provider: 'ollama', 'openai', 'openrouter'
        **kwargs: Provider-specific configuration

    Returns:
        LlmAdapter instance
    """
    adapters = {
        "ollama": OllamaAdapter,
        "openai": OpenAiAdapter,
        "openrouter": OpenRouterAdapter,
    }

    if provider not in adapters:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(adapters.keys())}")

    return adapters[provider](**kwargs)
```

---

## Processing Profiles

### Profile Schema

```python
# llm/profile.py

from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path
import yaml

@dataclass
class ProcessingProfile:
    """LLM processing profile with prompts."""
    name: str
    description: str
    system_prompt: str
    user_template: str  # {text} placeholder for transcription
    temperature: float = 0.3
    max_tokens: int = 500
    enabled: bool = True

    def format_user_message(self, text: str) -> str:
        """Format user message with transcription text."""
        return self.user_template.format(text=text)


# Built-in profiles
BUILTIN_PROFILES: Dict[str, ProcessingProfile] = {
    "grammar": ProcessingProfile(
        name="grammar",
        description="Fix grammar and punctuation",
        system_prompt="""You are a text correction assistant. Your job is to:
1. Fix grammar and spelling errors
2. Add proper punctuation and capitalization
3. Remove filler words (um, uh, like, you know)
4. Keep the original meaning and tone

Output ONLY the corrected text, nothing else.""",
        user_template="{text}",
        temperature=0.2,
    ),

    "punctuation": ProcessingProfile(
        name="punctuation",
        description="Add punctuation only (minimal changes)",
        system_prompt="""You are a punctuation assistant. Your job is to:
1. Add periods, commas, and question marks where needed
2. Capitalize sentence beginnings and proper nouns
3. Do NOT change any words or phrasing

Output ONLY the punctuated text, nothing else.""",
        user_template="{text}",
        temperature=0.1,
    ),

    "formal": ProcessingProfile(
        name="formal",
        description="Convert to formal written style",
        system_prompt="""You are a writing assistant. Convert the spoken text to formal written style:
1. Fix grammar and punctuation
2. Use formal vocabulary and tone
3. Expand contractions (don't → do not)
4. Structure into proper sentences
5. Remove filler words and speech artifacts

Output ONLY the formal text, nothing else.""",
        user_template="{text}",
        temperature=0.3,
    ),

    "casual": ProcessingProfile(
        name="casual",
        description="Clean up while keeping casual tone",
        system_prompt="""You are a text cleanup assistant. Clean up the text while keeping it casual:
1. Fix obvious errors
2. Add basic punctuation
3. Keep contractions and casual expressions
4. Remove excessive filler words
5. Preserve the speaker's voice

Output ONLY the cleaned text, nothing else.""",
        user_template="{text}",
        temperature=0.3,
    ),

    "code": ProcessingProfile(
        name="code",
        description="Format for code dictation",
        system_prompt="""You are a code dictation assistant. Format the text for code:
1. Convert spoken code to actual code syntax
2. "open paren" → (, "close bracket" → ]
3. "new line" → actual newline
4. "indent" → proper indentation
5. Recognize common programming keywords
6. Format numbers and operators correctly

Output ONLY the formatted code, nothing else.""",
        user_template="{text}",
        temperature=0.2,
    ),

    "passthrough": ProcessingProfile(
        name="passthrough",
        description="No processing (bypass LLM)",
        system_prompt="",
        user_template="{text}",
        enabled=False,  # Special case - skips LLM entirely
    ),
}


class ProfileManager:
    """Manage processing profiles."""

    def __init__(self, config_dir: Path = Path("/etc/dictacode/profiles")):
        self.config_dir = config_dir
        self._profiles: Dict[str, ProcessingProfile] = BUILTIN_PROFILES.copy()

    def load_custom_profiles(self) -> None:
        """Load custom profiles from config directory."""
        if not self.config_dir.exists():
            return

        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                profile = ProcessingProfile(**data)
                self._profiles[profile.name] = profile
            except Exception as e:
                logger.warning(f"Failed to load profile {yaml_file}: {e}")

    def get_profile(self, name: str) -> ProcessingProfile:
        """Get profile by name."""
        if name not in self._profiles:
            raise ValueError(f"Unknown profile: {name}. Available: {list(self._profiles.keys())}")
        return self._profiles[name]

    def list_profiles(self) -> List[str]:
        """List available profile names."""
        return list(self._profiles.keys())
```

### Custom Profile Example

```yaml
# /etc/dictacode/profiles/medical.yaml
name: medical
description: Format for medical documentation
system_prompt: |
  You are a medical transcription assistant. Format the text for medical documentation:
  1. Use proper medical terminology
  2. Format drug names and dosages correctly
  3. Structure as clinical notes
  4. Fix grammar while preserving medical accuracy

  Output ONLY the formatted medical text, nothing else.
user_template: "{text}"
temperature: 0.2
max_tokens: 1000
```

---

## Post-Processor

```python
# llm/processor.py

import asyncio
from typing import Optional
from dataclasses import dataclass

@dataclass
class ProcessingResult:
    """Result of LLM post-processing."""
    original_text: str
    processed_text: str
    profile_used: str
    llm_provider: str
    llm_model: str
    latency_ms: int
    success: bool
    error: Optional[str] = None

class PostProcessor:
    """LLM post-processor for transcription text."""

    def __init__(
        self,
        llm: Optional[LlmAdapter] = None,
        profile: Optional[ProcessingProfile] = None,
        enabled: bool = True,
        fallback_on_error: bool = True,  # Return original text on error
    ):
        self.llm = llm
        self.profile = profile or BUILTIN_PROFILES["grammar"]
        self.enabled = enabled and llm is not None
        self.fallback_on_error = fallback_on_error

    def set_profile(self, profile: ProcessingProfile) -> None:
        """Change processing profile."""
        self.profile = profile
        logger.info(f"Switched to profile: {profile.name}")

    async def process(self, text: str) -> ProcessingResult:
        """
        Process transcription text through LLM.

        Args:
            text: Raw transcription text

        Returns:
            ProcessingResult with processed text
        """
        # Skip if disabled or passthrough profile
        if not self.enabled or not self.profile.enabled:
            return ProcessingResult(
                original_text=text,
                processed_text=text,
                profile_used="passthrough",
                llm_provider="none",
                llm_model="none",
                latency_ms=0,
                success=True,
            )

        # Skip empty or very short text
        if len(text.strip()) < 3:
            return ProcessingResult(
                original_text=text,
                processed_text=text,
                profile_used=self.profile.name,
                llm_provider=self.llm.get_provider().value,
                llm_model=self.llm.get_model(),
                latency_ms=0,
                success=True,
            )

        # Build request
        request = LlmRequest(
            messages=[
                LlmMessage(role="system", content=self.profile.system_prompt),
                LlmMessage(role="user", content=self.profile.format_user_message(text)),
            ],
            model=self.llm.get_model(),
            temperature=self.profile.temperature,
            max_tokens=self.profile.max_tokens,
        )

        # Call LLM
        response = await self.llm.complete(request)

        if response.success:
            return ProcessingResult(
                original_text=text,
                processed_text=response.text.strip(),
                profile_used=self.profile.name,
                llm_provider=self.llm.get_provider().value,
                llm_model=response.model,
                latency_ms=response.latency_ms,
                success=True,
            )
        else:
            logger.warning(f"LLM processing failed: {response.error}")
            return ProcessingResult(
                original_text=text,
                processed_text=text if self.fallback_on_error else "",
                profile_used=self.profile.name,
                llm_provider=self.llm.get_provider().value,
                llm_model=self.llm.get_model(),
                latency_ms=response.latency_ms,
                success=False,
                error=response.error,
            )
```

---

## Command Detection (Stub)

```python
# commands/detector.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum

class CommandType(Enum):
    NONE = "none"           # Not a command, pass through
    WAKE = "wake"           # Wake word detected
    ACTION = "action"       # Action command
    CANCEL = "cancel"       # Cancel/abort command
    MODE = "mode"           # Mode switch command

@dataclass
class DetectedCommand:
    """A detected voice command."""
    type: CommandType
    trigger: str            # The phrase that triggered detection
    argument: Optional[str] # Optional argument (e.g., mode name)
    confidence: float       # 0.0 - 1.0
    remaining_text: str     # Text after command removed

@dataclass
class CommandPattern:
    """Pattern for command detection."""
    type: CommandType
    patterns: List[str]     # Phrases to match
    has_argument: bool = False

# Built-in command patterns
DEFAULT_COMMANDS = [
    CommandPattern(
        type=CommandType.WAKE,
        patterns=["hey dictacode", "dictacode", "ok dictacode"],
    ),
    CommandPattern(
        type=CommandType.ACTION,
        patterns=["new paragraph", "new line", "stop typing", "delete that"],
    ),
    CommandPattern(
        type=CommandType.CANCEL,
        patterns=["cancel", "abort", "never mind", "scratch that"],
    ),
    CommandPattern(
        type=CommandType.MODE,
        patterns=["code mode", "prose mode", "formal mode", "casual mode"],
        has_argument=True,
    ),
]

class CommandDetector(ABC):
    """Abstract command detector interface."""

    @abstractmethod
    def detect(self, text: str) -> DetectedCommand:
        """
        Detect command in transcription text.

        Args:
            text: Transcription text to analyze

        Returns:
            DetectedCommand with type and remaining text
        """
        pass

    @abstractmethod
    def add_pattern(self, pattern: CommandPattern) -> None:
        """Add custom command pattern."""
        pass


class SimpleCommandDetector(CommandDetector):
    """Simple prefix-based command detection."""

    def __init__(self, patterns: Optional[List[CommandPattern]] = None):
        self._patterns = patterns or DEFAULT_COMMANDS.copy()

    def detect(self, text: str) -> DetectedCommand:
        """Detect command by prefix matching."""
        text_lower = text.lower().strip()

        for pattern in self._patterns:
            for phrase in pattern.patterns:
                if text_lower.startswith(phrase):
                    # Extract remaining text
                    remaining = text[len(phrase):].strip()

                    # Extract argument for mode commands
                    argument = None
                    if pattern.has_argument:
                        # Mode name is part of the pattern
                        parts = phrase.split()
                        if len(parts) >= 2:
                            argument = parts[0]  # e.g., "code" from "code mode"

                    return DetectedCommand(
                        type=pattern.type,
                        trigger=phrase,
                        argument=argument,
                        confidence=1.0,  # Exact match
                        remaining_text=remaining,
                    )

        # No command detected
        return DetectedCommand(
            type=CommandType.NONE,
            trigger="",
            argument=None,
            confidence=0.0,
            remaining_text=text,
        )

    def add_pattern(self, pattern: CommandPattern) -> None:
        """Add custom command pattern."""
        self._patterns.append(pattern)


class CommandHandler:
    """Handle detected commands (stub for future implementation)."""

    def __init__(self, service: "SttService"):
        self.service = service

    async def handle(self, command: DetectedCommand) -> bool:
        """
        Handle detected command.

        Args:
            command: Detected command

        Returns:
            True if command was handled, False to continue normal processing
        """
        if command.type == CommandType.NONE:
            return False

        logger.info(f"Command detected: {command.type.value} - {command.trigger}")

        if command.type == CommandType.WAKE:
            # Wake word - activate listening mode
            # TODO: Implement wake word behavior
            logger.debug("Wake word detected - stub")
            return True

        elif command.type == CommandType.ACTION:
            # Action command
            if command.trigger == "new paragraph":
                # TODO: Send paragraph break to HID
                pass
            elif command.trigger == "new line":
                # TODO: Send newline to HID
                pass
            elif command.trigger == "stop typing":
                # TODO: Pause transcription
                pass
            return True

        elif command.type == CommandType.CANCEL:
            # Cancel last action
            # TODO: Implement undo/cancel
            return True

        elif command.type == CommandType.MODE:
            # Mode switch
            if command.argument:
                profile_name = command.argument
                # TODO: Switch processing profile
                logger.info(f"Mode switch requested: {profile_name}")
            return True

        return False
```

---

## Service Integration

```python
# service.py updates

class SttService:
    def __init__(
        self,
        # ... existing params ...
        llm: Optional[LlmAdapter] = None,
        llm_profile: str = "grammar",
        enable_commands: bool = False,
    ):
        # ... existing init ...

        # LLM post-processing
        self.profile_manager = ProfileManager()
        self.profile_manager.load_custom_profiles()

        profile = self.profile_manager.get_profile(llm_profile) if llm_profile else None
        self.post_processor = PostProcessor(
            llm=llm,
            profile=profile,
            enabled=llm is not None,
        )

        # Command detection
        self.command_detector = SimpleCommandDetector() if enable_commands else None
        self.command_handler = CommandHandler(self) if enable_commands else None

    async def _process_transcription(self, text: str) -> str:
        """Process transcription through pipeline."""

        # Step 1: Command detection (if enabled)
        if self.command_detector:
            command = self.command_detector.detect(text)
            if command.type != CommandType.NONE:
                handled = await self.command_handler.handle(command)
                if handled:
                    # Command consumed the text
                    if not command.remaining_text:
                        return ""
                    text = command.remaining_text

        # Step 2: LLM post-processing (if enabled)
        if self.post_processor.enabled:
            result = await self.post_processor.process(text)
            if result.success:
                text = result.processed_text
                logger.debug(
                    f"LLM processed ({result.profile_used}): "
                    f"{result.latency_ms}ms, {result.llm_model}"
                )
            else:
                logger.warning(f"LLM processing failed: {result.error}")
                # Fallback to original text is handled in PostProcessor

        return text

    def _on_final_result(self, result: FinalResult) -> None:
        """Handle final transcription result."""
        if not result.text:
            return

        # Process through pipeline
        processed_text = asyncio.run(self._process_transcription(result.text))

        if processed_text:
            logger.info(f"Sending: {processed_text[:50]}...")
            self.send_text(processed_text)
```

---

## Configuration

### CLI Flags

```bash
# Enable LLM with Ollama (local)
dictacode-stt --llm ollama --llm-model llama3.2:3b

# Enable LLM with OpenAI
dictacode-stt --llm openai --llm-model gpt-4o-mini

# Enable LLM with OpenRouter
dictacode-stt --llm openrouter --llm-model meta-llama/llama-3.2-3b-instruct

# Select processing profile
dictacode-stt --llm ollama --profile formal
dictacode-stt --llm ollama --profile code
dictacode-stt --llm ollama --profile punctuation

# Disable LLM (passthrough)
dictacode-stt --no-llm

# Enable command detection
dictacode-stt --llm ollama --enable-commands

# List available profiles
dictacode-stt-profile list
```

### Config File

```ini
# /etc/dictacode/stt.conf

[llm]
enabled = true
provider = ollama           # ollama, openai, openrouter
model = llama3.2:3b
# api_key =                 # For OpenAI/OpenRouter (or use env var)
# base_url =                # Custom endpoint

[processing]
profile = grammar           # grammar, punctuation, formal, casual, code
fallback_on_error = true    # Return original text if LLM fails
timeout_seconds = 10

[commands]
enabled = false             # Command detection (experimental)
# custom_wake_word = hey assistant
```

### Environment Variables

```bash
# API Keys
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."

# Ollama URL (if not localhost)
export OLLAMA_HOST="http://192.168.1.100:11434"
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── llm/                          # NEW: LLM adapters
│   ├── __init__.py               # Factory function
│   ├── adapter.py                # LlmAdapter ABC
│   ├── ollama.py                 # OllamaAdapter
│   ├── openai.py                 # OpenAiAdapter
│   ├── openrouter.py             # OpenRouterAdapter
│   ├── profile.py                # ProcessingProfile, ProfileManager
│   └── processor.py              # PostProcessor
├── commands/                     # NEW: Command detection (stub)
│   ├── __init__.py
│   ├── detector.py               # CommandDetector, patterns
│   └── handler.py                # CommandHandler (stub)
├── service.py                    # MODIFIED: Pipeline integration
├── cli.py                        # MODIFIED: LLM flags
└── ...

/etc/dictacode/
├── stt.conf                      # LLM configuration
└── profiles/                     # Custom profiles
    └── *.yaml
```

---

## Files to Create/Modify

1. `apps/stt/src/dictacode_stt/llm/__init__.py` - NEW: Package, factory
2. `apps/stt/src/dictacode_stt/llm/adapter.py` - NEW: LlmAdapter ABC
3. `apps/stt/src/dictacode_stt/llm/ollama.py` - NEW: Ollama implementation
4. `apps/stt/src/dictacode_stt/llm/openai.py` - NEW: OpenAI implementation
5. `apps/stt/src/dictacode_stt/llm/openrouter.py` - NEW: OpenRouter implementation
6. `apps/stt/src/dictacode_stt/llm/profile.py` - NEW: Processing profiles
7. `apps/stt/src/dictacode_stt/llm/processor.py` - NEW: PostProcessor
8. `apps/stt/src/dictacode_stt/commands/__init__.py` - NEW: Package
9. `apps/stt/src/dictacode_stt/commands/detector.py` - NEW: Command detection
10. `apps/stt/src/dictacode_stt/commands/handler.py` - NEW: Command handler stub
11. `apps/stt/src/dictacode_stt/service.py` - Pipeline integration
12. `apps/stt/src/dictacode_stt/cli.py` - Add LLM flags
13. `apps/stt/pyproject.toml` - Add aiohttp dependency

---

## Success Criteria

v0.2.14 is complete when:

1. ✅ `LlmAdapter` ABC defined with async complete()
2. ✅ `OllamaAdapter` works with local Ollama
3. ✅ `OpenAiAdapter` works with OpenAI API
4. ✅ `OpenRouterAdapter` works with OpenRouter
5. ✅ Factory function `get_llm_adapter(name)` works
6. ✅ Built-in profiles: grammar, punctuation, formal, casual, code
7. ✅ Custom profiles loadable from config directory
8. ✅ `PostProcessor` integrates into pipeline
9. ✅ Graceful fallback on LLM error
10. ✅ `--llm` and `--profile` CLI flags work
11. ✅ Config file support for LLM settings
12. ✅ `CommandDetector` stub with basic patterns
13. ✅ `CommandHandler` stub prepared for extension
14. ✅ Unit tests for adapters and profiles
15. ✅ Integration tests for pipeline

---

## Out of Scope (v0.2.14)

- Voice activity detection for command isolation
- Continuous conversation context
- Multi-turn LLM interactions
- Custom fine-tuned models
- Streaming LLM responses
- Full command system implementation (only stub)
- Wake word audio detection (only text-based)
- Cost tracking/budgeting for API calls
