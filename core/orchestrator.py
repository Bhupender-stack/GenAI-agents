# =============================================================================
# core/orchestrator.py
# Central execution engine.
#
# • Non-agentic agents (e.g. schema_compare, schema_gap_analysis)
#     → ExecutionHandler
# • Agentic agents → LLM pipeline
# =============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from core.config_loader import ConfigLoader
from core.llm_client import LLMClient
from core.token_optimizer import TokenOptimizer
from core.knowledge_manager import KnowledgeManager
from core.rule_injector import RuleInjector
from core.prompt_builder import PromptBuilder
from core.execution_handler import ExecutionHandler
from core.run_logger import RunLogger
from core.agent_result import AgentResult

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main execution router.
    """

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or Path(__file__).resolve().parent.parent
        self.cfg = ConfigLoader(base_dir=self._base)

        # ---------------------------------------------------------------------
        # LLM stack (used ONLY for agentic agents)
        # ---------------------------------------------------------------------
        self.llm = LLMClient(self.cfg)
        self.to = TokenOptimizer(self.cfg)
        self.km = KnowledgeManager(self.cfg, base_dir=self._base)
        self.ri = RuleInjector(base_dir=self._base)
        self.pb = PromptBuilder(
            self.cfg, self.to, self.km, self.ri, base_dir=self._base
        )

        # ---------------------------------------------------------------------
        # Deterministic executor (non-agentic agents)
        # ---------------------------------------------------------------------
        self.exec_h = ExecutionHandler(self.cfg, base_dir=self._base)

        self.log = RunLogger.get()
        self._cache: Dict[str, AgentResult] = {}

    # -------------------------------------------------------------------------
    # Agent listing (used by UI catalog)
    # -------------------------------------------------------------------------
    def list_agents(self, **filters) -> list:
        return self.cfg.list_agents(**filters)

    # -------------------------------------------------------------------------
    # Main run API
    # -------------------------------------------------------------------------
    def run(
        self,
        agent_id: str,
        metadata: Dict[str, Any] | List[Dict[str, Any]],
        user_context: str = "",
        task_override: str = "",
        use_cache: bool = True,
    ) -> AgentResult:

        run_id = self._make_run_id(agent_id)
        start = time.perf_counter()

        # Normalize metadata (always list internally)
        if isinstance(metadata, dict):
            metadata = [metadata]

        try:
            agent_cfg = self.cfg.get_agent_config(agent_id)
            agent_type = agent_cfg.get("agent", {}).get("type", "agentic")

            # ===============================================================
            # ✅ NON‑AGENTIC PATH (FIXED & EXTENDED)
            # ===============================================================
            if agent_type == "non_agentic":

                result_dict = self.exec_h.run_non_agentic(
                    agent_id=agent_id,
                    metadata=metadata[0],
                    user_context=user_context,
                )

                duration = time.perf_counter() - start

                # ✅ IMPORTANT:
                # Pass FULL result_dict to UI (including download bytes)
                return AgentResult(
                    agent_id=agent_id,
                    status="success",
                    output=result_dict,   # ✅ NOT just a string
                    duration_seconds=round(duration, 3),
                    run_id=run_id,
                    log_entries=self.log.get_entries(run_id),
                )

            # ===============================================================
            # AGENTIC PATH (OLD CODE — RETAINED)
            # ===============================================================
            cache_enabled = use_cache and self.cfg.token_config.get(
                "cache_enabled", True
            )

            cache_key = self._cache_key(agent_id, metadata, user_context)

            if cache_enabled and cache_key in self._cache:
                cached = self._cache[cache_key]
                cached.run_id = run_id
                cached.log_entries = self.log.get_entries(run_id)
                return cached

            optimized = self.to.optimize_metadata_list(metadata)

            system_prompt, user_prompt = self.pb.build(
                agent_id=agent_id,
                agent_config=agent_cfg,
                metadata=optimized,
                user_context=user_context,
                task_override=task_override,
            )

            llm_response = self.llm.complete(
                prompt=user_prompt,
                system=system_prompt,
                agent_id=agent_id,
            )

            duration = time.perf_counter() - start

            result = AgentResult(
                agent_id=agent_id,
                status="success",
                output=llm_response.text,
                token_usage=llm_response.token_usage,
                cost_usd=llm_response.cost_estimate_usd,
                duration_seconds=round(duration, 3),
                run_id=run_id,
                log_entries=self.log.get_entries(run_id),
            )

            if cache_enabled:
                self._cache[cache_key] = result

            return result

        except Exception as exc:
            duration = time.perf_counter() - start
            logger.exception(f"Agent '{agent_id}' failed")

            return AgentResult(
                agent_id=agent_id,
                status="error",
                output="",
                error=str(exc),
                duration_seconds=round(duration, 3),
                run_id=run_id,
                log_entries=self.log.get_entries(run_id),
            )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _make_run_id(self, agent_id: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{agent_id}_{ts}"

    def _cache_key(
        self,
        agent_id: str,
        metadata: List[Dict[str, Any]],
        context: str,
    ) -> str:
        payload = json.dumps(
            {"agent": agent_id, "meta": metadata, "ctx": context},
            sort_keys=True,
            default=str,
        )
        return hashlib.md5(payload.encode()).hexdigest()
