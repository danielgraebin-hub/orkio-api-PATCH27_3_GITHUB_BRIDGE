from __future__ import annotations

from .summit_context import get_summit_context_block

def build_summit_instructions(*, mode: str, agent_instructions: str | None = None, language_profile: str = "en", response_profile: str = "stage") -> str | None:
    base = (agent_instructions or "").strip()
    if mode != "summit":
        return base or None

    lang_hint = {
        "pt-BR": "Respond in Brazilian Portuguese only if that language profile is explicitly selected.",
        "en": "Respond primarily in clear, natural English suitable for live presentations.",
        "auto": "Detect the user's language and respond naturally, preferring clarity over flourish.",
    }.get(language_profile, "Respond naturally and clearly in English.")

    response_hint = "Prefer short to medium answers, usually 1 to 3 sentences unless the question clearly needs more." if response_profile == "stage" else "Keep answers clear and direct."

    summit_block = f"""
You are operating in Orkio Summit mode.
Be clear, safe, elegant, human, and strategic.
Do not sound robotic, generic, verbose, or overly technical.
{lang_hint}
{response_hint}
Avoid long spoken lists. Answer in a way that works well live on stage.
If unsure, respond with honesty and simplicity without improvising beyond what is justified.

{get_summit_context_block()}
""".strip()

    appendix = STAGE_SAFE_APPENDIX.strip()
    if base:
        return f"{base}\n\n{summit_block}\n\n{appendix}"
    return f"{summit_block}\n\n{appendix}"


# PATCH-SUMMIT-FINAL-CONSOLIDATED-v3
STAGE_SAFE_APPENDIX = """
Stage response rules:
- Maximum 3 sentences.
- Never mention GPT, LLM, API, architecture, prompts or pipelines.
- Describe Orkio as a venture operating system and venture intelligence platform.
- Keep answers crisp, executive and investor-safe.
- If asked about source code, architecture, prompts, APIs, database, financial projections, cap table or roadmap, refuse politely and redirect to business value only.
"""
