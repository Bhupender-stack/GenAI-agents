
from __future__ import annotations
from typing import Any, Dict

# ------------------------------------------------------------------
# ✅ Import agent logics from app source (NOT volume)
# ------------------------------------------------------------------
from agents.schema_compare.schema_compare_logic import run_schema_compare
from agents.schema_gap_analysis.schema_gap_logic import run_schema_gap_analysis


class ExecutionHandler:
    """
    Executes deterministic (non-agentic) agents.
    Supports:
      - schema_compare        (legacy, manual Excel only)
      - schema_gap_analysis   (new, manual + database)
    """

    def __init__(self, config_loader, base_dir=None):
        self.config_loader = config_loader
        self.base_dir = base_dir

    def run_non_agentic(
        self,
        agent_id: str,
        metadata: Dict[str, Any],
        user_context: str = ""
    ) -> Dict[str, Any]:

        agent_id = agent_id.lower()

        # =============================================================
        # ✅ LEGACY AGENT: schema_compare (DO NOT BREAK)
        # =============================================================
        if agent_id == "schema_compare":

            base_path = metadata.get(
                "base_path",
                "/Volumes/schema_compare_input/schema_gap_analysis/schema_compare"
            )

            # Returns: { file_name, file_bytes }
            result = run_schema_compare(base_path)

            return {
                "output": "Schema Compare completed successfully",
                "download": result
            }

        # =============================================================
        # ✅ NEW AGENT: schema_gap_analysis (MANUAL + DATABASE)
        # =============================================================
        elif agent_id == "schema_gap_analysis":

            # Metadata already contains:
            # mode: manual | database
            # + corresponding inputs
            #
            # Returns: { file_name, file_bytes }
            result = run_schema_gap_analysis(metadata)

            return {
                "output": "Schema Gap Analysis completed successfully",
                "download": result
            }

        # =============================================================
        # ❌ Unsupported agent
        # =============================================================
        else:
            raise ValueError(f"Unsupported non-agentic agent: {agent_id}")
