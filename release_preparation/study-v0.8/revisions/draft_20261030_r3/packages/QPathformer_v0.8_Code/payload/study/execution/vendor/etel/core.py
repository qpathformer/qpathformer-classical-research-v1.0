"""Bounded local ETEL scheduling; logical 64-worker blocks are not model replicas."""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
import json
from threading import Lock
from typing import Callable, Sequence

BLOCK_SIZE = 64


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _job_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("job_id must be a non-empty string")
    return value


def _json_copy(value: object, name: str) -> object:
    """Validate finite JSON, reject key coercion, and detach nested mutable values."""
    def check_keys(item: object) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError(f"{name} object keys must be strings")
            for child in item.values():
                check_keys(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check_keys(child)

    try:
        check_keys(value)
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError(f"{name} must contain finite JSON-compatible values: {exc}") from exc


@dataclass(frozen=True)
class Config:
    min_blocks: int = 1
    max_blocks: int = 3
    max_parallel_tasks: int = 5
    scale_down_checks: int = 2

    def __post_init__(self) -> None:
        for name in ("min_blocks", "max_blocks", "max_parallel_tasks", "scale_down_checks"):
            _integer(getattr(self, name), name, 1)
        if self.max_blocks < self.min_blocks:
            raise ValueError("max_blocks must be >= min_blocks")


@dataclass(frozen=True)
class Task:
    job_id: str
    payload: dict

    def __post_init__(self) -> None:
        _job_id(self.job_id)
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a JSON object")
        object.__setattr__(self, "payload", _json_copy(self.payload, "payload"))


class Controller:
    """Single-owner logical allocator; run_tasks keeps all calls on its main thread."""

    def __init__(self, config: Config):
        if not isinstance(config, Config):
            raise ValueError("config must be a Config")
        self.config = config
        self.events: list[dict] = []
        self._states = ["INACTIVE"] * config.max_blocks
        self._assignments: dict[int, str] = {}
        self._seen_jobs: set[str] = set()
        self._next_block = 0
        self._down_checks = 0
        self._peak_ready = 0
        self._peak_in_flight = 0
        self.scale_to(config.min_blocks)

    def _capacities(self) -> dict:
        ready = self._states.count("READY") * BLOCK_SIZE
        draining = self._states.count("DRAINING") * BLOCK_SIZE
        return {"ready_capacity": ready, "draining_capacity": draining,
                "enabled_capacity": ready + draining}

    def _emit(self, event: str, block_id: int | None = None,
              worker_id: int | None = None, job_id: str | None = None) -> None:
        capacities = self._capacities()
        self._peak_ready = max(self._peak_ready, capacities["ready_capacity"])
        self.events.append({"event": event, "block_id": block_id,
                            "worker_id": worker_id, "job_id": job_id,
                            **capacities, "in_flight": len(self._assignments)})

    def _block_busy(self, block_id: int) -> bool:
        return any(worker // BLOCK_SIZE == block_id for worker in self._assignments)

    def scale_to(self, blocks: int) -> None:
        """Set the desired READY prefix, retaining busy removed blocks as DRAINING."""
        _integer(blocks, "blocks", self.config.min_blocks)
        if blocks > self.config.max_blocks:
            raise ValueError("blocks exceeds max_blocks")
        self._down_checks = 0
        for block_id in range(self.config.max_blocks):
            state = self._states[block_id]
            if block_id < blocks and state != "READY":
                self._states[block_id] = "READY"
                self._emit("block_reactivated" if state == "DRAINING" else "block_activated",
                           block_id)
            elif block_id >= blocks and state == "READY":
                busy = self._block_busy(block_id)
                self._states[block_id] = "DRAINING" if busy else "INACTIVE"
                self._emit("block_draining" if busy else "block_deactivated", block_id)

    def acquire(self, job_id: str) -> int | None:
        job_id = _job_id(job_id)
        if job_id in self._seen_jobs:
            raise ValueError(f"job_id has already been acquired: {job_id}")
        if len(self._assignments) >= self.config.max_parallel_tasks:
            return None
        for step in range(self.config.max_blocks):
            block_id = (self._next_block + step) % self.config.max_blocks
            if self._states[block_id] != "READY":
                continue
            for offset in range(BLOCK_SIZE):
                worker_id = block_id * BLOCK_SIZE + offset
                if worker_id not in self._assignments:
                    self._assignments[worker_id] = job_id
                    self._seen_jobs.add(job_id)
                    self._next_block = (block_id + 1) % self.config.max_blocks
                    self._peak_in_flight = max(self._peak_in_flight, len(self._assignments))
                    self._emit("task_acquired", block_id, worker_id, job_id)
                    return worker_id
        return None

    def release(self, worker_id: int) -> None:
        _integer(worker_id, "worker_id")
        if worker_id not in self._assignments:
            raise ValueError("worker_id has no in-flight assignment")
        job_id = self._assignments.pop(worker_id)
        block_id = worker_id // BLOCK_SIZE
        self._emit("task_released", block_id, worker_id, job_id)
        if self._states[block_id] == "DRAINING" and not self._block_busy(block_id):
            self._states[block_id] = "INACTIVE"
            self._emit("block_deactivated", block_id)

    def observe(self, outstanding_tasks: int) -> dict:
        """Scale on pending plus in-flight tasks; consecutive lower observations drain."""
        _integer(outstanding_tasks, "outstanding_tasks")
        target = min(self.config.max_blocks,
                     max(self.config.min_blocks, (outstanding_tasks + BLOCK_SIZE - 1) // BLOCK_SIZE))
        current = self._states.count("READY")
        if target > current:
            self.scale_to(target)
        elif target < current:
            self._down_checks += 1
            if self._down_checks >= self.config.scale_down_checks:
                self.scale_to(target)
        else:
            self._down_checks = 0
        return self.snapshot()

    def snapshot(self) -> dict:
        return {**self._capacities(), "in_flight": len(self._assignments),
                "ready_blocks": self._states.count("READY"),
                "draining_blocks": self._states.count("DRAINING"),
                "inactive_blocks": self._states.count("INACTIVE"),
                "scale_down_checks_pending": self._down_checks,
                "peak_ready_capacity": self._peak_ready,
                "peak_in_flight": self._peak_in_flight,
                "blocks": [{"block_id": block_id, "state": state,
                            "in_flight": sum(w // BLOCK_SIZE == block_id
                                             for w in self._assignments)}
                           for block_id, state in enumerate(self._states)],
                "assignments": dict(self._assignments)}


def run_tasks(tasks: Sequence[Task], handler: Callable[[Task], object],
              config: Config) -> dict:
    """Execute isolated task copies with bounded threads, ordered results, and no retries.

    Thread overlap is not a claim of CPU parallelism or a measured study throughput.
    Handler Exceptions fail only that task. KeyboardInterrupt/SystemExit propagate.
    """
    if not isinstance(config, Config):
        raise ValueError("config must be a Config")
    if not callable(handler):
        raise ValueError("handler must be callable")
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        raise ValueError("tasks must be a sequence of Task objects")
    prepared = []
    seen = set()
    for task in tasks:
        if not isinstance(task, Task):
            raise ValueError("tasks must contain only Task objects")
        if task.job_id in seen:
            raise ValueError(f"duplicate job_id: {task.job_id}")
        seen.add(task.job_id)
        prepared.append(Task(task.job_id, task.payload))

    controller = Controller(config)
    results: list[dict | None] = [None] * len(prepared)
    running = 0
    peak_running = 0
    running_lock = Lock()

    def execute(task: Task) -> dict:
        nonlocal running, peak_running
        try:
            private_task = Task(task.job_id, task.payload)
            with running_lock:
                running += 1
                peak_running = max(peak_running, running)
            try:
                output = handler(private_task)
            finally:
                with running_lock:
                    running -= 1
            return {"job_id": task.job_id, "status": "succeeded",
                    "output": _json_copy(output, "handler output")}
        except Exception as exc:
            return {"job_id": task.job_id, "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}"}

    next_index = 0
    futures = {}
    try:
        with ThreadPoolExecutor(max_workers=config.max_parallel_tasks,
                                thread_name_prefix="etel") as pool:
            while next_index < len(prepared) or futures:
                controller.observe(len(prepared) - next_index + len(futures))
                while next_index < len(prepared) and len(futures) < config.max_parallel_tasks:
                    task = prepared[next_index]
                    worker_id = controller.acquire(task.job_id)
                    if worker_id is None:
                        break
                    future = pool.submit(execute, task)
                    futures[future] = (next_index, worker_id)
                    next_index += 1
                if not futures:
                    raise RuntimeError("pending tasks could not acquire a ready worker")
                completed, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in completed:
                    index, worker_id = futures.pop(future)
                    try:
                        results[index] = future.result()
                    finally:
                        controller.release(worker_id)
    finally:
        # Executor shutdown waits for started handlers before their leases are retired.
        for worker_id in list(controller.snapshot()["assignments"]):
            controller.release(worker_id)
        controller.scale_to(config.min_blocks)

    if any(result is None for result in results):
        raise RuntimeError("execution ended without a result for every submitted task")
    final = controller.snapshot()
    succeeded = sum(result["status"] == "succeeded" for result in results)
    return {"results": results, "events": controller.events,
            "summary": {"submitted": len(prepared), "succeeded": succeeded,
                        "failed": len(prepared) - succeeded,
                        "peak_in_flight": final["peak_in_flight"],
                        "peak_running": peak_running,
                        "max_parallel_tasks": config.max_parallel_tasks,
                        "final_capacity": final["enabled_capacity"],
                        "peak_ready_capacity": final["peak_ready_capacity"]}}
