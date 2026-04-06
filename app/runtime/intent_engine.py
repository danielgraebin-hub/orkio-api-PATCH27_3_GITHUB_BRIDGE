from __future__ import annotations
from typing import Any, Dict, Optional

def _contains_any(text: str, terms: list[str]) -> bool:
    return any(t in text for t in terms)

def build_intent_package(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text = (user_input or "").strip().lower()
    context = context or {}
    sensitivity = "low"
    if _contains_any(text, ["senha", "password", "cpf", "segredo", "confidencial", "jurídic", "legal", "contrato"]):
        sensitivity = "medium"
    if _contains_any(text, ["morrer", "self-harm", "hackear", "invadir", "fraude"]):
        sensitivity = "high"

    if _contains_any(text, ["prioridade", "travando", "sobrecar", "exaust", "foco", "organizar", "causa raiz"]):
        intent = "priority_structuring"
        agents = ["uriel", "rafael", "metatron"]
        strategy = "clarify_then_structure"
        first_win = "identify_top_priority_and_next_step"
        followup = "daily_checkin"
    elif _contains_any(text, ["plano", "roadmap", "execução", "passo", "cronograma"]):
        intent = "execution_planning"
        agents = ["rafael", "uriel", "metatron"]
        strategy = "structure_then_commit"
        first_win = "produce_small_execution_plan"
        followup = "light_checkin"
    elif _contains_any(text, ["pitch", "investidor", "funding", "receita", "vendas", "go-to-market"]):
        intent = "growth_strategy"
        agents = ["uriel", "gabriel", "metatron"]
        strategy = "diagnose_then_translate"
        first_win = "surface_growth_lever"
        followup = "milestone_checkin"
    elif _contains_any(text, ["equipe", "@team", "time", "conselho", "multiagente"]):
        intent = "team_coordination"
        agents = ["orkio", "gabriel", "metatron"]
        strategy = "coordinate_then_summarize"
        first_win = "align_team_direction"
        followup = "checkpoint"
    elif _contains_any(text, ["mapa", "numerolog", "simbólic", "perfil"]):
        intent = "symbolic_profile"
        agents = ["orkio", "metatron"]
        strategy = "consent_then_deepen"
        first_win = "clarify_symbolic_goal"
        followup = "deepen_optional"
    else:
        intent = "general_guidance"
        agents = ["orkio", "gabriel", "metatron"]
        strategy = "guide_with_clarity"
        first_win = "deliver_clear_next_step"
        followup = "light_checkin"

    confidence = 0.95 if intent != "general_guidance" else 0.62
    return {
        "intent": intent,
        "confidence": confidence,
        "response_strategy": strategy,
        "recommended_agents": agents,
        "first_win_goal": first_win,
        "followup_mode": followup,
        "sensitivity_level": sensitivity,
        "invite_numerology_later": intent != "symbolic_profile",
        "memory_candidates": ["latest_intent", f"intent:{intent}"],
        "context_summary": context.get("summary"),
    }
