import os
import base64
import time
import sqlite3
from typing import Iterator, Optional
import typer
from agno.agent import Agent, RunResponse
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.embedder.google import GeminiEmbedder
from agno.tools.yfinance import YFinanceTools
#from agno.tools.twilio import TwilioTools
from twilio_tools import TwilioTools
from agno.tools.arxiv import ArxivTools
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.calculator import CalculatorTools
from agno.tools.openweather import OpenWeatherTools
from agno.tools.gmail import GmailTools
from agno.tools.duckduckgo import DuckDuckGoTools
from notion_tools import NotionTools
from agno.tools.youtube import YouTubeTools
from agno.tools.googlecalendar import GoogleCalendarTools
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.models.google import Gemini
from agno.vectordb.lancedb import LanceDb, SearchType
from rich.prompt import Prompt
from agno.media import Audio, Image
from agno.utils.pprint import pprint_run_response
from dotenv import load_dotenv
import datetime
import json
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from agno.tools.mcp import MCPTools
from mcp import StdioServerParameters, ClientSession
from audio import record_audio, play_audio
from transcription import transcribe_audio
from tts import text2speech
from config import Config
import logging
from pathlib import Path
from tzlocal import get_localzone_name
from agno.team import Team
from elevenlabs import play


load_dotenv()


os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
os.environ["TWILIO_ACCOUNT_SID"] = os.getenv("TWILIO_ACCOUNT_SID")
os.environ["TWILIO_AUTH_TOKEN"] = os.getenv("TWILIO_AUTH_TOKEN")
os.environ["TWILIO_FROM_NUMBER"] = os.getenv("TWILIO_FROM_NUMBER")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_TOKEN = os.getenv("NOTION_API_KEY")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALEN_CREDENTIALS_PATH = os.path.join(BASE_DIR, "demo_calen_credentials.json")
GMAIL_CREDENTIALS_PATH = os.path.join(BASE_DIR, "demo_gmail_credentials.json")
# TOKEN_PATH = os.path.join(BASE_DIR, "calender_token.json")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
AGENT_SESSIONS_DB_PATH = "AGENT_SESSIONS/agents_sessions.db"


if not os.path.exists(CALEN_CREDENTIALS_PATH) or not os.path.exists(GMAIL_CREDENTIALS_PATH):
    raise FileNotFoundError(
        f"Credentials file not found at {CALEN_CREDENTIALS_PATH}. Please download it from Google Cloud Console."
    )

if not os.access(BASE_DIR, os.W_OK):
    raise PermissionError(
        f"Directory {BASE_DIR} is not writable. Please adjust permissions or run in a writable directory."
    )
if not os.access(CALEN_CREDENTIALS_PATH, os.W_OK):
    raise PermissionError("Permission Denied: CALEN_CREDENTIALS_PATH")

if not os.access(GMAIL_CREDENTIALS_PATH, os.W_OK):
    raise PermissionError("Permission Denied: GMAIL_CREDENTIALS_PATH")


# Notion API headers
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


if not os.path.exists("database"):
    os.makedirs("database")


DB_PATH = "database/chat_history.db"

def transcribe():
    GROQ_API_KEY = os.getenv("GROQ2_API_KEY") # Seperate Groq API for transcription
    audio_file = "input.wav"
    record_audio(audio_file)
    user_input = transcribe_audio(
        Config.TRANSCRIPTION_MODEL,
        GROQ_API_KEY=GROQ_API_KEY,
        audio_file_path=audio_file,
    )
    logging.info("You said:", user_input)
    return user_input

# PDF knowledge base
def create_kb(pdf_path):
    """Create a PDF knowledge base for document analysis"""
    pdf_knowledge_base = PDFKnowledgeBase(
        path=pdf_path,
        vector_db=LanceDb(
            table_name="KB",
            uri="Knowledge_base/pdfs",
            search_type=SearchType.vector,
            embedder=GeminiEmbedder(dimensions=1536),
        ),
        reader=PDFReader(chunk=True),
    )
    pdf_knowledge_base.load(recreate=True)
    return pdf_knowledge_base

# Base function to create specialized agents
def create_specialized_agent(name,description, tools, session_id,table_name):
    """Create a specialized agent with common parameters"""
    return Agent(
        name=name,
        model=Gemini(id="gemini-2.0-flash-exp"),
        description=description,
        tools=tools,
        storage=SqliteAgentStorage(table_name=table_name, db_file=str(AGENT_SESSIONS_DB_PATH), auto_upgrade_schema=True),
        session_id=session_id,
        user_id="User",
        add_history_to_messages=True,
        read_chat_history=True,
        num_history_responses=10,
        show_tool_calls=True,
        markdown=True,
    )

# Document analysis agent
def create_document_analysis_agent(knowledge_base, session_id, table_name):
    """Create the document analysis agent with optional knowledge base"""
    description = (
        "I am an expert in analyzing documents using RAG (Retrieval Augmented Generation). "
        "If no document is loaded, I'll let you know that no document is available."
    )
    return Agent(
        name="Document Analysis Agent",
        model=Gemini(id="gemini-2.0-flash-exp"),
        description=description,
        knowledge=knowledge_base,
        storage=SqliteAgentStorage(table_name=table_name, db_file=str(AGENT_SESSIONS_DB_PATH), auto_upgrade_schema=True),
        session_id=session_id,
        user_id="User",
        add_history_to_messages=True,
        read_chat_history=True,
        num_history_responses=10,
        show_tool_calls=True,
        markdown=True,
    )

console = Console()

