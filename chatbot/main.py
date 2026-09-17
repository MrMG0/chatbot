import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from models.requests import ChatRequest, UsageRequest
from memory.memory import limpar_memoria
from services.chat_service import gerar_chat
from services.usage_service import analisar_uso, analises_uso

# Configuração de logs estruturados
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("libertapp.api")

app = FastAPI(
    title="LibertApp Chatbot API",
    description="API do Conselheiro Virtual para hábitos saudáveis de tecnologia",
    version="1.1.0"
)

# Configuração de CORS para permitir requisições do frontend mobile/web
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def inicio():
    """Rota de verificação de integridade (Health Check)."""
    return {
        "status": "ok",
        "mensagem": "API do LibertApp funcionando!",
        "version": "1.1.0"
    }


@app.post("/analyze-usage")
async def analyze_usage(request: UsageRequest):
    """
    Analisa os dados de tempo de tela em relação à meta diária e
    retorna um feedback acolhedor gerado pela IA.
    """
    return await analisar_uso(
        user_id=request.user_id,
        screen_time=request.screen_time,
        goal=request.goal
    )


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Endpoint de chat conversacional com streaming assíncrono em tempo real.
    A memória é gerenciada e resumida em segundo plano sem travar a resposta.
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }

    return StreamingResponse(
        gerar_chat(
            user_id=request.user_id,
            message=request.message,
            analises_uso=analises_uso
        ),
        media_type="text/plain; charset=utf-8",
        headers=headers
    )


@app.delete("/chat/{user_id}")
async def reset_chat(user_id: int):
    """Permite reiniciar o histórico de conversa e memória de um usuário."""
    limpar_memoria(user_id)
    return {
        "sucesso": True,
        "mensagem": f"Memória do usuário {user_id} redefinida com sucesso."
    }