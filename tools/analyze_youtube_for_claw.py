"""Bridge the Claw Code video skill to the local J.A.R.V.I.S. analyzer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.brain import JarvisBrain


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a YouTube URL with local J.A.R.V.I.S.")
    parser.add_argument("url", help="YouTube watch, Shorts, youtu.be, or embed URL")
    parser.add_argument(
        "--question",
        default="Analysiere dieses Video vollständig und beschreibe Inhalt, Personen, Szenen und sichtbaren Text.",
        help="Question to answer from the analyzed video",
    )
    args = parser.parse_args()

    brain = JarvisBrain()
    answer = brain.process_request(f"{args.url}\n{args.question}")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
