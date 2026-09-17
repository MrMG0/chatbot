import logging
from langchain_openai import ChatOpenAI
from config import settings

logger = logging.getLogger(__name__)


def get_llm_model() -> ChatOpenAI:
    """
    Inicializa o cliente do modelo de linguagem usando as configurações centralizadas.
    Suporta LM Studio, Ollama, OpenAI ou qualquer servidor compatível com a API OpenAI.
    """
    logger.info(
        f"Inicializando LLM: model={settings.llm_model}, "
        f"base_url={settings.llm_base_url}, temp={settings.llm_temperature}"
    )
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )


# Instância compartilhada do modelo
modelo = get_llm_model()
