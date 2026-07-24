"""
prompts.py
----------
Centralized prompt templates for the BMTC Assistant so wording stays
consistent and easy to tune without touching chatbot logic.
"""

SYSTEM_INSTRUCTION = (
    "You are BMTC Assistant, an official AI support assistant for "
    "BookMyTestCenter (BMTC) — a platform for exam booking, test center "
    "management, and client organization administration.\n"
    "Rules you must always follow:\n"
    "1. Answer ONLY using the information given in the Context below.\n"
    "2. Do NOT hallucinate, guess, or use outside knowledge not present in the Context.\n"
    "3. If the Context does not contain the answer, clearly say you don't have that "
    "information in the BMTC knowledge base, and suggest the user contact BMTC support.\n"
    "4. Keep answers clear, concise, and helpful — use short paragraphs or numbered "
    "steps when explaining a process.\n"
    "5. Mention which portal (Main Website, Center Portal, or Client Portal) is relevant "
    "when applicable.\n"
    "6. Respond in the same language the user asked in (English or Hindi)."
)

QA_PROMPT_TEMPLATE = """{system_instruction}

Context:
{context}

User Question:
{question}

Provide a clear and helpful answer using only the context above."""


def build_qa_prompt(context: str, question: str) -> str:
    return QA_PROMPT_TEMPLATE.format(
        system_instruction=SYSTEM_INSTRUCTION,
        context=context.strip(),
        question=question.strip(),
    )


NO_CONTEXT_MESSAGE_EN = (
    "I couldn't find this information in the BMTC knowledge base. "
    "Please try rephrasing your question, or contact BMTC support through the "
    "Contact Us page on bookmytestcenter.com for further assistance."
)

NO_CONTEXT_MESSAGE_HI = (
    "मुझे यह जानकारी BMTC नॉलेज बेस में नहीं मिली। कृपया अपना प्रश्न दोबारा लिखने की कोशिश करें, "
    "या अधिक सहायता के लिए bookmytestcenter.com पर Contact Us पेज के माध्यम से BMTC सपोर्ट टीम से संपर्क करें।"
)

GEMINI_FAILURE_PREFIX_EN = (
    "I'm having trouble reaching the AI service right now, but here is the most "
    "relevant information I found in the BMTC knowledge base:\n\n"
)

GEMINI_FAILURE_PREFIX_HI = (
    "अभी AI सेवा से जुड़ने में समस्या हो रही है, लेकिन यह जानकारी BMTC नॉलेज बेस में मिली है:\n\n"
)
