# Speech to Text - OpenAI API

Learn how to turn audio into text with the OpenAI API.

---

## Overview

The Audio API provides two speech-to-text endpoints:

| Endpoint | Description |
|----------|-------------|
| `transcriptions` | Transcribe audio into the input language |
| `translations` | Translate and transcribe audio into English |

### Available Models

Historically, both endpoints have been backed by our open source Whisper model (`whisper-1`). The `transcriptions` endpoint now also supports higher quality model snapshots:

| Model | Description |
|-------|-------------|
| `whisper-1` | Open source Whisper V2 model |
| `gpt-4o-transcribe` | Higher quality transcription |
| `gpt-4o-mini-transcribe` | Lightweight transcription model |
| `gpt-4o-transcribe-diarize` | Transcription with speaker diarization |

### Supported Input Formats

File uploads are currently limited to **25 MB**, and the following input file types are supported:

`mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, and `webm`

---

## Quickstart

### Transcriptions

The transcriptions API takes as input the audio file you want to transcribe and the desired output file format for the transcription of the audio.

#### Output Format Support by Model

| Model | Supported Formats |
|-------|-------------------|
| `whisper-1` | `json`, `text`, `srt`, `verbose_json`, `vtt` |
| `gpt-4o-transcribe` / `gpt-4o-mini-transcribe` | `json`, `text` |
| `gpt-4o-transcribe-diarize` | `json`, `text`, `diarized_json` |

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();

const transcription = await openai.audio.transcriptions.create({
  file: fs.createReadStream("/path/to/file/audio.mp3"),
  model: "gpt-4o-transcribe",
});

console.log(transcription.text);
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/audio.mp3", "rb")

transcription = client.audio.transcriptions.create(
    model="gpt-4o-transcribe",
    file=audio_file
)

print(transcription.text)
```

**cURL:**

```bash
curl --request POST \
  --url https://api.openai.com/v1/audio/transcriptions \
  --header "Authorization: Bearer $OPENAI_API_KEY" \
  --header 'Content-Type: multipart/form-data' \
  --form file=@/path/to/file/audio.mp3 \
  --form model=gpt-4o-transcribe
```

By default, the response type will be JSON with the raw text included.

#### Setting Response Format

To set the `response_format` as `text`:

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/speech.mp3", "rb")

transcription = client.audio.transcriptions.create(
    model="gpt-4o-transcribe",
    file=audio_file,
    response_format="text"
)

print(transcription.text)
```

---

## Speaker Diarization

`gpt-4o-transcribe-diarize` produces speaker-aware transcripts. Request the `diarized_json` response format to receive an array of segments with `speaker`, `start`, and `end` metadata.

Set `chunking_strategy` (either `"auto"` or a Voice Activity Detection configuration) so that the service can split the audio into segments; **this is required when the input is longer than 30 seconds**.

You can optionally supply up to **four short audio references** with `known_speaker_names[]` and `known_speaker_references[]` to map segments onto known speakers. Provide reference clips between 2–10 seconds in any supported input format; encode them as data URLs when using multipart form data.

**JavaScript (Node.js) - Diarization:**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();
const agentRef = fs.readFileSync("agent.wav").toString("base64");

const transcript = await openai.audio.transcriptions.create({
  file: fs.createReadStream("meeting.wav"),
  model: "gpt-4o-transcribe-diarize",
  response_format: "diarized_json",
  chunking_strategy: "auto",
  extra_body: {
    known_speaker_names: ["agent"],
    known_speaker_references: ["data:audio/wav;base64," + agentRef],
  },
});

for (const segment of transcript.segments) {
  console.log(`${segment.speaker}: ${segment.text}`, segment.start, segment.end);
}
```

**Python - Diarization:**

```python
import base64
from openai import OpenAI

client = OpenAI()

def to_data_url(path: str) -> str:
    with open(path, "rb") as fh:
        return "data:audio/wav;base64," + base64.b64encode(fh.read()).decode("utf-8")

with open("meeting.wav", "rb") as audio_file:
    transcript = client.audio.transcriptions.create(
        model="gpt-4o-transcribe-diarize",
        file=audio_file,
        response_format="diarized_json",
        chunking_strategy="auto",
        extra_body={
            "known_speaker_names": ["agent"],
            "known_speaker_references": [to_data_url("agent.wav")],
        },
    )

for segment in transcript.segments:
    print(segment.speaker, segment.text, segment.start, segment.end)
```

> **Note:** When `stream=true`, diarized responses emit `transcript.text.segment` events whenever a segment completes. `transcript.text.delta` events include a `segment_id` field, but diarized deltas do not stream partial speaker assignments until each segment is finalized.

