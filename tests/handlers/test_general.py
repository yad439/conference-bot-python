import pytest
from unittest.mock import AsyncMock

from handlers import general


@pytest.mark.asyncio(loop_scope='function')
async def test_start():
    message = AsyncMock(text='/start')
    state_mock = AsyncMock()
    await general.handle_start(message, state_mock)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '/configure' in args[0]
    assert '/list' in args[0]
