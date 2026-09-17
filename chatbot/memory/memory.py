import time
import threading
from typing import Dict, Any, List
from langchain_core.messages import BaseMessage
from config import settings

# Estrutura de memória em memória com lock reentrante (RLock) para thread-safety
_lock = threading.RLock()
memorias: Dict[int, Dict[str, Any]] = {}


def _limpar_sessoes_antigas() -> None:
    """
    Remove sessões inativas quando atingir o limite de usuários ou com base no TTL.
    Previne vazamentos de memória (memory leaks) no servidor.
    """
    agora = time.time()
    limite_tempo = agora - (settings.user_session_ttl_hours * 3600)

    # 1. Limpeza por TTL
    usuarios_expirados = [
        uid for uid, dados in memorias.items()
        if dados.get("last_accessed", agora) < limite_tempo
    ]
    for uid in usuarios_expirados:
        del memorias[uid]

    # 2. Se ainda exceder max_active_users, remove os mais antigos (LRU simples)
    if len(memorias) > settings.max_active_users:
        usuarios_ordenados = sorted(
            memorias.keys(),
            key=lambda uid: memorias[uid].get("last_accessed", 0)
        )
        qtd_remover = len(memorias) - settings.max_active_users
        for uid in usuarios_ordenados[:qtd_remover]:
            del memorias[uid]


def obter_memoria(user_id: int) -> Dict[str, Any]:
    """Retorna os dados de memória do usuário, inicializando caso não exista."""
    with _lock:
        if user_id not in memorias:
            _limpar_sessoes_antigas()
            memorias[user_id] = {
                "summary": "",
                "messages": [],
                "last_accessed": time.time(),
                "is_summarizing": False
            }
        else:
            memorias[user_id]["last_accessed"] = time.time()

        return memorias[user_id]


def adicionar_mensagem(user_id: int, mensagem: BaseMessage) -> None:
    """Adiciona uma nova mensagem ao histórico do usuário."""
    with _lock:
        memoria = obter_memoria(user_id)
        memoria["messages"].append(mensagem)
        memoria["last_accessed"] = time.time()


def remover_mensagem(user_id: int, mensagem: BaseMessage = None) -> None:
    """Remove uma mensagem específica ou a última mensagem em caso de falha."""
    with _lock:
        memoria = obter_memoria(user_id)
        if mensagem is not None:
            if mensagem in memoria["messages"]:
                memoria["messages"].remove(mensagem)
        elif memoria["messages"]:
            memoria["messages"].pop()


def obter_ultimas_mensagens(user_id: int, quantidade: int = None) -> List[BaseMessage]:
    """Retorna as últimas N mensagens do usuário."""
    if quantidade is None:
        quantidade = settings.recent_messages_count

    memoria = obter_memoria(user_id)
    with _lock:
        return list(memoria["messages"][-quantidade:])


def obter_resumo(user_id: int) -> str:
    """Retorna o resumo consolidado da conversa anterior."""
    memoria = obter_memoria(user_id)
    return memoria.get("summary", "")


def atualizar_resumo(user_id: int, resumo: str, mensagens_recentes: List[BaseMessage]) -> None:
    """Atualiza o resumo e compacta a lista de mensagens ativas."""
    with _lock:
        memoria = obter_memoria(user_id)
        memoria["summary"] = resumo
        memoria["messages"] = mensagens_recentes
        memoria["is_summarizing"] = False
        memoria["last_accessed"] = time.time()


def pode_iniciar_resumo(user_id: int) -> bool:
    """Verifica e reserva o flag de sumarização para evitar múltiplas execuções simultâneas."""
    with _lock:
        memoria = obter_memoria(user_id)
        if memoria.get("is_summarizing", False):
            return False
        if len(memoria["messages"]) <= settings.memory_limit:
            return False
        memoria["is_summarizing"] = True
        return True


def liberar_flag_resumo(user_id: int) -> None:
    """Libera a flag de sumarização caso o processo falhe."""
    with _lock:
        if user_id in memorias:
            memorias[user_id]["is_summarizing"] = False


def limpar_memoria(user_id: int) -> None:
    """Limpa todo o histórico de um usuário."""
    with _lock:
        if user_id in memorias:
            del memorias[user_id]