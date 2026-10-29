import uuid
from typing import Dict, List, Optional, Any
from app.conversation.constraint_tracker import ActiveConstraints

class ConversationSession:
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.history: List[Dict[str, Any]] = []
        self.constraints = ActiveConstraints()

    def add_turn(self, user_message: str, response_data: Dict[str, Any]) -> None:
        self.history.append({
            "user": user_message,
            "assistant": response_data.get("response_text"),
            "decision": response_data.get("decision")
        })
        # Keep recent 20 turns
        if len(self.history) > 20:
            self.history = self.history[-20:]

class ContextManager:
    """Manages multi-turn conversation sessions in-memory."""

    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, conversation_id: Optional[str] = None) -> ConversationSession:
        if not conversation_id or conversation_id.strip() == "":
            cid = str(uuid.uuid4())
            session = ConversationSession(cid)
            self.sessions[cid] = session
            return session

        cid = conversation_id.strip()
        if cid not in self.sessions:
            self.sessions[cid] = ConversationSession(cid)
        return self.sessions[cid]

    def reset_session(self, conversation_id: str) -> None:
        if conversation_id in self.sessions:
            del self.sessions[conversation_id]

context_manager = ContextManager()
