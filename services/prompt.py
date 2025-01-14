# prompt.py
from langchain_core.prompts import PromptTemplate

def get_default_prompt_template():
    """기본 프롬프트 템플릿을 반환"""
    return PromptTemplate.from_template(
        """
        {{instruction}}

        # Previous Chat History:
        {chat_history}

        # Question: 
        {question} 

        # Context: 
        {context} 

        # Answer:
        """
    )
