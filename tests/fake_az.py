"""A stand-in for bw.az.Az: records every command and answers from canned responses. Never runs az."""

from typing import Any, Dict, List, Tuple

from bw.az import AzError


class FakeAz:
    def __init__(self, responses: Dict[Tuple[str, ...], Any], dry_run: bool = False):
        # Longest matching argument prefix wins. A value that is an Exception instance is raised.
        self.responses = responses
        self.dry_run = dry_run
        self.calls: List[List[str]] = []
        self.mutations: List[List[str]] = []

    def run(self, args: List[str], *, mutating: bool = False) -> Any:
        self.calls.append(list(args))
        if mutating:
            self.mutations.append(list(args))
            if self.dry_run:
                return None
        best = None
        for prefix in self.responses:
            if tuple(args[: len(prefix)]) == prefix and (best is None or len(prefix) > len(best)):
                best = prefix
        if best is None:
            if mutating:
                return None
            raise AssertionError(f"FakeAz has no response for: az {' '.join(args)}")
        value = self.responses[best]
        if isinstance(value, Exception):
            raise value
        return value


def az_error(message: str = "boom") -> AzError:
    return AzError(["x"], 1, message)
