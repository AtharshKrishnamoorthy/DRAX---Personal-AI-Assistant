from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import os

load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

def text2speech(text):
    try:
       audio = client.text_to_speech.convert(
           text=text,
           voice_id="JBFqnCBsd6RMkjVDRZzb",
           model_id="eleven_multilingual_v2",
           output_format="mp3_44100_128",
       )
       
       return audio
    
    except Exception as e:
        print("ERROR GENERATING VOICE")