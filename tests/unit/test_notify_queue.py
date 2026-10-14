"""NotifyQueue 单元测试。"""
from __future__ import annotations

import asyncio

import pytest

from app.notification.mock import MockChannel
from app.notification.registry import register, reset_for_test
from app.services.notify_queue import NotifyJob, NotifyQueue, get_notify_queue, reset_for_test


@pytest.fixture
def mock_channels():
    reset_for_test()
    ch = MockChannel("email")
    register(ch)
    return ch


@pytest.mark.asyncio
async def test_enqueue_and_drain(mock_channels):
    queue = NotifyQueue()
    await queue.start_workers(n=2)
    await queue.enqueue(NotifyJob(recipient="u1", subject="s", body="b", channel_name="email"))
    await queue.enqueue(NotifyJob(recipient="u2", subject="s", body="b", channel_name="email"))
    await queue.drain()
    await queue.stop_workers()
    assert mock_channels.call_count == 2
    assert mock_channels.calls[0].recipient == "u1"


@pytest.mark.asyncio
async def test_channel_not_registered_logs_only():
    queue = NotifyQueue()
    await queue.start_workers(n=1)
    await queue.enqueue(NotifyJob(recipient="u", subject="s", body="b", channel_name="ghost"))
    await queue.drain()
    await queue.stop_workers()


@pytest.mark.asyncio
async def test_default_singleton():
    reset_for_test()
    q1 = get_notify_queue()
    q2 = get_notify_queue()
    assert q1 is q2


@pytest.mark.asyncio
async def test_qsize_tracks_puts(mock_channels):
    queue = NotifyQueue()
    await queue.start_workers(n=1)
    assert queue.qsize() == 0
    await queue.enqueue(NotifyJob(recipient="u", subject="s", body="b", channel_name="email"))
    assert queue.qsize() == 1
    await queue.drain()
    await queue.stop_workers()
    assert queue.qsize() == 0
