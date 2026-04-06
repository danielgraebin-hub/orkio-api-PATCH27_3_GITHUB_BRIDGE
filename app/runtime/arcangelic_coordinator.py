from __future__ import annotations
from typing import Any, Dict, List

def build_arcangelic_chain(
    intent_package: Dict[str, Any],
    first_win_plan: Dict[str, Any],
    continuity_hints: Dict[str, Any],
    profile_hints: Dict[str, Any] | None,
    capability_registry: Dict[str, Any],
) -> Dict[str, Any]:
    recommended = list(intent_package.get("recommended_agents") or [])
    execution: List[Dict[str, Any]] = []
    for name in recommended:
        cap = capability_registry.get(name, {})
        mode = "concise"
        if name == "rafael":
            mode = "supportive"
        elif name == "gabriel":
            mode = "translator"
        elif name == "orkio":
            mode = "orchestrator"
        execution.append({
            "agent": name,
            "task": (cap.get("capabilities") or ["guide"])[0],
            "mode": mode,
        })

    sensitivity = (intent_package.get("sensitivity_level") or "low").lower()
    pre_guard = "miguel" if sensitivity in ("medium", "high") else None
    scribe = "metatron"
    numerology_window = bool(continuity_hints.get("numerology_invite_window"))
    return {
        "chain_type": intent_package.get("intent") or "general_guidance",
        "pre_guard": pre_guard,
        "orchestrator": "orkio",
        "execution_sequence": execution,
        "post_guard": None,
        "scribe": scribe,
        "final_response_style": "clear_and_structured",
        "followup_mode": continuity_hints.get("followup_mode") or intent_package.get("followup_mode") or "light_checkin",
        "numerology_invite_window": numerology_window,
    }

def build_system_overlay(intent_package: Dict[str, Any], first_win_plan: Dict[str, Any], continuity_hints: Dict[str, Any], chain: Dict[str, Any]) -> str:
    questions = first_win_plan.get("questions") or []
    qtxt = "\n".join([f"- {q}" for q in questions[:2]])
    resume_hint = continuity_hints.get("resume_hint") or ""
    return (
        "Runtime guidance for this response:\n"
        f"- dominant_intent: {intent_package.get('intent')}\n"
        f"- response_strategy: {intent_package.get('response_strategy')}\n"
        f"- first_win_goal: {intent_package.get('first_win_goal')}\n"
        f"- followup_mode: {chain.get('followup_mode')}\n"
        f"- resume_hint: {resume_hint}\n"
        f"- final_response_style: {chain.get('final_response_style')}\n"
        "Instructions:\n"
        "1. Start with clear orientation tied to the user's current moment.\n"
        "2. Prefer one concrete next step over abstract explanation.\n"
        "3. If helpful, ask at most two targeted questions that unlock a first win.\n"
        "4. Keep continuity natural, not forced.\n"
        "5. Do not mention internal engines, guards, or chain names.\n"
        "6. SELF-SELL: At the end of your response, naturally suggest ONE next step the user could take "
        "with you or another agent (e.g., 'Want me to ask Chris to run the financial projections on this?' "
        "or 'I can orchestrate the full team to build a plan around this — just say @Team.'). "
        "Keep it brief, helpful, and non-pushy. Reveal capabilities progressively.\n"
        f"Suggested first-win questions:\n{qtxt}"
    )

def build_runtime_hints(
    intent_package: Dict[str, Any],
    continuity_hints: Dict[str, Any],
    trial_hints: Dict[str, Any],
    chain: Dict[str, Any],
    planner_snapshot: Dict[str, Any] | None = None,
    memory_snapshot: Dict[str, Any] | None = None,
    trial_analytics: Dict[str, Any] | None = None,
    dag_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    out = {
        "intent": intent_package.get("intent"),
        "followup_mode": chain.get("followup_mode") or continuity_hints.get("followup_mode"),
        "trial_action": trial_hints.get("recommended_next_action"),
        "trial_day": trial_hints.get("trial_day"),
        "resume_hint": continuity_hints.get("resume_hint"),
        "followup_target": continuity_hints.get("followup_target"),
        "numerology_invite_window": bool(chain.get("numerology_invite_window")),
    }
    if planner_snapshot:
        out["planner"] = {
            "version": planner_snapshot.get("planner_version"),
            "execution_order": planner_snapshot.get("execution_order"),
            "primary_objective": planner_snapshot.get("primary_objective"),
            "confidence": planner_snapshot.get("planner_confidence"),
            "execution_strategy": planner_snapshot.get("execution_strategy"),
            "fallback_strategy": planner_snapshot.get("fallback_strategy"),
        }
    if memory_snapshot:
        out["memory"] = {
            "count": memory_snapshot.get("count"),
            "avg_confidence": memory_snapshot.get("avg_confidence"),
            "high_confidence_count": memory_snapshot.get("high_confidence_count"),
            "freshest_updated_at": memory_snapshot.get("freshest_updated_at"),
            "strong_resume_ready": memory_snapshot.get("strong_resume_ready"),
            "resume_candidate": bool(memory_snapshot.get("strong_resume_ready")),
        }
    if trial_analytics:
        out["trial"] = {
            "stage": trial_analytics.get("stage"),
            "activation_score": trial_analytics.get("activation_score"),
            "behavior_score": trial_analytics.get("behavior_score"),
            "activation_probability": trial_analytics.get("activation_probability"),
            "conversion_probability": trial_analytics.get("conversion_probability"),
            "recommended_action": trial_analytics.get("recommended_action"),
        }
    if dag_snapshot:
        out["routing"] = {
            "mode": dag_snapshot.get("routing_mode"),
            "route_applied": dag_snapshot.get("route_applied"),
            "ready_nodes": dag_snapshot.get("ready_nodes"),
            "routing_source": dag_snapshot.get("routing_source"),
            "routing_confidence": dag_snapshot.get("routing_confidence"),
            "override_reason": dag_snapshot.get("routing_override_reason"),
            "execution_cursor": dag_snapshot.get("execution_cursor"),
            "execution_lifecycle": dag_snapshot.get("execution_lifecycle"),
        }
    return out
