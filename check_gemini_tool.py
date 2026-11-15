import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = os.getenv("GEMINI_MODEL")
print("Model:", model)

get_customer = types.FunctionDeclaration(
    name="get_customer",
    description="Retrieve the details of one customer by numeric customer ID.",
    parameters_json_schema={
        "type": "object",
        "properties": {"customer_id": {"type": "integer"}},
        "required": ["customer_id"],
    },
)

config = types.GenerateContentConfig(
    tools=[types.Tool(function_declarations=[get_customer])],
    # We run tools ourselves (through MCP), so Gemini must not auto-call them.
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

try:
    resp = client.models.generate_content(
        model=model, contents="Find customer 1025.", config=config
    )
    for call in resp.function_calls or []:
        print("Gemini wants to call:", call.name, dict(call.args))
    if not resp.function_calls:
        print("No tool call. Text reply:", resp.text)
except Exception as e:
    print("ERROR:", type(e).__name__, e)