# Importing necessary libraries
import json
import os
import requests

# let's create some custom tools with Python
def record_message_tool(message):
    print(f"Tool called to record an message: {message}")
    with open("user_message.txt","a", encoding="utf-8") as file:
        file.write(message + "\n")
    return "Message Received!!"

## let define some function for recording details and recording unanswered question
def record_user_details(email, name: str="Name not defined", notes: str= "not provided"):
    record_message_tool(f"\nRecording interest from {name} with email {email} and notes {notes}\n")
    return "User Details Recorded!"

def record_unknown_question(question):
    record_message_tool(f"\nRecording '{question}' asked that I couldn't answer\n")
    return "Unknown Question Recorded!"


# define a json info for AI model on how to use tool (OpenAI)
record_user_details_json_openai = {
    "name":"record_user_details",
    "description":"Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters":{
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name":{
                "type": "string",
                "description": "The user's name if they provide it"
            },
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth noting/recording"
            }
        },
        "required":["email"],
        "additionalProperties":False
    }
}
record_unknown_question_json_openai = {
    "name":"record_unknown_question",
    "description":"Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters":{
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            }
        },
        "required":["question"],
        "additionalProperties":False
    }
}
# combine tools
tools_openai = [
    {
        "type": "function",
        "function": record_user_details_json_openai
    },
    {
        "type": "function",
        "function": record_unknown_question_json_openai
    }
]

tools_anthropic =[
{   
    "name":"record_unknown_question",
    "description":"Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "input_schema":{
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            }
        },
        "required":["question"]
    }
}, 
{
    "name":"record_user_details",
    "description":"Use this tool to record that a user is interested in being in touch and provided an email address",
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name":{
                "type": "string",
                "description": "The user's name if they provide it"
            },
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth noting/recording"
            }
        },
        "required":["email"]
    }
}
]

# define a common  map for both AI models
tool_map = {
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question
}

## Let's make a function to handle tool calls
## It will take a list of tool calls, and run them. This is the replacement for that code which we put after knowing AI need tools
## tool handling function for openAI
def handle_tool_calls_openai(tool_calls):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        print(f"Tool called: '{tool_name}' with arguments '{arguments}'", flush=True)
        # Using tool_map to call the tool function
        tool = tool_map.get(tool_name)
        result = tool(**arguments) if tool else "UNKNOWN TOOL: " + tool_name
        results.append(
            {
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            }
        )
    return results

## Tool handling function for Anthropic
def handle_tool_calls_anthropic(response_content):
    results = [] # define an empty list to store the results of the tool
    for content in response_content:
        if content.type == "tool_use":
            tool_name, tool_inputs, tool_id = content.name, content.input, content.id
            print(f"Tool called: '{tool_name}' with arguments '{tool_inputs}'", flush=True)
             # Using tool_map to call the tool function
            tool = tool_map.get(tool_name)
            result = tool(**tool_inputs) if tool else "UNKNOWN TOOL: " + tool_name
            # storing tool results                
            results.append({
                "type":"tool_result",
                "content": str(result),
                "tool_use_id": tool_id
            })
    return results