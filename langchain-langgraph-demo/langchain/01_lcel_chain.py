import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

MODEL = os.getenv("MODEL", "gpt-4o")

# 1) a prompt template with variables
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise technical teacher. Answer in ONE sentence."),
    ("human", "Explain {topic} to a {audience}."),
])

# 2) a model  3) an output parser (message -> plain string)
model = ChatOpenAI(model=MODEL, temperature=0)
parser = StrOutputParser()

# THE CHAIN — this is LangChain in one line:
chain = prompt | model | parser

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in ../.env to run this live."); raise SystemExit(0)

    print("chain = prompt | model | parser\n")
    for topic, aud in [("vector embeddings", "DevOps engineer"),
                       ("idempotency", "junior developer")]:
        out = chain.invoke({"topic": topic, "audience": aud})
        print(f"• {topic} → {out}\n")

    # Streaming is free — the same chain, token by token:
    print("Streaming demo: ", end="", flush=True)
    for chunk in chain.stream({"topic": "a race condition", "audience": "student"}):
        print(chunk, end="", flush=True)
    print()