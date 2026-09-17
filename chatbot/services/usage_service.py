import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException
from langchain_core.messages import SystemMessage, HumanMessage

from prompts.prompts import SYSTEM_PROMPT, ANALYZE_USAGE_PROMPT
from services.llm_service import modelo

logger = logging.getLogger(__name__)

# Armazenamento temporário das últimas análises de uso por usuário
analises_uso: Dict[int, Dict[str, Any]] = {}


def obter_analise_uso(user_id: int) -> Optional[Dict[str, Any]]:
    """Recupera a última análise de uso registrada para um usuário."""
    return analises_uso.get(user_id)


async def analisar_uso(user_id: int, screen_time: int, goal: int) -> Dict[str, Any]:
    """
    Analisa os dados de uso de tela do usuário de forma assíncrona,
    gerando uma recomendação acolhedora e personalizada via IA.
    """
    difference = screen_time - goal

    if difference > 0:
        above_goal = True
        status = "acima da meta"
    elif difference < 0:
        above_goal = False
        status = "abaixo da meta"
    else:
        above_goal = False
        status = "exatamente na meta"

    prompt = ANALYZE_USAGE_PROMPT.format(
        screen_time=screen_time,
        goal=goal,
        difference=abs(difference),
        status=status
    )

    try:
        resposta = await modelo.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
    except Exception as e:
        logger.error(f"Erro ao chamar o modelo em analisar_uso para user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Não foi possível realizar a análise no momento. Verifique se o provedor de IA está em execução."
        )

    analise = {
        "above_goal": above_goal,
        "difference": difference,
        "screen_time": screen_time,
        "goal": goal,
        "recommendation": resposta.content
    }

    analises_uso[user_id] = analise
    return analise