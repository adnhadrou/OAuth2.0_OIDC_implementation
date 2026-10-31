"""Intentionally unsafe logic exists ONLY in this isolated teaching fixture."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def test_introduced_check_then_set_flaw():
    state = {"consumed": False}
    both_read = Barrier(2)

    def unsafe_redeem():
        observed = state["consumed"]
        both_read.wait(timeout=5)
        if observed:
            return False
        state["consumed"] = True
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(unsafe_redeem) for _ in range(2)]
        assert [future.result() for future in futures] == [True, True]
