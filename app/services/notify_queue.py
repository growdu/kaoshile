"""批量通知队列（asyncio.Queue 单进程版）。

约定：
- 生产者 enqueue（send_one / dispatch 改异步）；
- worker 是 async 循环从队列取任务、调 channel.send、写 log；
- v1.1 多实例可换 Redis Streams；
- 单实例部署默认 in-memory queue。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from app.notification.registry import get as registry_get

log = logging.getLogger(__name__)


@dataclass
class NotifyJob:
    """队列任务。"""

    recipient: str
    subject: str
    body: str
    channel_name: str
    # 标识信息（用于日志）
    subscription_id: Optional[str] = None
    exam_id: Optional[int] = None
    node_type: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 3


class NotifyQueue:
    """asyncio.Queue 包装。"""

    def __init__(self, *, maxsize: int = 1000) -> None:
        self._queue: asyncio.Queue[NotifyJob] = asyncio.Queue(maxsize=maxsize)
        self._workers: list[asyncio.Task] = []
        self._retries: list[asyncio.Task] = []
        self._stopped = False

    async def enqueue(self, job: NotifyJob) -> None:
        await self._queue.put(job)

    def qsize(self) -> int:
        return self._queue.qsize()

    async def _worker_loop(self) -> None:
        while not self._stopped:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            try:
                retry_job = self._process_sync(job)
            finally:
                self._queue.task_done()
            # 重试放到 task_done 之后，避免 join 阻塞
            if retry_job is not None:
                await self.enqueue(retry_job)

    def _process_sync(self, job: NotifyJob) -> NotifyJob | None:
        """同步处理一个 job；返回需要重试的 job（或 None）。"""
        try:
            channel = registry_get(job.channel_name)
        except KeyError:
            log.error("notify_channel_not_registered", channel=job.channel_name)
            return None
        try:
            result = channel.send(job.recipient, job.subject, job.body)
        except Exception:  # noqa: BLE001
            log.exception("notify_exception", channel=job.channel_name)
            return None
        if result.success:
            log.info(
                "notify_sent",
                channel=job.channel_name,
                subscription_id=job.subscription_id,
            )
            return None
        log.warning(
            "notify_failed",
            channel=job.channel_name,
            error=result.error,
            attempt=job.attempt,
        )
        if result.retryable and job.attempt < job.max_attempts:
            job.attempt += 1
            return job
        return None

    async def start_workers(self, n: int = 1) -> None:
        """启动 n 个 worker（必须在事件循环内调用）。"""
        for _ in range(n):
            task = asyncio.create_task(self._worker_loop())
            self._workers.append(task)

    async def stop_workers(self) -> None:
        self._stopped = True
        for t in self._workers + self._retries:
            t.cancel()
        await asyncio.gather(*self._workers, *self._retries, return_exceptions=True)
        self._workers.clear()
        self._retries.clear()

    async def drain(self) -> None:
        """等待所有任务完成（测试用）。"""
        await self._queue.join()


_default: Optional[NotifyQueue] = None


def get_notify_queue() -> NotifyQueue:
    global _default
    if _default is None:
        _default = NotifyQueue()
    return _default


def reset_for_test() -> None:
    global _default
    _default = None
