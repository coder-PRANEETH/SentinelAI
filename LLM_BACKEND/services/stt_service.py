"""
Speech-to-Text service using Faster-Whisper.
Provides functionality to transcribe audio files to text.
"""

from faster_whisper import WhisperModel


def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe an audio file using Faster-Whisper.
    
    Args:
        file_path: Path to the audio file to transcribe
        
    Returns:
        Transcribed text from the audio file
        
    Raises:
        Exception: If transcription fails
    """
    try:
        # Initialize Faster-Whisper model (base model for balance between speed and accuracy)
        model = WhisperModel("base", device="cpu", compute_type="default")
        
        # Transcribe the audio file
        segments, info = model.transcribe(file_path, language="en")
        
        # Combine all segments into a single transcript
        transcript = " ".join([segment.text for segment in segments])
        
        return transcript.strip()
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")
