"""
Transcript export service.

Provides export functionality for transcripts to various formats.
With the simplified transcription model (gpt-4o-transcribe), only
plain text and JSON exports are fully supported.

Note: SRT/VTT formats require timestamps which are no longer available
in the simplified model. These methods return single-caption fallbacks.
"""

from __future__ import annotations

import json

from app.models.transcript import Transcript


class TranscriptExporter:
    """Service for exporting transcripts to various formats."""

    def export_txt(self, transcript: Transcript) -> str:
        """
        Export transcript to plain text format.

        Returns the full text content without timestamps or formatting.

        Args:
            transcript: Transcript to export

        Returns:
            Plain text content
        """
        return transcript.text

    def export_json(self, transcript: Transcript) -> str:
        """
        Export transcript to structured JSON format.

        Includes transcript metadata and text content.

        Args:
            transcript: Transcript to export

        Returns:
            JSON formatted string with indentation
        """
        data = transcript.model_dump()
        # Convert datetime to ISO string for JSON serialization
        if "created_at" in data and data["created_at"]:
            data["created_at"] = data["created_at"].isoformat()
        return json.dumps(data, indent=2, ensure_ascii=False)

    def export_srt(self, transcript: Transcript) -> str:
        """
        Export transcript to SRT (SubRip) subtitle format.

        Note: With simplified transcription model, timestamps are not available.
        Returns a single caption spanning the full duration.

        Args:
            transcript: Transcript to export

        Returns:
            SRT formatted string with single caption
        """
        start_time = self._format_srt_timestamp(0.0)
        end_time = self._format_srt_timestamp(transcript.duration)
        return f"1\n{start_time} --> {end_time}\n{transcript.text}\n"

    def export_vtt(self, transcript: Transcript) -> str:
        """
        Export transcript to WebVTT subtitle format.

        Note: With simplified transcription model, timestamps are not available.
        Returns a single caption spanning the full duration.

        Args:
            transcript: Transcript to export

        Returns:
            WebVTT formatted string with single caption
        """
        start_time = self._format_vtt_timestamp(0.0)
        end_time = self._format_vtt_timestamp(transcript.duration)
        return f"WEBVTT\n\n{start_time} --> {end_time}\n{transcript.text}\n"

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Format seconds as SRT timestamp (HH:MM:SS,mmm).

        Args:
            seconds: Time in seconds from video start

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_timestamp(self, seconds: float) -> str:
        """
        Format seconds as WebVTT timestamp (HH:MM:SS.mmm).

        Args:
            seconds: Time in seconds from video start

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
