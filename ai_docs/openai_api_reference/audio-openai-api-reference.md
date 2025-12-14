# Audio - OpenAI API Reference

Learn how to turn audio into text or text into audio.

**Related Guide:** [Speech to Text](https://platform.openai.com/docs/guides/speech-to-text)

---

## Create Speech

```
POST https://api.openai.com/v1/audio/speech
```

Generates audio from the input text.

### Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input` | string | **Required** | The text to generate audio for. The maximum length is 4096 characters. |
| `model` | string | **Required** | One of the available TTS models: `tts-1`, `tts-1-hd` or `gpt-4o-mini-tts`. |
| `voice` | string | **Required** | The voice to use when generating the audio. Supported voices are `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, and `verse`. |
| `instructions` | string | Optional | Control the voice of your generated audio with additional instructions. Does not work with `tts-1` or `tts-1-hd`. |
| `response_format` | string | Optional | The format to audio in. Supported formats are `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`. |
| `speed` | number | Optional | The speed of the generated audio. Select a value from `0.25` to `4.0`. `1.0` is the default. |
| `stream_format` | string | Optional | The format to stream the audio in. Supported formats are `sse` and `audio`. `sse` is not supported for `tts-1` or `tts-1-hd`. |

### Returns

The audio file content or a stream of audio events.

### Examples

**cURL:**

```bash
curl https://api.openai.com/v1/audio/speech \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini-tts",
    "input": "The quick brown fox jumped over the lazy dog.",
    "voice": "alloy"
  }' \
  --output speech.mp3
```

**Python:**

```python
from pathlib import Path
import openai

speech_file_path = Path(__file__).parent / "speech.mp3"

with openai.audio.speech.with_streaming_response.create(
    model="gpt-4o-mini-tts",
    voice="alloy",
    input="The quick brown fox jumped over the lazy dog."
) as response:
    response.stream_to_file(speech_file_path)
```

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import path from "path";
import OpenAI from "openai";

const openai = new OpenAI();
const speechFile = path.resolve("./speech.mp3");

async function main() {
  const mp3 = await openai.audio.speech.create({
    model: "gpt-4o-mini-tts",
    voice: "alloy",
    input: "Today is a wonderful day to build something people love!",
  });
  console.log(speechFile);
  const buffer = Buffer.from(await mp3.arrayBuffer());
  await fs.promises.writeFile(speechFile, buffer);
}

main();
```

**C#:**

```csharp
using System;
using System.IO;
using OpenAI.Audio;

AudioClient client = new(
    model: "gpt-4o-mini-tts",
    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
);

BinaryData speech = client.GenerateSpeech(
    text: "The quick brown fox jumped over the lazy dog.",
    voice: GeneratedSpeechVoice.Alloy
);

using FileStream stream = File.OpenWrite("speech.mp3");
speech.ToStream().CopyTo(stream);
```

---

## Create Transcription

```
POST https://api.openai.com/v1/audio/transcriptions
```

Transcribes audio into the input language.

### Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | **Required** | The audio file object (not file name) to transcribe, in one of these formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, or webm. |
| `model` | string | **Required** | ID of the model to use. The options are `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `whisper-1` (powered by Whisper V2 model), and `gpt-4o-transcribe-diarize`. |
| `chunking_strategy` | "auto" or object | Optional | Controls how the audio is cut into chunks. When set to `"auto"`, the server first normalizes loudness and then uses voice activity detection (VAD) to choose boundaries. `server_vad` object can be provided to tweak VAD detection parameters manually. Required when using `gpt-4o-transcribe-diarize` for inputs longer than 30 seconds. |
| `include[]` | array | Optional | Additional information to include in the transcription response. `logprobs` will return the log probabilities of the tokens in the response. Only works with response_format set to `json` and with models `gpt-4o-transcribe` and `gpt-4o-mini-transcribe`. Not supported for `gpt-4o-transcribe-diarize`. |
| `known_speaker_names[]` | array | Optional | Optional list of speaker names that correspond to the audio samples provided in `known_speaker_references[]`. Each entry should be a short identifier (e.g., `customer` or `agent`). Up to 4 speakers are supported. |
| `known_speaker_references[]` | array | Optional | Optional list of audio samples (as data URLs) that contain known speaker references matching `known_speaker_names[]`. Each sample must be between 2 and 10 seconds. |
| `language` | string | Optional | The language of the input audio. Supplying the input language in ISO-639-1 (e.g., `en`) format will improve accuracy and latency. |
| `prompt` | string | Optional | An optional text to guide the model's style or continue a previous audio segment. The prompt should match the audio language. Not supported for `gpt-4o-transcribe-diarize`. |
| `response_format` | string | Optional | The format of the output: `json`, `text`, `srt`, `verbose_json`, `vtt`, or `diarized_json`. For `gpt-4o-transcribe` and `gpt-4o-mini-transcribe`, only `json` is supported. For `gpt-4o-transcribe-diarize`, supported formats are `json`, `text`, and `diarized_json`, with `diarized_json` required to receive speaker annotations. |
| `stream` | boolean | Optional | If set to true, the model response data will be streamed to the client as it is generated using server-sent events. **Note:** Streaming is not supported for the `whisper-1` model. |
| `temperature` | number | Optional | The sampling temperature, between 0 and 1. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. |
| `timestamp_granularities[]` | array | Optional | The timestamp granularities to populate for this transcription. `response_format` must be set to `verbose_json`. Options: `word` or `segment`. Not available for `gpt-4o-transcribe-diarize`. |

### Returns

The transcription object, a diarized transcription object, a verbose transcription object, or a stream of transcript events.

### Examples

**cURL:**

```bash
curl https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F file="@/path/to/file/audio.mp3" \
  -F model="gpt-4o-transcribe"
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("speech.mp3", "rb")

transcript = client.audio.transcriptions.create(
    model="gpt-4o-transcribe",
    file=audio_file
)
```

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();

async function main() {
  const transcription = await openai.audio.transcriptions.create({
    file: fs.createReadStream("audio.mp3"),
    model: "gpt-4o-transcribe",
  });
  console.log(transcription.text);
}

main();
```

**Example Response:**

```json
{
  "text": "Imagine the wildest idea that you've ever had, and you're curious about how it might scale to something that's a 100, a 1,000 times bigger. This is a place where you can get to do that.",
  "usage": {
    "type": "tokens",
    "input_tokens": 14,
    "input_token_details": {
      "text_tokens": 0,
      "audio_tokens": 14
    },
    "output_tokens": 45,
    "total_tokens": 59
  }
}
```

---

## Create Translation

```
POST https://api.openai.com/v1/audio/translations
```

Translates audio into English.

### Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | **Required** | The audio file object (not file name) translate, in one of these formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, or webm. |
| `model` | string or "whisper-1" | **Required** | ID of the model to use. Only `whisper-1` (powered by Whisper V2 model) is currently available. |
| `prompt` | string | Optional | An optional text to guide the model's style or continue a previous audio segment. The prompt should be in English. |
| `response_format` | string | Optional | The format of the output: `json`, `text`, `srt`, `verbose_json`, or `vtt`. |
| `temperature` | number | Optional | The sampling temperature, between 0 and 1. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. |

### Returns

The translated text.

### Examples

**cURL:**

```bash
curl https://api.openai.com/v1/audio/translations \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F file="@/path/to/file/german.m4a" \
  -F model="whisper-1"
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("speech.mp3", "rb")

transcript = client.audio.translations.create(
    model="whisper-1",
    file=audio_file
)
```

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();

async function main() {
  const translation = await openai.audio.translations.create({
    file: fs.createReadStream("speech.mp3"),
    model: "whisper-1",
  });
  console.log(translation.text);
}

