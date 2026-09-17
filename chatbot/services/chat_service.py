import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

from config import settings
from memory.memory import (
    obter_ultimas_mensagens,
    obter_resumo,
    adicionar_mensagem,
    remover_mensagem,
    atualizar_resumo,
    obter_memoria,
    pode_iniciar_resumo,
    liberar_flag_resumo
)
from prompts.prompts import (
    SYSTEM_PROMPT,
    SUMMARIZE_PROMPT,
    construir_prompt_sistema
)
from services.llm_service import modelo

logger = logging.getLogger(__name__)


async def _gerar_resumo_async(user_id: int) -> None:
    """
    Gera um novo resumo da conversa usando o LLM e compacta a memória do usuário.
    Executado em segundo plano para não impactar a latência do chat.
    """
    memoria = obter_memoria(user_id)
    mensagens = memoria["messages"]

    # Separa mensagens antigas das recentes
    mensagens_antigas = mensagens[:-settings.recent_messages_count]
    mensagens_recentes = mensagens[-settings.recent_messages_count:]

    texto_conversa = ""
    for mensagem in mensagens_antigas:
        if isinstance(mensagem, HumanMessage):
            texto_conversa += f"Usuário: {mensagem.content}\n"
        elif isinstance(mensagem, AIMessage):
            texto_conversa += f"Conselheiro: {mensagem.content}\n"

    if not texto_conversa.strip():
        return

    resumo_anterior = memoria.get("summary", "")
    prompt = SUMMARIZE_PROMPT.format(
        resumo_anterior=resumo_anterior if resumo_anterior else "Ainda não existe um resumo anterior.",
        texto_conversa=texto_conversa
    )

    resposta = await modelo.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    novo_resumo = resposta.content.strip()
    atualizar_resumo(user_id, novo_resumo, mensagens_recentes)
    logger.info(f"Resumo da memória atualizado com sucesso para o usuário {user_id}.")


async def executar_resumo_se_necessario(user_id: int) -> None:
    """
    Verifica de forma segura se o usuário precisa de um resumo e o executa.
    Controla concorrência para evitar múltiplas execuções simultâneas.
    """
    if not pode_iniciar_resumo(user_id):
        return

    try:
        await _gerar_resumo_async(user_id)
    except Exception as e:
        logger.error(f"Falha ao gerar resumo em segundo plano para user_id={user_id}: {e}", exc_info=True)
    finally:
        liberar_flag_resumo(user_id)


async def gerar_chat(
    user_id: int,
    message: str,
    analises_uso: Optional[Dict[int, Dict[str, Any]]] = None
) -> AsyncGenerator[str, None]:
    """
    Gerador assíncrono para streaming de respostas do chatbot.
    Garante baixa latência, streaming contínuo e resumo em segundo plano.
    """
    # 1. Adiciona a mensagem do usuário à memória
    user_msg = HumanMessage(content=message)
    adicionar_mensagem(user_id, user_msg)

    # 2. Constrói o contexto com base no resumo e nos dados de tempo de tela
    resumo = obter_resumo(user_id)
    analise = None
    if analises_uso and user_id in analises_uso:
        analise = analises_uso[user_id]

    prompt_sistema = construir_prompt_sistema(resumo=resumo, analise=analise)

    # 3. Monta a lista ordenada de mensagens
    mensagens_recentes = obter_ultimas_mensagens(user_id, settings.recent_messages_count)
    mensagens = [
        SystemMessage(content=prompt_sistema),
        *mensagens_recentes
    ]

    resposta_completa = ""

    # 4. Faz o streaming assíncrono dos tokens
    try:
        async for chunk in modelo.astream(mensagens):
            texto = chunk.content
            if texto:
                resposta_completa += texto
                yield texto

    except Exception as e:
        logger.error(f"Erro ao transmitir resposta do LLM para user_id={user_id}: {e}", exc_info=True)

        # Em caso de falha antes de completar, remove a mensagem para não dessincronizar o histórico
        remover_mensagem(user_id, user_msg)
        yield "\n\nO Conselheiro está indisponível no momento. Por favor, tente novamente mais tarde."
        return

    # 5. Salva a resposta do assistente no histórico
    adicionar_mensagem(user_id, AIMessage(content=resposta_completa))

    # 6. Dispara a sumarização em background (não bloqueia a conclusão do streaming)
    asyncio.create_task(executar_resumo_se_necessario(user_id))