> **Important:** `gpt-4o-transcribe-diarize` is currently available via `/v1/audio/transcriptions` only and is not yet supported in the Realtime API.

---

## Translations

The translations API takes as input the audio file in any of the supported languages and transcribes, if necessary, the audio into English. This endpoint supports only the `whisper-1` model.

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();

const translation = await openai.audio.translations.create({
  file: fs.createReadStream("/path/to/file/german.mp3"),
  model: "whisper-1",
});

console.log(translation.text);
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/german.mp3", "rb")

translation = client.audio.translations.create(
    model="whisper-1",
    file=audio_file,
)

print(translation.text)
```

> **Note:** We only support translation into English at this time.

---

## Supported Languages

We currently support the following languages through both the `transcriptions` and `translations` endpoint:

Afrikaans, Arabic, Armenian, Azerbaijani, Belarusian, Bosnian, Bulgarian, Catalan, Chinese, Croatian, Czech, Danish, Dutch, English, Estonian, Finnish, French, Galician, German, Greek, Hebrew, Hindi, Hungarian, Icelandic, Indonesian, Italian, Japanese, Kannada, Kazakh, Korean, Latvian, Lithuanian, Macedonian, Malay, Marathi, Maori, Nepali, Norwegian, Persian, Polish, Portuguese, Romanian, Russian, Serbian, Slovak, Slovenian, Spanish, Swahili, Swedish, Tagalog, Tamil, Thai, Turkish, Ukrainian, Urdu, Vietnamese, and Welsh.

While the underlying model was trained on 98 languages, we only list the languages that exceeded **<50% word error rate (WER)** which is an industry standard benchmark for speech-to-text model accuracy. The model will return results for languages not listed above but the quality will be low.

We support some ISO 639-1 and 639-3 language codes for GPT-4o based models. For language codes we don't have, try prompting for specific languages (i.e., "Output in English").

---

## Timestamps

By default, the Transcriptions API will output a transcript of the provided audio in text. The `timestamp_granularities[]` parameter enables a more structured and timestamped JSON output format, with timestamps at the segment, word level, or both.

This enables word-level precision for transcripts and video edits, which allows for the removal of specific frames tied to individual words.

**JavaScript (Node.js):**

```javascript
import fs from "fs";
import OpenAI from "openai";

const openai = new OpenAI();

const transcription = await openai.audio.transcriptions.create({
  file: fs.createReadStream("audio.mp3"),
  model: "whisper-1",
  response_format: "verbose_json",
  timestamp_granularities: ["word"]
});

console.log(transcription.words);
```

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/speech.mp3", "rb")

transcription = client.audio.transcriptions.create(
    file=audio_file,
    model="whisper-1",
    response_format="verbose_json",
    timestamp_granularities=["word"]
)

print(transcription.words)
```

> **Note:** The `timestamp_granularities[]` parameter is only supported for `whisper-1`.

---

## Longer Inputs

By default, the Transcriptions API only supports files that are less than **25 MB**. If you have an audio file that is longer than that, you will need to break it up into chunks of 25 MB's or less or use a compressed audio format.

To get the best performance, we suggest that you avoid breaking the audio up mid-sentence as this may cause some context to be lost.

**Python - Using PyDub:**

```python
from pydub import AudioSegment

song = AudioSegment.from_mp3("good_morning.mp3")

# PyDub handles time in milliseconds
ten_minutes = 10 * 60 * 1000
first_10_minutes = song[:ten_minutes]

first_10_minutes.export("good_morning_10.mp3", format="mp3")
```

> **Disclaimer:** OpenAI makes no guarantees about the usability or security of 3rd party software like PyDub.

---

## Prompting

You can use a `prompt` to improve the quality of the transcripts generated by the Transcriptions API.

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/speech.mp3", "rb")

transcription = client.audio.transcriptions.create(
    model="gpt-4o-transcribe",
    file=audio_file,
    response_format="text",
    prompt="The following conversation is a lecture about the recent developments around OpenAI, GPT-4.5 and the future of AI."
)