main();
```

**Example Response:**

```json
{
  "text": "Hello, my name is Wolfgang and I come from Germany. Where are you heading today?"
}
```

---

## Response Objects

### The Transcription Object (JSON)

Represents a transcription response returned by model, based on the provided input.

| Property | Type | Description |
|----------|------|-------------|
| `logprobs` | array | The log probabilities of the tokens in the transcription. Only returned with `gpt-4o-transcribe` and `gpt-4o-mini-transcribe` if `logprobs` is added to the `include` array. |
| `text` | string | The transcribed text. |
| `usage` | object | Token usage statistics for the request. |

**Example:**

```json
{
  "text": "Imagine the wildest idea that you've ever had, and you're curious about how it might scale to something that's a 100, a 1,000 times bigger. This is a place where you can get to do that.",
  "usage": {
    "type": "tokens",
    "input_tokens": 14,
    "input_token_details": {
      "text_tokens": 10,
      "audio_tokens": 4
    },
    "output_tokens": 101,
    "total_tokens": 115
  }
}
```

---

### The Transcription Object (Diarized JSON)

Represents a diarized transcription response returned by the model, including the combined transcript and speaker-segment annotations.

| Property | Type | Description |
|----------|------|-------------|
| `duration` | number | Duration of the input audio in seconds. |
| `segments` | array | Segments of the transcript annotated with timestamps and speaker labels. |
| `task` | string | The type of task that was run. Always `transcribe`. |
| `text` | string | The concatenated transcript text for the entire audio input. |
| `usage` | object | Token or duration usage statistics for the request. |

**Example:**

```json
{
  "task": "transcribe",
  "duration": 42.7,
  "text": "Agent: Thanks for calling OpenAI support.\nCustomer: Hi, I need help with diarization.",
  "segments": [
    {
      "type": "transcript.text.segment",
      "id": "seg_001",
      "start": 0.0,
      "end": 5.2,
      "text": "Thanks for calling OpenAI support.",
      "speaker": "agent"
    },
    {
      "type": "transcript.text.segment",
      "id": "seg_002",
      "start": 5.2,
      "end": 12.8,
      "text": "Hi, I need help with diarization.",
      "speaker": "A"
    }
  ],
  "usage": {
    "type": "duration",
    "seconds": 43
  }
}
```

---

### The Transcription Object (Verbose JSON)

Represents a verbose json transcription response returned by model, based on the provided input.

| Property | Type | Description |
|----------|------|-------------|
| `duration` | number | The duration of the input audio. |
| `language` | string | The language of the input audio. |
| `segments` | array | Segments of the transcribed text and their corresponding details. |
| `text` | string | The transcribed text. |
| `usage` | object | Usage statistics for models billed by audio input duration. |
| `words` | array | Extracted words and their corresponding timestamps. |

**Example:**

```json
{
  "task": "transcribe",
  "language": "english",
  "duration": 8.470000267028809,
  "text": "The beach was a popular spot on a hot summer day. People were swimming in the ocean, building sandcastles, and playing beach volleyball.",
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 3.319999933242798,
      "text": " The beach was a popular spot on a hot summer day.",
      "tokens": [50364, 440, 7534, 390, 257, 3743, 4008, 322, 257, 2368, 4266, 786, 13, 50530],
      "temperature": 0.0,
      "avg_logprob": -0.2860786020755768,
      "compression_ratio": 1.2363636493682861,
      "no_speech_prob": 0.00985979475080967
    }
  ],
  "usage": {
    "type": "duration",
    "seconds": 9
  }
}
```

---

## Stream Events

### speech.audio.delta

Emitted for each chunk of audio data generated during speech synthesis.

| Property | Type | Description |
|----------|------|-------------|
| `audio` | string | A chunk of Base64-encoded audio data. |
| `type` | string | The type of the event. Always `speech.audio.delta`. |

**Example:**

```json
{
  "type": "speech.audio.delta",
  "audio": "base64-encoded-audio-data"
}
```

---

### speech.audio.done

Emitted when the speech synthesis is complete and all audio has been streamed.

| Property | Type | Description |
|----------|------|-------------|
| `type` | string | The type of the event. Always `speech.audio.done`. |
| `usage` | object | Token usage statistics for the request. |

**Example:**

```json
{
  "type": "speech.audio.done",
  "usage": {
    "input_tokens": 14,
    "output_tokens": 101,
    "total_tokens": 115
  }
}
```

---

### transcript.text.delta

Emitted when there is an additional text delta. This is the first event emitted when the transcription starts. Only emitted when you create a transcription with the `Stream` parameter set to `true`.

| Property | Type | Description |
|----------|------|-------------|
| `delta` | string | The text delta that was additionally transcribed. |
| `logprobs` | array | The log probabilities of the delta. Only included if you create a transcription with the `include[]` parameter set to `logprobs`. |
| `segment_id` | string | Identifier of the diarized segment that this delta belongs to. Only present when using `gpt-4o-transcribe-diarize`. |
| `type` | string | The type of the event. Always `transcript.text.delta`. |

**Example:**

```json
{
  "type": "transcript.text.delta",
  "delta": " wonderful"
}
```

---

### transcript.text.segment

Emitted when a diarized transcription returns a completed segment with speaker information. Only emitted when you create a transcription with `stream` set to `true` and `response_format` set to `diarized_json`.

| Property | Type | Description |
|----------|------|-------------|
| `end` | number | End timestamp of the segment in seconds. |
| `id` | string | Unique identifier for the segment. |
| `speaker` | string | Speaker label for this segment. |
| `start` | number | Start timestamp of the segment in seconds. |
| `text` | string | Transcript text for this segment. |
| `type` | string | The type of the event. Always `transcript.text.segment`. |

**Example:**

```json
{
  "type": "transcript.text.segment",
  "id": "seg_002",
  "start": 5.2,
  "end": 12.8,
  "text": "Hi, I need help with diarization.",
  "speaker": "A"
}
```

---

### transcript.text.done

Emitted when the transcription is complete. Contains the complete transcription text. Only emitted when you create a transcription with the `Stream` parameter set to `true`.

| Property | Type | Description |
|----------|------|-------------|
| `logprobs` | array | The log probabilities of the individual tokens in the transcription. Only included if you create a transcription with the `include[]` parameter set to `logprobs`. |
| `text` | string | The text that was transcribed. |
| `type` | string | The type of the event. Always `transcript.text.done`. |
| `usage` | object | Usage statistics for models billed by token usage. |

**Example:**

```json
{
  "type": "transcript.text.done",
  "text": "I see skies of blue and clouds of white, the bright blessed days, the dark sacred nights, and I think to myself, what a wonderful world.",
  "usage": {
    "type": "tokens",
    "input_tokens": 14,
    "input_token_details": {
      "text_tokens": 10,
      "audio_tokens": 4
    },
    "output_tokens": 31,
    "total_tokens": 45
  }
}
```

---

## Quick Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/speech` | POST | Generate speech from text |
| `/v1/audio/transcriptions` | POST | Transcribe audio to text |
| `/v1/audio/translations` | POST | Translate audio to English |

### Models

| Model | Use Case |
|-------|----------|
| `tts-1` | Standard text-to-speech |
| `tts-1-hd` | High-definition text-to-speech |
| `gpt-4o-mini-tts` | GPT-4o mini TTS with instructions support |
| `whisper-1` | Speech-to-text (Whisper V2) |
| `gpt-4o-transcribe` | High-quality transcription |
| `gpt-4o-mini-transcribe` | Lightweight transcription |
| `gpt-4o-transcribe-diarize` | Transcription with speaker diarization |

### Voices

`alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse`

### Audio Formats

**Input:** `flac`, `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `ogg`, `wav`, `webm`

**Output (TTS):** `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`

**Output (Transcription):** `json`, `text`, `srt`, `verbose_json`, `vtt`, `diarized_json`
