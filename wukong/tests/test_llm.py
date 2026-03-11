import pytest
import os
from dotenv import load_dotenv
from wukong.core.llm import get_llm_backend, ChatMessage

# Load environment variables
load_dotenv()

@pytest.fixture
def llm():
    """Pytest fixture for LLM backend."""
    # 强制在测试中使用 mock，除非明确指定
    if not os.getenv("wukong_LLM_PROVIDER"):
        os.environ["wukong_LLM_PROVIDER"] = "mock"
    
    return get_llm_backend()

@pytest.mark.asyncio
async def test_basic_chat(llm):
    """Test basic non-streaming chat."""
    messages = [
        ChatMessage(role="user", content="Hello, please introduce yourself.")
    ]
    response = await llm.chat(messages)
    
    assert response is not None
    # MockLLM returns "mock response"
    if os.getenv("wukong_LLM_PROVIDER") == "mock":
        assert "mock" in response.content
    else:
        assert response.content is not None
    
    assert "total_tokens" in response.usage

@pytest.mark.asyncio
async def test_streaming_chat(llm):
    """Test streaming chat."""
    messages = [
        ChatMessage(role="user", content="What is Python?")
    ]
    
    chunks = []
    async for chunk in llm.stream_chat(messages):
        if chunk.content:
            chunks.append(chunk.content)
    
    full_response = "".join(chunks)
    assert len(full_response) > 0
    
    if os.getenv("wukong_LLM_PROVIDER") == "mock":
        assert "mock" in full_response

if __name__ == "__main__":
    # Allow running this file directly
    import pytest
    pytest.main([__file__, "-v", "-s"])
