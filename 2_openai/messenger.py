# Importing libraries
import os
import requests
from dotenv import load_dotenv
import asyncio
import datetime
import win32com.client
import pythoncom
import subprocess
import re
import time
load_dotenv(override=True) # Load environment variables from .env file, override existing ones if necessary

## Setting up email sending method/tool 
# define a method/function to send email via Outlook COM
# @function_tool
def send_email_tool( 
    subject: str,
    body: str
    ) -> bool:
    """Send an email using the local Outlook desktop client."""
    # Read env var inside the function so it reflects whatever load_dotenv() loaded
    load_dotenv(override=True) # Load environment variables from .env file, override existing ones if necessary
    recipient = os.getenv("EMAIL_ADDRESS_TO")
    recipients = []
    if isinstance(recipient, list):
        recipients = [r.strip() for r in recipient if r.strip()]
    elif isinstance(recipient, str):
        if "," in recipient:
            recipients = [r.strip() for r in recipient.split(",") if r.strip()]
        else:
            recipients = [recipient.strip()]
    
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None

    # Validate all recipients
    invalid_recipients = [r for r in recipients if not validate_email(r)]
    if invalid_recipients:
        print(f"Error: Invalid email format(s): {invalid_recipients}")
        return False
    
    recipient_str = "; ".join(recipients)
    
    if not recipient_str:
        print("Error: No recipients specified. Email not sent.")
        return False

    if body is None:
        body = "Hello there!! "

    print(f"\nSending email to {recipient_str} with subject '{subject}'...")

    # Ensure COM is initialized for the current thread (agent tool calls may run in worker threads).
    pythoncom.CoInitialize()
    try:
        # Connect to Outlook, launch it if not running
        outlook = None
        for attempt in range(5):
            try:
                outlook = win32com.client.Dispatch("Outlook.Application")
                outlook.GetNamespace("MAPI")
                print("Outlook is up & running...")
                break
            except Exception as e:
                if attempt == 0:
                    print("Outlook not running — launching...")
                    for p in [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
                              r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE"]:
                        if os.path.exists(p):
                            subprocess.Popen([p])
                            time.sleep(45)
                            break
                    else:
                        print("Error: Outlook executable not found.")
                        return False
                elif attempt < 4:
                    print(f"Outlook connect attempt {attempt + 1}/5 — waiting...")
                    time.sleep(15)
                else:
                    print(f"Error: Outlook connect failed after 5 attempts: {e}")
                    return False

        try:
            mail = outlook.CreateItem(0)
            mail.To = recipient_str
            mail.Subject = subject
            mail.Body = body

            mail.Send()
            print(f"Email sent successfully to '{recipient_str}' with subject '{subject}'.")
            return True

        except Exception as e:
            print(f"Failed to send email: {e}")
            # Print recipient info for debugging
            print(f"Debug - Recipients used: {repr(recipient_str)}")
            print(f"Debug - Recipient type: {type(recipient_str)}")
            return False
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
# let's create some custom tools with Python using OpenAI SDK 
# @function_tool # help's making json format, required for AI model to understand about the function/tool
def record_message_tool(topic: str, message: str) -> str:
    """ Record the user message with it's topic in a file  """
    print(f"Tool called to record an message: '{message}' on topic '{topic}'")
    # setting up the timestamp and entry format
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n\n ## [{timestamp}] - TOPIC: {topic}\n* **Content:** {message}"

    with open("ai_model_message.txt","a", encoding="utf-8") as file:
        file.write(entry)
    return f"Successfully saved message on topic '{topic}'."