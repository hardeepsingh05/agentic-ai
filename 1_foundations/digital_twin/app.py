# Let's import some libraries
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from pypdf import PdfReader
from anthropic import AnthropicFoundry
from IPython.display import Markdown, display
import gradio as gr
import json
import os

# Import some function/method from other files
from context import system_prompt
from tools import tools_openai, tools_anthropic, handle_tool_calls_anthropic, handle_tool_calls_openai
from style import CSS, JS, EXAMPLES

load_dotenv(override=True)

## Loading environment variables 
# From OpenAI
AZURE_OPENAI_API_KEY= os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_MODEL_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_GPT_41 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_41")
AZURE_OPENAI_DEPLOYMENT_GPT_54_mini = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_54_mini")
AZURE_OPENAI_DEPLOYMENT_GPT_55 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_55")
AZURE_OPENAI_DEPLOYMENT_GPT_4O_mini = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_4O_mini")
# From Anthropic
AZURE_CLAUDE_DEPLOYMENT_OPUS_48=os.getenv("AZURE_CLAUDE_DEPLOYMENT_OPUS_48")
AZURE_CLAUDE_ENDPOINT=os.getenv("AZURE_CLAUDE_ENDPOINT")
AZURE_CLAUDE_API_KEY=os.getenv("AZURE_CLAUDE_API_KEY")

# setting up clients for both AI models
# Set the client for AzureOpenAI LLM 
client_OpenAI = AzureOpenAI(
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY
)
# Set the client for Anthropic model
client_anthropic=AnthropicFoundry(
    api_key=AZURE_CLAUDE_API_KEY,
    base_url=AZURE_CLAUDE_ENDPOINT
)

# Let's update this method for calling for AI model to chat with tool
def ask_AI_model(user_prompt, history, system_prompt: str = system_prompt, client: str = "openai", OpenAI_deployment: str = AZURE_OPENAI_DEPLOYMENT_GPT_41, Anthropic_deployment: str = AZURE_CLAUDE_DEPLOYMENT_OPUS_48,
    tools_openai:list = tools_openai, tools_anthropic:list = tools_anthropic) -> str:
    if client == "OpenAI" or client == "openAI" or client == "openai":
        # let's set the AI messages
        messages = [
            {
                "role": "system",
                "content": system_prompt
            }] + history + [
            {
                "role": "user",
                "content": user_prompt
            }
        ]
        # seeking response from AI model
        response = client_OpenAI.chat.completions.create(
        model=OpenAI_deployment,
        messages=messages,
        tools=tools_openai
        )
        # set the condition for tools calling
        if response.choices[0].finish_reason=="tool_calls":
            message = response.choices[0].message
            messages.append(message) # appnending the message to the chat history
            tool_calls = message.tool_calls
            results = handle_tool_calls_openai(tool_calls)
            messages.extend(results)
            # calling AI model second time
            response = client_OpenAI.chat.completions.create(
            model=OpenAI_deployment,
            messages=messages,
            tools=tools_openai
            )
        return response.choices[0].message.content

    elif client == "anthropic" or client == "Anthropic" or client == "anthro":
        # Let's set the AI messages
        history = [
            {
                "role": h["role"],
                "content": h["content"]
            } for h in history
        ]
        messages = history + [
            {
                "role": "user",
                "content": user_prompt
            }
        ]
        # seeking response from AI model
        response = client_anthropic.messages.create(
            model=Anthropic_deployment,
            system=system_prompt,
            messages=messages,
            tools=tools_anthropic,
            max_tokens=5000
        )
        
        if response.stop_reason == "tool_use":
            messages.append({
                "role": "assistant",
                "content": response.content
                })
            response_content = response.content
            results = handle_tool_calls_anthropic(response_content)
                
            # Only append tool result message if we have results
            if results:
                messages.append({
                    "role": "user",
                    "content": results
                })
                
                # Calling model second time
                response = client_anthropic.messages.create(
                    model=Anthropic_deployment,
                    system=system_prompt,
                    messages=messages,
                    tools=tools_anthropic,
                    max_tokens=5000
                )
        
        return response.content[0].text
    else:
        return "PLEASE GIVE A CHECK ON CLIENT NAME BEFORE CALLING FUNCTION"


## Let's launch our gradio application of digital twin
if __name__ == "__main__":
    gr.ChatInterface(
        ask_AI_model,
        examples=EXAMPLES,
        title = "Digital Twin",
        description="Talk to my AI twin about my career",
        chatbot=gr.Chatbot(show_label=False)
    ).launch(css=CSS,js=JS,theme=gr.themes.Base())
