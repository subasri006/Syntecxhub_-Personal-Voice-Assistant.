"""AI Conversation and Natural Language Understanding Service.

Supports:
1. Online Generative AI via Google Gemini REST API or OpenAI-compatible REST API
   (reads GEMINI_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY securely from environment or .env).
2. Robust Offline Conversational Knowledge Engine (handles general questions,
   definitions, math calculations, code explanation, chit-chat, and ambiguity clarification).
3. Two-tier response generation: Full informative text for chat UI, and a concise 1-2
   sentence spoken summary for offline Text-to-Speech to avoid lengthy audio playback.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def load_env_file() -> None:
    """Read key-value pairs from .env in project root if present, without overwriting existing env."""
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    env_file = root_dir / ".env"
    if not env_file.exists():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as exc:
        logger.debug("Could not read .env file: %s", exc)


# Load .env once upon module import
load_env_file()


def get_configured_ai_provider() -> Tuple[Optional[str], Optional[str]]:
    """Check whether an AI API key is configured.

    Returns (provider_name, api_key) or (None, None).
    """
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip():
        return "gemini", gemini_key.strip()

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and openai_key.strip():
        return "openai", openai_key.strip()

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        return "groq", groq_key.strip()

    return None, None


# --- Safe Math Evaluation ---

SAFE_MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval_math_expression(expr_str: str) -> Optional[float]:
    """Safely evaluate basic arithmetic without arbitrary code execution."""
    cleaned = expr_str.strip().replace("x", "*").replace("^", "**")

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type in SAFE_MATH_OPERATORS:
                left = _eval(node.left)
                right = _eval(node.right)
                return SAFE_MATH_OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in SAFE_MATH_OPERATORS:
                return SAFE_MATH_OPERATORS[op_type](_eval(node.operand))
        raise ValueError("Unsupported expression")

    try:
        parsed = ast.parse(cleaned, mode="eval")
        res = _eval(parsed.body)
        return float(res)
    except Exception:
        return None


# --- Offline Knowledge Base ---

OFFLINE_KNOWLEDGE_BANK: Dict[str, Tuple[str, str]] = {
    "artificial intelligence": (
        "Artificial Intelligence (AI) refers to the simulation of human intelligence in machines "
        "programmed to think, learn, reason, and solve complex problems. It powers applications ranging "
        "from natural language processing and computer vision to autonomous vehicles and healthcare diagnostics.",
        "Artificial intelligence is the simulation of human intelligence by machines, enabling them to learn, reason, and solve problems."
    ),
    "machine learning": (
        "Machine Learning (ML) is a subfield of artificial intelligence where algorithms learn patterns "
        "from historical data rather than following strictly hardcoded instructions. Key types include "
        "Supervised Learning, Unsupervised Learning, and Reinforcement Learning.",
        "Machine learning is a subset of AI where computers learn from data to make predictions and decisions without being explicitly programmed."
    ),
    "deep learning": (
        "Deep Learning is a specialized branch of machine learning based on multi-layered artificial neural "
        "networks inspired by the human brain. It excels at processing unstructured data such as images, audio, "
        "and human language.",
        "Deep learning is a subset of machine learning using multi-layered neural networks to solve complex pattern recognition tasks."
    ),
    "python": (
        "Python is a high-level, general-purpose, interpreted programming language known for its clean syntax, "
        "readability, and vast ecosystem. It is widely used in artificial intelligence, data science, web development, "
        "and system automation.",
        "Python is a popular, easy-to-read programming language widely used in AI, data science, and web development."
    ),
    "cloud computing": (
        "Cloud Computing is the on-demand delivery of computing services—including servers, storage, databases, "
        "networking, and software—over the internet with pay-as-you-go pricing.",
        "Cloud computing is the delivery of computing services like storage, servers, and software over the internet."
    ),
    "data science": (
        "Data Science is an interdisciplinary field that uses scientific methods, algorithms, and processes "
        "to extract knowledge and actionable insights from structured and unstructured data.",
        "Data science combines statistics, programming, and domain expertise to extract insights from data."
    ),
    "api": (
        "An API (Application Programming Interface) is a set of rules, protocols, and tools that allows different "
        "software applications to communicate and exchange data with each other.",
        "An API is an interface that allows different software applications to communicate with each other."
    ),
}


class AIService:
    """Orchestrates AI question answering and intent understanding."""

    def __init__(self):
        self.provider, self.api_key = get_configured_ai_provider()

    def has_online_ai(self) -> bool:
        """Return True if an online AI API is configured."""
        return self.provider is not None and bool(self.api_key)

    def answer_question(self, user_query: str) -> Tuple[str, str]:
        """Generate response text and a concise spoken summary for any general query.

        Returns:
            (full_display_text: str, spoken_summary: str)
        """
        # If an online AI provider is configured, use it first
        if self.has_online_ai():
            try:
                if self.provider == "gemini":
                    return self._query_gemini(user_query)
                elif self.provider in ("openai", "groq"):
                    return self._query_openai_compatible(user_query)
            except Exception as exc:
                logger.warning("Online AI query failed (%s), falling back to local engine: %s", self.provider, exc)

        # Fallback to smart offline conversational engine
        return self._answer_offline(user_query)

    def _query_gemini(self, user_query: str) -> Tuple[str, str]:
        """Query Google Gemini API via standard REST endpoint."""
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

        system_instruction = (
            "You are a helpful desktop voice assistant. Provide clear, accurate answers. "
            "Keep the first sentence a standalone, concise summary suitable for text-to-speech."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_instruction}\n\nUser Question: {user_query}"}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 400,
                "temperature": 0.7,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=8.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        candidates = body.get("candidates", [])
        if not candidates:
            return "I could not generate an answer at this moment.", "I could not generate an answer."

        parts = candidates[0].get("content", {}).get("parts", [])
        full_text = parts[0].get("text", "").strip() if parts else "No response generated."

        spoken_summary = self._extract_concise_spoken_summary(full_text)
        return full_text, spoken_summary

    def _query_openai_compatible(self, user_query: str) -> Tuple[str, str]:
        """Query OpenAI or Groq compatible API via standard REST endpoint."""
        if self.provider == "groq":
            api_url = "https://api.groq.com/openai/v1/chat/completions"
            model_name = "llama-3.1-8b-instant"
        else:
            api_url = "https://api.openai.com/v1/chat/completions"
            model_name = "gpt-4o-mini"

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful desktop voice assistant. Provide clear, accurate answers. "
                        "Keep the first sentence a concise standalone summary suitable for text-to-speech."
                    ),
                },
                {"role": "user", "content": user_query},
            ],
            "max_tokens": 350,
            "temperature": 0.7,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=8.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        choices = body.get("choices", [])
        if not choices:
            return "I could not generate an answer at this moment.", "I could not generate an answer."

        full_text = choices[0].get("message", {}).get("content", "").strip()
        spoken_summary = self._extract_concise_spoken_summary(full_text)
        return full_text, spoken_summary

    def _extract_concise_spoken_summary(self, full_text: str) -> str:
        """Extract the first 1-2 clean sentences suitable for spoken audio."""
        clean = re.sub(r"[`*#_>\-]", "", full_text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if not sentences:
            return "Here is the answer."
        spoken = " ".join(sentences[:2])
        if len(spoken) > 180:
            spoken = spoken[:175].rsplit(" ", 1)[0] + "..."
        return spoken

    def _answer_offline(self, user_query: str) -> Tuple[str, str]:
        """Offline smart conversational fallback."""
        norm = user_query.strip().lower()

        # 1. Code explanation request
        if "explain this code" in norm or "explain code" in norm or re.search(r"\bdef\s+\w+|\bclass\s+\w+|import\s+\w+|for\s+\w+\s+in", user_query):
            return self._explain_code_offline(user_query)

        # 2. Math calculation
        math_candidate = re.sub(r"^(?:calculate|what is|compute|how much is)\s+", "", norm).strip()
        math_candidate = math_candidate.rstrip("?").strip()
        if any(ch in math_candidate for ch in "+-*/^x") and any(ch.isdigit() for ch in math_candidate):
            res = safe_eval_math_expression(math_candidate)
            if res is not None:
                formatted_res = f"{res:g}" if abs(res) < 1e12 else f"{res:.2e}"
                display = f"The result of {math_candidate} is {formatted_res}."
                spoken = f"The result is {formatted_res}."
                return display, spoken

        # 3. Offline knowledge base lookup
        for topic, (full_info, spoken_info) in OFFLINE_KNOWLEDGE_BANK.items():
            if re.search(rf"\b{re.escape(topic)}\b", norm):
                display = (
                    f"{full_info}\n\n"
                    f"[Offline AI Engine] (Tip: Add GEMINI_API_KEY or OPENAI_API_KEY to your environment for live unrestricted AI answers!)"
                )
                return display, spoken_info

        # 4. Identity & Chit-chat
        if any(g in norm for g in ("who created you", "who made you", "who built you")):
            text = "I was built as a modern Personal Voice Assistant for Windows using Python, CustomTkinter, and intelligent speech automation."
            return text, text

        if any(g in norm for g in ("what is your name", "what's your name", "who are you")):
            text = "I am your Personal Voice Assistant. I can launch applications, search the web, control system volume, take screenshots, manage files, and answer your questions."
            return text, text

        if any(g in norm for g in ("tell me a joke", "make me laugh", "say something funny")):
            joke = "Why do programmers prefer dark mode? Because light attracts bugs!"
            return joke, joke

        if any(g in norm for g in ("thank you", "thanks a lot", "good job", "awesome")):
            reply = "You're very welcome! I'm always here to help you get things done."
            return reply, reply

        # 5. Clarification for ambiguous requests
        clarification_msg = (
            f"I understood your question as: '{user_query}', but I don't have this entry in my offline knowledge bank.\n\n"
            "• If this was meant to be a desktop action, try: 'open notepad', 'take a screenshot', 'play music', or 'search for <topic>'.\n"
            "• To enable unrestricted real-time AI answers for any topic, add a GEMINI_API_KEY or OPENAI_API_KEY to your environment."
        )
        spoken_clarification = "I don't have that in my offline knowledge bank. You can set an AI API key or ask me to search Google for it."
        return clarification_msg, spoken_clarification

    def _explain_code_offline(self, query: str) -> Tuple[str, str]:
        """Provide a structural explanation of code when offline."""
        # Detect syntax constructs
        findings = []
        if re.search(r"\bdef\s+([a-zA-Z_]\w*)", query):
            funcs = re.findall(r"\bdef\s+([a-zA-Z_]\w*)", query)
            findings.append(f"Function definitions: {', '.join(funcs)}")
        if re.search(r"\bclass\s+([a-zA-Z_]\w*)", query):
            classes = re.findall(r"\bclass\s+([a-zA-Z_]\w*)", query)
            findings.append(f"Class definitions: {', '.join(classes)}")
        if re.search(r"\bimport\s+([a-zA-Z_0-9,\s]+)|\bfrom\s+(\w+)\s+import", query):
            findings.append("Imports external modules and libraries for specialized functionality.")
        if re.search(r"\bfor\s+\w+\s+in|\bwhile\s+", query):
            findings.append("Loops that iterate through data collections or execute until a condition is met.")
        if re.search(r"\bif\s+.*:", query):
            findings.append("Conditional branching logic to handle different program states.")
        if re.search(r"\breturn\b", query):
            findings.append("Returns computed values to the caller.")

        if findings:
            explanation = (
                "Here is an overview of the code you provided:\n"
                + "\n".join(f"• {f}" for f in findings)
                + "\n\nThe code defines structured programmatic logic to execute tasks sequentially."
                + "\n\n[Offline AI Engine] (Tip: For line-by-line semantic breakdown, configure GEMINI_API_KEY or OPENAI_API_KEY.)"
            )
            spoken = "Here is an explanation of the code structure and functions."
        else:
            explanation = (
                "Please provide or paste the specific code snippet you would like me to explain (for example: 'explain this code: def add(a, b): return a + b')."
            )
            spoken = "Please provide the code snippet you would like me to explain."

        return explanation, spoken
