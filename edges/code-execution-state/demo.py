"""code-execution-state: wrapper for the code-execution-statefulness edge.

Two phases (the durability proof needs a >20-minute idle between them):
    python demo.py              # write phase: write a nonce, warm read-back, save container ids
    python demo.py --verify     # re-read the same containers after the idle gap
"""

from engine.demonstrators.code_execution_state import main


if __name__ == "__main__":
    raise SystemExit(main())
