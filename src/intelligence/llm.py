from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

model: BaseChatModel = init_chat_model(
    # model="mistralai/ministral-3-3b",
    model="liquid/lfm2.5-1.2b",
    model_provider="openai",
    base_url="http://127.0.0.1:1234/v1",
    api_key="not-needed",
)
