"""Python wrapper around haql-memory C++ CLI binary."""
import subprocess
import json
import os
from pathlib import Path
from typing import Optional

MEMORY_BIN = os.environ.get(
    "HAQL_MEMORY_BIN",
    str(Path.home() / "Desktop" / "haql-memory" / "build" / "haql-memory"),
)


class MemoryClient:
    """Thin subprocess wrapper around the haql-memory binary."""

    def __init__(self, bin_path: str = MEMORY_BIN):
        self.bin = Path(bin_path)
        if not self.bin.exists():
            raise FileNotFoundError(f"haql-memory not found at {self.bin}")
        self._env = os.environ.copy()

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            [str(self.bin), *args],
            capture_output=True, text=True, timeout=30, env=self._env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"haql-memory failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def project_create(self, pid: str, name: str = "",
                       domain: str = "generic") -> str:
        cmd = ["project", "create", pid]
        if name:
            cmd += ["--name", name]
        cmd += ["--domain", domain]
        return self._run(*cmd)

    def project_delete(self, pid: str) -> str:
        return self._run("project", "delete", pid)

    def entity_add(self, pid: str, eid: str, *,
                   kind: str = "", name: str = "") -> str:
        cmd = ["entity", "add", pid, eid]
        if kind:
            cmd += ["--kind", kind]
        if name:
            cmd += ["--name", name]
        return self._run(*cmd)

    def entity_set(self, pid: str, eid: str,
                   props: Optional[dict] = None,
                   tags: Optional[list] = None) -> str:
        cmd = ["entity", "set", pid, eid]
        if props:
            for k, v in props.items():
                cmd += ["--prop", f"{k}={v}"]
        if tags:
            for t in tags:
                cmd += ["--tag", t]
        return self._run(*cmd)

    def entity_get(self, pid: str, eid: str) -> str:
        return self._run("entity", "get", pid, eid)

    def relate(self, pid: str, src: str, tgt: str,
               kind: str = "related") -> str:
        return self._run("relate", pid, src, tgt, "--kind", kind)

    def log(self, pid: str, eid: str, action: str = "event",
            props: Optional[dict] = None) -> str:
        cmd = ["log", pid, eid, "--action", action]
        if props:
            for k, v in props.items():
                cmd += ["--prop", f"{k}={v}"]
        return self._run(*cmd)

    def search(self, pid: str, query: str, kind: str = "") -> str:
        cmd = ["search", pid, query]
        if kind:
            cmd += ["--kind", kind]
        return self._run(*cmd)

    def save(self) -> str:
        return self._run("save")