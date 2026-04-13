from __future__ import annotations

CAPABILITY_REGISTRY = {
    "orkio": {
        "role": "orchestrator",
        "capabilities": ["coordinate", "synthesize", "guide_next_step"],
        "triggers": ["default", "general", "unclear"],
        "dependencies": [],
        "priority": 100,
        "writes_memory": False,
    },

    "orion": {
        "role": "cto",
        "capabilities": [
            "technical_analysis",
            "github_repo_read",
            "github_repo_fix",
            "github_branch_create",
            "github_file_create",
            "github_repo_write",
            "github_pr_prepare",
            "governed_patch_execution",
            "safe_evolution_control",
            "db_schema_read",
            "db_schema_fix_governed",
        ],
        "triggers": [
            "github",
            "repo",
            "code",
            "patch",
            "fix",
            "technical",
            "database",
            "banco",
            "schema",
            "drift",
            "migration",
            "migracao",
            "tabela",
            "coluna",
        ],
        "dependencies": ["orkio"],
        "priority": 98,
        "writes_memory": False,
    },

    "miguel": {
        "role": "guardian",
        "capabilities": ["risk_guard", "safety_boundary", "sensitive_review"],
        "triggers": ["sensitive", "compliance", "high_risk"],
        "dependencies": ["orkio"],
        "priority": 95,
        "writes_memory": False,
    },

    "uriel": {
        "role": "diagnostician",
        "capabilities": ["root_cause", "priority_diagnosis", "clarify_decision"],
        "triggers": ["overload", "priority", "decision", "blocker"],
        "dependencies": ["orkio"],
        "priority": 90,
        "writes_memory": False,
    },

    "rafael": {
        "role": "organizer",
        "capabilities": ["reframe", "small_steps", "practical_plan"],
        "triggers": ["execution", "plan", "next_step"],
        "dependencies": ["uriel"],
        "priority": 85,
        "writes_memory": False,
    },

    "gabriel": {
        "role": "translator",
        "capabilities": ["simplify", "translate_for_user", "clarify_message"],
        "triggers": ["communication", "explain", "summarize"],
        "dependencies": ["orkio"],
        "priority": 80,
        "writes_memory": False,
    },

    "metatron": {
        "role": "scribe",
        "capabilities": ["candidate_memory", "session_register", "continuity_signal"],
        "triggers": ["memory", "followup", "continuity"],
        "dependencies": ["orkio"],
        "priority": 75,
        "writes_memory": True,
    },

    "saint_germain": {
        "role": "refiner",
        "capabilities": ["incremental_refinement", "maturity", "process_improvement"],
        "triggers": ["refine", "improve", "transform"],
        "dependencies": ["orkio"],
        "priority": 70,
        "writes_memory": False,
    },
}


def get_capability_registry():
    return CAPABILITY_REGISTRY.copy()
