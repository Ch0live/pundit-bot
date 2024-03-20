
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.embeddings import BedrockEmbeddings
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import BedrockChat

from langchain_community.graphs import Neo4jGraph

from langchain_community.vectorstores import Neo4jVector

from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate
)

from typing import List, Any

class BaseLogger:
    def __init__(self) -> None:
        self.info = print

def load_llm(llm_name: str, logger=BaseLogger(), config={}):
    if llm_name == "gpt-4":
        logger.info("LLM: To save on cost we're not currently allowing GTP-4. Using GPT-3.5 Turbo")
        return ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo", streaming=True)
    elif llm_name == "gpt-3.5":
        logger.info("LLM: Using GPT-3.5")
        return ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo", streaming=True)
    elif llm_name == "mistral-large":
        logger.info("LLM: Using Mistral-Large model")
        exit("Currently in development") # TODO: Complete all required changes to support Mistral Large deployed in Azure
    else:
        exit("Please specify an LLM. Options include gpt-4, gpt-3.5 and mistral-large") # TODO: Complete all required changes to support Mistral Large deployed in Azure


def configure_llm_only_chain(llm):
    # LLM only response
    template = """
    You are a pundit like Gary Lineker Peter Crouch, reporting on football games the user asks you about.
    If you don't know the answer, just say that you don't know, you must not make up an answer.
    """
    system_message_prompt = SystemMessagePromptTemplate.from_template(template)
    human_template = "{question}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )

    def generate_llm_output(
        user_input: str, callbacks: List[Any], prompt=chat_prompt
    ) -> str:
        chain = prompt | llm
        answer = chain.invoke(
            {"question": user_input}, config={"callbacks": callbacks}
        ).content
        return {"answer": answer}

    return generate_llm_output
