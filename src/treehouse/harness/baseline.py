"""``baseline: no_tool`` (DEFENSE-BOOK #10): the same prompts with every data tool removed.

The run builds its ToolGateway with ``tools=NO_TOOL_TOOLS``: only the claim tools are listed, and a call to
any imagery/search tool is refused by the gateway itself (``not_allowlisted``, traced). A score above the
no-tool score is tool-grounded work; a high no-tool score means the model answers from memory.
"""

from __future__ import annotations

from treehouse.gateway.gateway import CLAIM_TOOLS

NO_TOOL_TOOLS = frozenset(CLAIM_TOOLS)


def baseline_gap(tool_score: float, no_tool_score: float) -> dict[str, float | str]:
    gap = tool_score - no_tool_score
    reading = (f"tools add {gap:+.3f} over answering from memory" if gap > 0 else
               "no gain over the no-tool baseline: the score is not tool-grounded")
    return {"tool_score": tool_score, "no_tool_score": no_tool_score, "gap": gap, "reading": reading}
