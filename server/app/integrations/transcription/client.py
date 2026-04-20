from __future__ import annotations


class TranscriptionClient:
    async def transcribe(self, file_url: str) -> str:
        raise NotImplementedError("Transcription provider will be integrated later.")
