import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, AIMessage

from main import app
from memory.memory import (
    obter_memoria,
    adicionar_mensagem,
    obter_ultimas_mensagens,
    obter_resumo,
    atualizar_resumo,
    pode_iniciar_resumo,
    liberar_flag_resumo,
    limpar_memoria,
    memorias
)
from prompts.prompts import construir_prompt_sistema
from config import settings


class TestChatbot(unittest.TestCase):

    def setUp(self):
        memorias.clear()

    def test_health_check(self):
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("API do LibertApp", data["mensagem"])

    def test_memory_management(self):
        user_id = 999
        msg1 = HumanMessage(content="Olá!")
        msg2 = AIMessage(content="Olá, como posso ajudar?")

        adicionar_mensagem(user_id, msg1)
        adicionar_mensagem(user_id, msg2)

        ultimas = obter_ultimas_mensagens(user_id, 5)
        self.assertEqual(len(ultimas), 2)
        self.assertEqual(ultimas[0].content, "Olá!")
        self.assertEqual(ultimas[1].content, "Olá, como posso ajudar?")

        # Testar resumo
        atualizar_resumo(user_id, "Usuário cumprimentou o conselheiro.", [msg2])
        self.assertEqual(obter_resumo(user_id), "Usuário cumprimentou o conselheiro.")
        self.assertEqual(len(obter_ultimas_mensagens(user_id)), 1)

        # Testar limpeza
        limpar_memoria(user_id)
        self.assertNotIn(user_id, memorias)

    def test_pode_iniciar_resumo_concorrencia(self):
        user_id = 888
        # Com poucas mensagens, não deve disparar resumo
        self.assertFalse(pode_iniciar_resumo(user_id))

        # Simular limite excedido
        memoria = obter_memoria(user_id)
        memoria["messages"] = [HumanMessage(content=f"msg {i}") for i in range(settings.memory_limit + 1)]

        # Primeira tentativa deve permitir
        self.assertTrue(pode_iniciar_resumo(user_id))
        # Segunda tentativa imediata deve recusar (já em andamento)
        self.assertFalse(pode_iniciar_resumo(user_id))

        # Liberar flag
        liberar_flag_resumo(user_id)
        self.assertTrue(pode_iniciar_resumo(user_id))

    def test_construir_prompt_sistema(self):
        prompt = construir_prompt_sistema(
            resumo="Usuário tem meta de reduzir 30 minutos.",
            analise={"screen_time": 120, "goal": 90, "difference": 30}
        )
        self.assertIn("Conselheiro Virtual do LibertApp", prompt)
        self.assertIn("Usuário tem meta de reduzir 30 minutos.", prompt)
        self.assertIn("Tempo de tela: 120 minutos", prompt)

    def test_analyze_usage_endpoint(self):
        mock_response = MagicMock()
        mock_response.content = "Ótimo esforço hoje! Tente fazer uma pausa à noite."

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("services.usage_service.modelo", mock_llm):
            client = TestClient(app)
            response = client.post(
                "/analyze-usage",
                json={"user_id": 1, "screen_time": 100, "goal": 120}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["above_goal"])
            self.assertEqual(data["difference"], -20)
            self.assertEqual(data["recommendation"], "Ótimo esforço hoje! Tente fazer uma pausa à noite.")

    def test_chat_streaming_endpoint(self):
        async def fake_astream(mensagens):
            chunks = ["Olá, ", "tudo ", "bem?"]
            for c in chunks:
                chunk_mock = MagicMock()
                chunk_mock.content = c
                yield chunk_mock

        mock_llm = MagicMock()
        mock_llm.astream = fake_astream

        with patch("services.chat_service.modelo", mock_llm):
            client = TestClient(app)
            response = client.post(
                "/chat",
                json={"user_id": 1, "message": "Oi"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "Olá, tudo bem?")
            self.assertEqual(response.headers["cache-control"], "no-cache")

    def test_reset_chat_endpoint(self):
        user_id = 42
        adicionar_mensagem(user_id, HumanMessage(content="Mensagem antiga"))
        self.assertIn(user_id, memorias)

        client = TestClient(app)
        response = client.delete(f"/chat/{user_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["sucesso"])
        self.assertNotIn(user_id, memorias)


if __name__ == "__main__":
    unittest.main()
