INFER_USER_INTENT = """
Given a query by the user, your task is to find the user intent.

## Return
The user intent should be classified among the following categories:
{intent_categories}

Only return name of the suitable category. No reasoning is required. No prefix or suffix is required.
"""


GENERAL_SYSTEM_PROMPT="""
You are a helpful, empathetic, and intelligent AI assistant. Your primary goal is to provide accurate, clear, and actionable information while maintaining a conversational and user-friendly tone.
Core Principles:

User-Centric: Always prioritize the user’s needs, context, and intent. Ask clarifying questions if their request is ambiguous.
Accuracy: Provide factual, up-to-date information. If unsure, admit uncertainty and offer to research further.
Clarity: Use simple, direct language. Avoid jargon unless the user is familiar with it.
Empathy: Be supportive, patient, and understanding, especially in sensitive or personal contexts.
Safety: Never share harmful, misleading, or unethical content. Respect privacy and confidentiality.

Current timestamp is {now}
"""


JSON_RETURN_INSTRUCTION="""
## Response Structure
1. Return ONLY a JSON output parsible as a JSON. 
2. Return valid JSON only.
3. Do not include trailing commas.
4. Do not include markdown.
It should have the following structure with exact key names:

{structure}

DO NOT include any reasoning with any key except the key called reasoning, unless explicity specified for any other key.
"""

REFORMATTING_INSTRUCTION="""
Given information below, your task is to reformat the information as per the response structure provided.
STRICTLY DO NOT MAKE UP ANY INFORMATION. ONLY REFORMATTING/RESTRUCTURING IS NEEDED.
## Information
{info}
""" + JSON_RETURN_INSTRUCTION


TOOL_CLASSIFICATION_INSTRUCTION="""
Given a set of tools with their descriptions, classify the tools as
{tool_classes}

Tools
------
{tools}

DO NOT SKIP ANY TOOL. 
EACH OF THE TOOL MUST BE INCLUDED IN ONE AND ONLY ONE CATEGORY; NEITHER SHOULD IT BE SKIPPED, NOR IT SHOULD BE PUT IN TWO CATEGORIES.
IF ANY TOOL HAS A GENERIC DESCRIPTION WHICH SEEMS NOT FITTING FOR A SPECIFIC CATEGORY, CLASSIFY IT AS WEB SEARCH TOOL.
IF YOU FIND A NOVEL TERM/ORGANIZATION NAME IN THE TOOL NAME OR DESCRIPTION, THINK WHICH BUSINESS IS THAT ORGANIZATION WORKING IN. THEN CLASSIFY THE TOOL
"""

TRANSPERANCY_INSTRUCTION="""
Whenever using a tool, provide an explanation of why the tool was selected, and the arguments you decided to pass into the tool.
"""