import json
import logging
import threading
import time
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, messages_to_dict, messages_from_dict
from config import settings

logger = logging.getLogger(__name__)

# Lock reentrante para sincronização de threads locais
_lock = threading.RLock()

# Fallback em memória (utilizado quando o Redis não estiver configurado)
memorias: Dict[int, Dict[str, Any]] = {}

# Inicialização do cliente Redis caso redis_url esteja preenchida
redis_client = None
if settings.redis_url:
    try:
        import redis
        redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5.0
        )
        redis_client.ping()
        logger.info("Conexão com Upstash Redis estabelecida com sucesso!")
    except Exception as e:
        logger.warning(f"Não foi possível conectar ao Redis ({e}). Usando memória local temporária.")
        redis_client = None


def _obter_chave_redis(user_id: int) -> str:
    return f"libertapp:memory:{user_id}"


def _carregar_memoria_redis(user_id: int) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_obter_chave_redis(user_id))
        if raw:
            dados = json.loads(raw)
            return {
                "summary": dados.get("summary", ""),
                "messages": messages_from_dict(dados.get("messages", [])),
                "last_accessed": dados.get("last_accessed", time.time()),
                "is_summarizing": dados.get("is_summarizing", False)
            }
    except Exception as e:
        logger.error(f"Erro ao carregar memória do Redis para user_id={user_id}: {e}")
    return None


def _salvar_memoria_redis(user_id: int, dados: Dict[str, Any]) -> None:
    if not redis_client:
        return
    try:
        payload = {
            "summary": dados.get("summary", ""),
            "messages": messages_to_dict(dados.get("messages", [])),
            "last_accessed": dados.get("last_accessed", time.time()),
            "is_summarizing": dados.get("is_summarizing", False)
        }
        # TTL automático em segundos (ex: 24h = 86400s)
        ttl = settings.user_session_ttl_hours * 3600
        redis_client.set(_obter_chave_redis(user_id), json.dumps(payload), ex=ttl)
    except Exception as e:
        logger.error(f"Erro ao salvar memória no Redis para user_id={user_id}: {e}")


def _limpar_sessoes_antigas() -> None:
    """Limpeza periódica de memória local quando o Redis não estiver ativo."""
    agora = time.time()
    limite_tempo = agora - (settings.user_session_ttl_hours * 3600)

    usuarios_expirados = [
        uid for uid, dados in memorias.items()
        if dados.get("last_accessed", agora) < limite_tempo
    ]
    for uid in usuarios_expirados:
        del memorias[uid]

    if len(memorias) > settings.max_active_users:
        usuarios_ordenados = sorted(
            memorias.keys(),
            key=lambda uid: memorias[uid].get("last_accessed", 0)
        )
        qtd_remover = len(memorias) - settings.max_active_users
        for uid in usuarios_ordenados[:qtd_remover]:
            del memorias[uid]


def obter_memoria(user_id: int) -> Dict[str, Any]:
    """Retorna os dados de memória do usuário (do Redis ou da memória local)."""
    with _lock:
        if redis_client:
            memoria = _carregar_memoria_redis(user_id)
            if memoria is not None:
                memoria["last_accessed"] = time.time()
                return memoria

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

        if redis_client:
            _salvar_memoria_redis(user_id, memorias[user_id])

        return memorias[user_id]


def adicionar_mensagem(user_id: int, mensagem: BaseMessage) -> None:
    """Adiciona uma nova mensagem ao histórico do usuário."""
    with _lock:
        memoria = obter_memoria(user_id)
        memoria["messages"].append(mensagem)
        memoria["last_accessed"] = time.time()
        if redis_client:
            _salvar_memoria_redis(user_id, memoria)


def remover_mensagem(user_id: int, mensagem: BaseMessage = None) -> None:
    """Remove uma mensagem específica ou a última mensagem em caso de falha."""
    with _lock:
        memoria = obter_memoria(user_id)
        if mensagem is not None:
            if mensagem in memoria["messages"]:
                memoria["messages"].remove(mensagem)
        elif memoria["messages"]:
            memoria["messages"].pop()
        if redis_client:
            _salvar_memoria_redis(user_id, memoria)


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
        if redis_client:
            _salvar_memoria_redis(user_id, memoria)


def pode_iniciar_resumo(user_id: int) -> bool:
    """Verifica e reserva o flag de sumarização para evitar múltiplas execuções simultâneas."""
    with _lock:
        memoria = obter_memoria(user_id)
        if memoria.get("is_summarizing", False):
            return False
        if len(memoria["messages"]) <= settings.memory_limit:
            return False
        memoria["is_summarizing"] = True
        if redis_client:
            _salvar_memoria_redis(user_id, memoria)
        return True


def liberar_flag_resumo(user_id: int) -> None:
    """Libera a flag de sumarização caso o processo falhe."""
    with _lock:
        memoria = obter_memoria(user_id)
        memoria["is_summarizing"] = False
        if redis_client:
            _salvar_memoria_redis(user_id, memoria)


def limpar_memoria(user_id: int) -> None:
    """Limpa todo o histórico de um usuário."""
    with _lock:
        if user_id in memorias:
            del memorias[user_id]
        if redis_client:
            try:
                redis_client.delete(_obter_chave_redis(user_id))
            except Exception as e:
                logger.error(f"Erro ao deletar chave do Redis para user_id={user_id}: {e}")