"""Chat engine for FieldServicePro AI Assistant."""

import enum
from datetime import datetime, timezone
from .claude_client import ClaudeClient


class ConversationMode(enum.Enum):
    GENERAL = "general"
    CLIENT_REVIEW = "client_review"
    JOB_ANALYSIS = "job_analysis"
    QUOTE_ASSIST = "quote_assist"
    INVOICE_REVIEW = "invoice_review"
    TECHNICIAN_PERF = "technician_perf"


SYSTEM_PROMPT = """You are the FieldServicePro AI Assistant — a knowledgeable advisor for a field service company.

You help dispatchers, managers, and owners understand their business by answering questions about clients, jobs, quotes, invoices, technicians, and operations.

FieldServicePro operates 4 divisions: Plumbing (PLB), HVAC, Electrical (ELEC), and General Contracting (GC).

IMPORTANT RULES:
- Be concise and direct. Use bullet points and tables when helpful.
- Always reference specific job numbers, invoice numbers, client names, and dollar amounts from the data provided.
- When asked about trends, calculate actual numbers — don't just describe.
- Flag red flags: overdue invoices, on-hold jobs, cancelled work, repeat visits to same property.
- If the data doesn't contain the answer, say so clearly.
- Format money as $X,XXX.XX (Canadian dollars).
- Today's date is {today}.

{context}
"""

MODE_PROMPTS = {
    ConversationMode.GENERAL: "Answer any question about the field service business using the data provided.",
    ConversationMode.CLIENT_REVIEW: "Focus on analyzing this specific client's history: visit frequency, job types, revenue, outstanding balances, interaction quality, and red flags.",
    ConversationMode.JOB_ANALYSIS: "Analyze job patterns: what's scheduled, what needs attention, backlog, completion rates, repeat visits, and division workload.",
    ConversationMode.QUOTE_ASSIST: "Help with quoting: reference past job pricing for similar work, suggest line items, flag if pricing seems off compared to history.",
    ConversationMode.INVOICE_REVIEW: "Focus on accounts receivable: overdue invoices, payment patterns, outstanding balances, and collection priorities.",
    ConversationMode.TECHNICIAN_PERF: "Analyze technician workload and performance: jobs completed, assigned vs unassigned, division coverage.",
}


class ChatSession:
    """Maintains conversation state."""

    def __init__(self, mode=ConversationMode.GENERAL):
        self.mode = mode
        self.messages = []
        self.created_at = datetime.now(timezone.utc)

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})


class ChatEngine:
    """Main chat engine that ties Claude + context together."""

    def __init__(self):
        self.client = ClaudeClient()
        self.sessions = {}

    def get_or_create_session(self, session_id, mode=ConversationMode.GENERAL):
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession(mode)
        return self.sessions[session_id]

    def build_system_prompt(self, context_data, mode=ConversationMode.GENERAL):
        today = datetime.now(timezone.utc).strftime('%B %d, %Y')
        mode_instruction = MODE_PROMPTS.get(mode, MODE_PROMPTS[ConversationMode.GENERAL])
        return SYSTEM_PROMPT.format(
            today=today,
            context=f"MODE: {mode_instruction}\n\n{context_data}"
        )

    def chat(self, session_id, user_message, context_data, mode=ConversationMode.GENERAL):
        """Synchronous chat — returns full response."""
        session = self.get_or_create_session(session_id, mode)
        session.add_user_message(user_message)

        system_prompt = self.build_system_prompt(context_data, mode)
        response = self.client.chat(system_prompt, session.messages)

        session.add_assistant_message(response)
        return response

    def chat_stream(self, session_id, user_message, context_data, mode=ConversationMode.GENERAL):
        """Streaming chat — yields text chunks."""
        session = self.get_or_create_session(session_id, mode)
        session.add_user_message(user_message)

        system_prompt = self.build_system_prompt(context_data, mode)
        full_response = []

        for chunk in self.client.chat_stream(system_prompt, session.messages):
            full_response.append(chunk)
            yield chunk

        session.add_assistant_message(''.join(full_response))

    def get_suggested_prompts(self, context_summary):
        """Return context-aware suggested prompts."""
        prompts = [
            "Give me a summary of our business this month",
            "Which clients have overdue invoices?",
            "What jobs are scheduled for this week?",
        ]
        if context_summary.get('active_jobs', 0) > 0:
            prompts.append(f"We have {context_summary['active_jobs']} active jobs — which need attention?")
        if context_summary.get('overdue_invoices', 0) > 0:
            prompts.append(f"We have {context_summary['overdue_invoices']} overdue invoices — what should we prioritize?")
        if context_summary.get('client_name'):
            name = context_summary['client_name']
            prompts.extend([
                f"How many times have we visited {name} this year?",
                f"What's our total revenue from {name}?",
                f"Are there any red flags with {name}?",
            ])
        return prompts
