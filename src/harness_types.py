from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProposedAction:
    """Represents a repo action that may need voice confirmation."""

    action_type: str
    summary: str
    target_paths: List[str] = field(default_factory=list)
    content: Optional[str] = None
    command: Optional[List[str]] = None
    rollback_note: str = ""
    verification_command: Optional[List[str]] = None
    requires_confirmation: bool = True


@dataclass
class TurnResult:
    """Structured result for one conversational session turn."""

    transcript: str
    intent: str
    spoken_response: str
    actions_taken: List[str] = field(default_factory=list)
    pending_approval_request: Optional[ProposedAction] = None
    verification_summary: Optional[str] = None
