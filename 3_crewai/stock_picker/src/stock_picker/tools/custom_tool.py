import os
from crewai.tools import BaseTool, tool
from typing import Type
from pydantic import BaseModel, Field
from tavily import TavilyClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class TavilySearchInput(BaseModel):
    """Input schema for the custom Tavily search tool."""
    query: str = Field(..., description="The precise search query string to look up on the web/internet.")

class CustomTavilySearchTool(BaseTool):
    name: str = "web_search_tool"
    description: str = (
        "A comprehensive web search engine. Use this tool whenever you need to look up real-time information, news, current events/affairs, or industry data on internet."
    )
    args_schema: Type[BaseModel] = TavilySearchInput

    def _run(self, query: str) -> str:
        # Initialize and run tavily search tool
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY is not set in the environment variables."
        try:
            tavily_client=TavilyClient(api_key=api_key)
            response =  tavily_client.search(query=query, max_results=5)
            return str(response)
        except Exception as e:
            return f"Error executing search: {str(e)}"

# define a tool around sending the email to recipients via SMTP
@tool("Send email to the recipient")
def send_email_tool(
    subject: str,
    body: str
) -> str:

    """
    Send an email using the SMTP server. Use this whenever there is a need to send email with a given subject and body to the recipient.
    Args:
        subject: The subject of the email
        body: The body of the email as plain text    
    Returns:
        A string indicating the status of the sent email to recipient.
    """
    # Importing environment variables
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
    SMTP_SERVER=os.getenv("SMTP_SERVER")

    # Configuration settings
    SMTP_PORT = 465                  # Standard port for SS

    # Create message container
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    message["Subject"] = subject

    # Add message body
    message.attach(MIMEText(body, "plain"))

    try:
        # Connect and send
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, GMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        print(f"Email sent successfully with '{subject}' to '{RECEIVER_EMAIL}', Thanks!")
    except Exception as e:
        print(f"Error: {e}")
