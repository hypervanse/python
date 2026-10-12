"""
Runs the headless self-test in its own process, exactly as a user would run it.

A separate process matters: the self-test calls pygame.quit() when it finishes, and running it
inside pytest would leave pygame shut down for the other tests.
"""

import subprocess
import sys


def test_selftest_passes_in_a_fresh_process():
    result = subprocess.run(
        [sys.executable, "-m", "flappy", "--selftest"],
        capture_output=True,
        text=True,
        timeout=180,                           # generous: sound synthesis plus ~25 s of simulated play
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
