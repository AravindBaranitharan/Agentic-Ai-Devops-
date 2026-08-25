"""
LangChain · 03 — Structured output (a real everyday use case).

Stop parsing strings. `with_structured_output(Model)` makes the LLM return a typed,
validated Pydantic object — perfect for extraction, classification and routing.

Run:  python 03_structured_output.py     (needs OPENAI_API_KEY)
"""

import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_openai import ChatOpenAI

MODEL = os.getenv("MODEL", "gpt-4o")


class Priority(str, Enum):
    low = "low"; medium = "medium"; high = "high"; urgent = "urgent"


class SupportTicket(BaseModel):
    """The structured shape we want extracted from a raw support message."""
    category: str = Field(description="e.g. billing, auth, bug, feature-request")
    priority: Priority
    summary: str = Field(description="one-line summary")
    needs_human: bool


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in ../.env to run this live."); raise SystemExit(0)

    extractor = ChatOpenAI(model=MODEL, temperature=0).with_structured_output(SupportTicket)

    msgs = [
        "My payment failed twice and now I'm locked out of my account. This is urgent!!",
        "It would be nice if the dashboard had a dark mode someday.",
    ]
    for m in msgs:
        ticket = extractor.invoke(m)
        print(f"IN : {m}")
        print(f"OUT: {ticket!r}\n")
