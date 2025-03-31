import os 
from dotenv import load_dotenv,find_dotenv

class Config:
    """
    Configuration class to hold the model selection and API keys.

    Attributes:
    TRANSCRIPTION_MODEL (str): The model to use for transcription ('grog', 'deepgram').
    RESPONSE_MODEL (str): The model to use for response generation ('grog').
    TTS_MODEL (str): The model to use for text-to-speech ('deepgram').
    GROQ_API_KEY (str): API key for Grog services.
    DEEPGRAM_API_KEY (str): API key for Deepgram services.
    """

    # Model selection
    TRANSCRIPTION_MODEL = 'groq'
    RESPONSE_MODEL = 'groq'      
    TTS_MODEL = 'deepgram'         

    # API keys and paes
    GROQ_API_KEY = os.getenv("GROQ2_API_KEY")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

    def validate_config():
        """
        Validates the configuration settings.

        Raises:
        ValueError: If a required environment variable is not set.
        """
        if Config.TRANSCRIPTION_MODEL not in ['groq', 'deepgram', 'local']:
            raise ValueError("Invalid TRANSCRIPTION_MODEL. Must be one of ['grog', 'deepgram']")
        
        if Config.RESPONSE_MODEL not in ['groq']:
            raise ValueError("Invalid RESPONSE_MODEL. Must be one of ['groq']")
        
        if Config.TTS_MODEL not in ['deepgram']:
            raise ValueError("Invalid TTS_MODEL. Must be one of ['deepgram']")
        
        if Config.TRANSCRIPTION_MODEL == 'groq' and not Config.GROQ_API_KEY:
            raise ValueError("GROG_API_KEY is required for Groq models")
        
        if Config.TRANSCRIPTION_MODEL == 'deepgram' and not Config.DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is required for Deepgram models")
        
        if Config.RESPONSE_MODEL == 'groq' and not Config.GROQ_API_KEY:
            raise ValueError("GROG_API_KEY is required for Grog models")
        
        if Config.TTS_MODEL == 'deepgram' and not Config.DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is required for Deepgram models")