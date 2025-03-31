from groq import Groq
from faster_whisper import WhisperModel
import logging
import os
from dotenv import load_dotenv

load_dotenv()

whisper_model = WhisperModel("tiny", compute_type="int8")

def transcribe_audio(model, GROQ_API_KEY, audio_file_path):
    try:
        if model == 'groq':
            client = Groq(api_key=GROQ_API_KEY)
            with open(audio_file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio_file
                )
            return transcription.text

        elif model == "local":
            segments, _ = whisper_model.transcribe(audio_file_path, beam_size=5, language="en", 
                                                   condition_on_previous_text=False)
            transcriptions = []
            for segment in segments:
                transcriptions.append(segment.text)
            return " ".join(transcriptions)

        else:
            raise ValueError("Unsupported transcription model")

    except Exception as e:
        logging.error(f"Failed to transcribe audio: {e}")
        return "Error in transcribing audio"