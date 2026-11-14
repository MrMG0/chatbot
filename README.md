# LibertApp Chatbot

Chatbot desenvolvido para o projeto acadêmico **LibertApp**.

## 🚀 Como realizar o deploy e configurar

Uma forma simples de colocar este projeto no ar é utilizando a plataforma Render:

1. Crie uma conta e inicie um novo serviço (Web Service) no [Render](https://render.com/) conectando este repositório.
2. Nas configurações do serviço, adicione as seguintes **variáveis de ambiente** (*Environment Variables*):
   - `LLM_API_KEY`: Insira a sua chave de API gerada no [Google AI Studio](https://aistudio.google.com/).
   - `LLM_MODEL`: Escolha o modelo de linguagem desejado (neste projeto, foi utilizado o `gemini-flash-lite-latest`).

### 💾 Persistência de memória (Opcional)

Por padrão, a memória do chatbot é perdida caso o serviço no Render entre em modo de suspensão ou seja reiniciado. Para manter o histórico ativo:

1. Crie um banco de dados Redis gratuito no [Upstash](https://upstash.com/).
2. Copie a URL de conexão fornecida pela plataforma.
3. No Render, adicione mais uma variável de ambiente:
   - `REDIS_URL`: Cole o link disponibilizado pelo Upstash.
