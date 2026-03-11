import pytest
import os
from dotenv import load_dotenv
from wukong.core.llm import get_llm_backend, ChatMessage

# 加载环境变量
load_dotenv()

@pytest.fixture
def llm():
    """获取 LLM 后端的 pytest fixture"""
    # 强制在测试中使用 mock，除非明确指定
    if not os.getenv("wukong_LLM_PROVIDER"):
        os.environ["wukong_LLM_PROVIDER"] = "mock"
    
    return get_llm_backend()

@pytest.mark.asyncio
async def test_basic_chat(llm):
    """测试普通非流式对话"""
    messages = [
        ChatMessage(role="user", content="你好，请自我介绍一下。")
    ]
    response = await llm.chat(messages)
    
    assert response is not None
    # MockLLM 的返回包含 "模拟回复"
    if os.getenv("wukong_LLM_PROVIDER") == "mock":
        assert "模拟回复" in response.content
    else:
        assert response.content is not None
    
    assert "total_tokens" in response.usage

@pytest.mark.asyncio
async def test_streaming_chat(llm):
    """测试流式对话"""
    messages = [
        ChatMessage(role="user", content="什么是 Python？")
    ]
    
    chunks = []
    async for chunk in llm.stream_chat(messages):
        if chunk.content:
            chunks.append(chunk.content)
    
    full_response = "".join(chunks)
    assert len(full_response) > 0
    
    if os.getenv("wukong_LLM_PROVIDER") == "mock":
        assert "模拟" in full_response

if __name__ == "__main__":
    # 允许直接运行此文件
    import pytest
    pytest.main([__file__, "-v", "-s"])