print(transcription.text)
```

### Prompting Tips

For `gpt-4o-transcribe` and `gpt-4o-mini-transcribe`, you can use the `prompt` parameter to improve the quality of the transcription by giving the model additional context similarly to how you would prompt other GPT-4o models.

> **Note:** Prompting is not currently available for `gpt-4o-transcribe-diarize`.

**Common prompting scenarios:**

1. **Correct specific words or acronyms** - For example: "The transcript is about OpenAI which makes technology like DALL·E, GPT-3, and ChatGPT..."

2. **Preserve context across segments** - Prompt the model with the transcript of the preceding segment. The `whisper-1` model only considers the final 224 tokens of the prompt and ignores anything earlier.

3. **Include punctuation** - Use a simple prompt that includes punctuation: "Hello, welcome to my lecture."

4. **Keep filler words** - If you want to keep filler words: "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking."

5. **Specify writing style** - For languages with different writing styles (e.g., simplified or traditional Chinese), use a prompt in your preferred style.

---

## Streaming Transcriptions

### Streaming a Completed Audio Recording

If you have an already completed audio recording, you can use our Transcription API with `stream=True` to receive a stream of transcript events as soon as the model is done transcribing that part of the audio.

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/speech.mp3", "rb")

stream = client.audio.transcriptions.create(
    model="gpt-4o-mini-transcribe",
    file=audio_file,
    response_format="text",
    stream=True
)

for event in stream:
    print(event)
```

You will receive a stream of `transcript.text.delta` events as soon as the model is done transcribing that part of the audio, followed by a `transcript.text.done` event when the transcription is complete.

Additionally, you can use the `include[]` parameter to include `logprobs` in the response to get the log probabilities of the tokens in the transcription.

> **Note:** Streamed transcription is not supported in `whisper-1`.

### Streaming an Ongoing Audio Recording

In the Realtime API, you can stream the transcription of an ongoing audio recording. To start a streaming session with the Realtime API, create a WebSocket connection:

```
wss://api.openai.com/v1/realtime?intent=transcription
```

**Example transcription session payload:**

```json
{
  "type": "transcription_session.update",
  "input_audio_format": "pcm16",
  "input_audio_transcription": {
    "model": "gpt-4o-transcribe",
    "prompt": "",
    "language": ""
  },
  "turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 500
  },
  "input_audio_noise_reduction": {
    "type": "near_field"
  },
  "include": ["item.input_audio_transcription.logprobs"]
}
```

---

## Improving Reliability

One of the most common challenges faced when using Whisper is the model often does not recognize uncommon words or acronyms. Here are some different techniques to improve reliability:

### Method 1: Using the Prompt Parameter

Pass a dictionary of the correct spellings using the optional prompt parameter.

**Python:**

```python
from openai import OpenAI

client = OpenAI()
audio_file = open("/path/to/file/speech.mp3", "rb")

transcription = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    response_format="text",
    prompt="ZyntriQix, Digique Plus, CynapseFive, VortiQore V8, EchoNix Array, OrbitalLink Seven, DigiFractal Matrix, PULSE, RAPT, B.R.I.C.K., Q.U.A.R.T.Z., F.L.I.N.T."
)

print(transcription.text)
```

> **Limitation:** This technique is limited to 224 tokens, so your list of SKUs needs to be relatively small for this to be a scalable solution.

### Method 2: Post-Processing with GPT-4

Use GPT-4 or GPT-3.5-Turbo as a post-processing step to correct spelling discrepancies.

**Python:**

```python
system_prompt = """
You are a helpful assistant for the company ZyntriQix. Your task is to correct
any spelling discrepancies in the transcribed text. Make sure that the names of
the following products are spelled correctly: ZyntriQix, Digique Plus,
CynapseFive, VortiQore V8, EchoNix Array, OrbitalLink Seven, DigiFractal
Matrix, PULSE, RAPT, B.R.I.C.K., Q.U.A.R.T.Z., F.L.I.N.T. Only add necessary
punctuation such as periods, commas, and capitalization, and use only the
context provided.
"""

def generate_corrected_transcript(temperature, system_prompt, audio_file):
    transcript = transcribe(audio_file)
    response = client.chat.completions.create(
        model="gpt-4",
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript}
        ]
    )
    return response.choices[0].message.content
```

This method is more scalable due to GPT-4's larger context window and more reliable because GPT-4 can be instructed and guided in ways that aren't possible with Whisper.

---

## API Reference

See the [API Reference](https://platform.openai.com/docs/api-reference/audio) for the full list of available parameters.

### Model Feature Comparison

| Feature | `whisper-1` | `gpt-4o-transcribe` | `gpt-4o-mini-transcribe` | `gpt-4o-transcribe-diarize` |
|---------|-------------|---------------------|--------------------------|------------------------------|
| Prompts | ✅ | ✅ | ✅ | ❌ |
| Logprobs | ❌ | ✅ | ✅ | ❌ |
| Streaming | ❌ | ✅ | ✅ | ✅ |
| Diarization | ❌ | ❌ | ❌ | ✅ |
| `timestamp_granularities[]` | ✅ | ❌ | ❌ | ❌ |
