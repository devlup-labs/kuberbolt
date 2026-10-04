import os
import requests
import json
import base64
from uuid import uuid4
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain.tools import tool

SDK_SERVER = os.getenv("SDK_SERVER_URL", "")
BUYER_PUBKEY = os.getenv("BUYER_NOSTR_PUBKEY", "")
BUYER_SESSION_TOKEN = os.getenv("BUYER_SESSION_TOKEN", "")
BUYER_FP_ADDR = os.getenv("BUYER_FP_ADDR", "")


def required_setting(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def sdk_auth_headers() -> dict[str, str]:
    """Build the bearer authentication header issued during registration."""
    if not BUYER_PUBKEY or not BUYER_SESSION_TOKEN:
        raise RuntimeError(
            "BUYER_NOSTR_PUBKEY and BUYER_SESSION_TOKEN must be set "
            "from the SDK registration response"
        )
    return {"Authorization": f"Bearer {BUYER_SESSION_TOKEN}"}

@tool
def discover_providers(category: str) -> list[dict]:
    """Find service providers by category on the Nostr network."""
    resp = requests.get(
        f"{required_setting('SDK_SERVER_URL', SDK_SERVER)}/api/providers",
        params={"category": category},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])

@tool
def request_endpoint(provider_pubkey: str) -> dict:
    """Send a NIP-44 encrypted DM to resolve the provider's private gRPC endpoint."""
    resp = requests.post(
        f"{required_setting('SDK_SERVER_URL', SDK_SERVER)}/api/requests",
        headers=sdk_auth_headers(),
        json={
            "agent_pubkey": BUYER_PUBKEY,
            "provider_pubkey": provider_pubkey,
            "payload": {"action": "resolve_endpoint", "job_id": str(uuid4())},
            "timeout_seconds": 30,
        },
    )
    resp.raise_for_status()
    return resp.json()["result"]

@tool
def call_service(host: str, port: int, text_to_summarize: str) -> str:
    """Call the seller's Financial Pod via gRPC with L402 payment.
    This routes through the buyer's local Financial Pod.
    """
    import subprocess
    
    target = f"{host}:{port}"
    job_spec = json.dumps({"text": text_to_summarize})
    
    # grpcurl encodes protobuf bytes fields as base64 in JSON.
    job_spec_base64 = base64.b64encode(job_spec.encode()).decode()
    
    try:
        # Using grpcurl to communicate with the local Financial Pod
        result = subprocess.run([
            "grpcurl", "-plaintext", "-d", 
            json.dumps({
                "provider_endpoint": target, 
                "service_kind": "text-summarization", 
                "job_spec": job_spec_base64
            }),
            required_setting("BUYER_FP_ADDR", BUYER_FP_ADDR),
            "kuberbolt.v1.FinancialPodService/CallService"
        ], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Failed to call service: {e.stderr}"
    except Exception as e:
        return f"Failed to call service: {e}"

@tool
def publish_feedback(provider_pubkey: str, job_id: str, rating: int, feedback: str) -> dict:
    """Publish on-chain feedback for a completed job."""
    resp = requests.post(
        f"{required_setting('SDK_SERVER_URL', SDK_SERVER)}/api/feedback",
        headers=sdk_auth_headers(),
        json={
            "reviewer_pubkey": BUYER_PUBKEY,
            "counterparty_pubkey": provider_pubkey,
            "job_id": job_id,
            "feedback_text": feedback,
            "rating": rating,
        },
    )
    resp.raise_for_status()
    return resp.json()

def run_agent(prompt: str):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
    tools = [discover_providers, request_endpoint, call_service, publish_feedback]
    
    template = '''Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''
    
    prompt_template = PromptTemplate.from_template(template)
    
    agent = create_react_agent(llm, tools, prompt_template)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    print(f"Running agent with prompt: {prompt}")
    result = agent_executor.invoke({"input": prompt})
    print(result["output"])

if __name__ == "__main__":
    import sys
    
    prompt = "Find a text summarization provider on the Kuberbolt network and use it to summarize this text: 'The Lightning Network is a payment channel network built on top of Bitcoin...'"
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        
    run_agent(prompt)