# Print chat history function
def print_chat_history(agent,session_id):
    """Print chat history for the given agent"""
    if session_id not in agent.session_id:
        console.print(f"[yellow]Welcome! This appears to be a new session with ID: {agent.session_id}[/yellow]")
        return False
    try:
        console.print(
            Panel(
                JSON(
                    json.dumps(
                        [
                            m.model_dump(include={"role", "content"})
                            for m in agent.memory.messages
                        ]
                    ),
                    indent=4,
                ),
                title=f"Chat History for session_id: {agent.session_id}",
                expand=True,
            )
        )
        return True
    except Exception as e:
        console.print(f"[red]Error printing chat history: {e}[/red]")
        console.print(f"[yellow]Probably you might have accessed first time which has no messages")
        return False
    
# Main function
def main():
    """Main function to run the interactive chat interface"""
    session_id = input("Provide the session ID to access the particular session (If need to create one, provide that too): ")
    print("-------------------------------------------------------------------------------------------------------------------------")
    pdf_path = input("Provide the path to the PDF file for document analysis (or press Enter to skip): ")
    if pdf_path:
        knowledge_base = create_kb(pdf_path)
    else:
        knowledge_base = None

    # Member Agents
    document_analysis_agent = create_document_analysis_agent(knowledge_base, session_id,"DOCUMENT")
    web_search_agent = create_specialized_agent("Web Search Agent","Expert in web search using DuckDuckGo.", [DuckDuckGoTools()], session_id,"WEB")
    stock_market_agent = create_specialized_agent("Stock Market Agent","Expert in stock market data using YFinance.", [YFinanceTools(enable_all=True)], session_id,"STOCK")
    research_papers_agent = create_specialized_agent("Research Paper Agent","Expert in research papers using Arxiv.", [ArxivTools()], session_id,"PAPER")
    messaging_agent = create_specialized_agent(
        "Message Agent",
        "Expert in messaging and calling using Twilio.",
        [TwilioTools()],
        session_id,
        "TWILIO"
        
    )
    weather_agent = create_specialized_agent(
        "Weather Agent",
        "Expert in weather information using OpenWeather.",
        [OpenWeatherTools(units="imperial", api_key=OPENWEATHER_API_KEY)],
        session_id,
        "WEATHER",
    )
    web_scraping_agent = create_specialized_agent(
        "Web Scrape Agent",
        "Expert in web scraping using Firecrawl.",
        [FirecrawlTools(scrape=True, limit=3, api_key=FIRECRAWL_API_KEY)],
        session_id,
        "FIRECRAWL",
    )
    email_agent = create_specialized_agent(
        "Email Agent Agent",
        "Expert in email management using Gmail.",
        [GmailTools(credentials_path=GMAIL_CREDENTIALS_PATH)],
        session_id,
        "EMAIL",
    )
    calculator_agent = create_specialized_agent("Calculator Agent","Expert in calculations.", [CalculatorTools(enable_all=True)], session_id,"CALCULATOR")
    youtube_agent = create_specialized_agent("Youtube Agent","Expert in YouTube video tasks.", [YouTubeTools()], session_id,"YOUTUBE")
    server_params = StdioServerParameters(command="npx", args=["-y", "@modelcontextprotocol/server-github"])
    github_agent = create_specialized_agent("Github agent","Expert in GitHub analysis using MCP.", [MCPTools(server_params=server_params)], session_id,"GITHUB")
    notion_agent = create_specialized_agent(
        "Notion Agent",
        "Expert in Notion database and page management.",
        [NotionTools(token=NOTION_TOKEN, database_id=DATABASE_ID)],
        session_id,
        "NOTION",
    )
    calendar_agent = create_specialized_agent(
        "Calender Agent",
        "Expert in Google Calendar management.",
        [GoogleCalendarTools(credentials_path=CALEN_CREDENTIALS_PATH)],
        session_id,
        "CALENDER",
    )

    # Member Agents Assemble
    team_members = [
        web_search_agent,
        stock_market_agent,
        research_papers_agent,
        messaging_agent,
        weather_agent,
        web_scraping_agent,
        email_agent,
        calculator_agent,
        youtube_agent,
        github_agent,
        notion_agent,
        calendar_agent,
        document_analysis_agent,
    ]

    # Manager Agent in a route fashion
    team = Team(
        model=Gemini(id="gemini-2.0-flash-exp"),
        description="Your name is DRAX , a friendly assistant , developed by me. My name is Atharsh. Your task is to do specific tasks for me I give you. And you are manager (a kind of supervisor) for many helper(members) agents down you , so you dont have to do any work but based on the input provided choose which member agent will be suitable and delegate the task to them and get response from them and update it to me. And most importantly the member agents should not communicate with directly you are one who is get the resposne from the Member Agent and then provide it to me in a specific format [NAME OF THE MEMBER AGENT: , MEMBER AGENT RESPONSE: ]. So be friendly and answer politely . And the outputs u provide must be neatly strcutured too.",
        mode="route",
        members=team_members,
        storage=SqliteAgentStorage(table_name="MANAGER", db_file=str(AGENT_SESSIONS_DB_PATH), auto_upgrade_schema=True),
        session_id=session_id,
        user_id="User",
        share_member_interactions=True,
        show_members_responses=True,
        show_tool_calls=True,
        num_of_interactions_from_history=10,
        enable_team_history=True,
        
    )

    while True:
        print_chat_history(team,session_id)
        user_input = Prompt.ask("Enter your query or type '/record' to record audio")
        if user_input == "/record":
            print("Recording audio...")
            user_input = transcribe()
        if user_input.lower() in ("exit", "quit", "bye"):
            break
        response : RunResponse = team.run(user_input)
        print(response.content)
        
        tts_choice = Prompt.ask("Type '/speak' if you want the TTS to be enabled")
        if tts_choice == "/speak":
            audio = text2speech(response.content)
            play(audio)

if __name__ == "__main__":
    main()