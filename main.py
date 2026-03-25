#!/usr/bin/env python3
"""
main.py — Entry point for the codeblind voice coding harness.

Usage:
    .venv/bin/python main.py
    .venv/bin/python main.py --voice handy
    .venv/bin/python main.py --once
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from voice_parser import VoiceParser, HandyVoiceParser, VoiceParserError
from claude_api import ClaudeAPI, ClaudeAPIError
from repo_ops import RepoOperations, RepoOperationError
from testing_guardrails import TestingGuardrails
from orchestrator import Orchestrator, TTSBridge, TTSError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Codeblind — voice-first coding harness")
    parser.add_argument("--voice", choices=["microphone", "handy"], default="microphone",
                        help="Voice input method (default: microphone)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single conversational turn and exit (default: loop)")
    parser.add_argument("--direct", action="store_true",
                        help="Use the legacy direct voice-to-Claude path without session gating")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set. Add it to .env or the environment.")
        sys.exit(1)

    voice_parser = HandyVoiceParser() if args.voice == "handy" else VoiceParser()
    testing_guardrails = TestingGuardrails()
    repo_operations = RepoOperations(
        repo_root=os.path.dirname(__file__),
        testing_guardrails=testing_guardrails,
    )
    orchestrator = Orchestrator(
        voice_parser=voice_parser,
        claude_api=ClaudeAPI(api_key=api_key),
        testing_guardrails=testing_guardrails,
        tts_bridge=TTSBridge(),
        repo_operations=repo_operations,
    )

    if args.direct:
        logger.info("CodeBlind direct mode ready. Speak your request. Press Ctrl+C to stop.")
        if args.once:
            _run_direct_cycle(orchestrator)
            return
        while True:
            try:
                _run_direct_cycle(orchestrator)
            except KeyboardInterrupt:
                logger.info("Interrupted. Goodbye.")
                break
        return

    logger.info("CodeBlind session mode ready. Speak your request. Press Ctrl+C to stop.")
    greeting = orchestrator.start_session()
    logger.info(greeting)

    if args.once:
        _run_session_cycle(orchestrator, voice_parser)
        return

    while True:
        try:
            _run_session_cycle(orchestrator, voice_parser)
        except KeyboardInterrupt:
            logger.info("Interrupted. Goodbye.")
            break


def _run_direct_cycle(orchestrator):
    try:
        result = orchestrator.run_pipeline()
        logger.info("Done. Command: %s", result["command"])
    except VoiceParserError as e:
        logger.warning("Voice input failed: %s — try again.", e)
    except ClaudeAPIError as e:
        logger.error("Claude API error: %s", e)
    except TTSError as e:
        logger.error("TTS error: %s", e)


def _run_session_cycle(orchestrator, voice_parser):
    try:
        logger.info("Listening for the next session turn...")
        transcript = voice_parser.speech_to_text()
        logger.info("You said: %s", transcript)
        result = orchestrator.handle_turn(transcript)
        logger.info("Intent: %s", result.intent)
        logger.info("Response: %s", result.spoken_response)
        if result.pending_approval_request:
            logger.info("Pending approval: %s", result.pending_approval_request.summary)
        if result.verification_summary:
            logger.info("Verification: %s", result.verification_summary)
    except VoiceParserError as e:
        logger.warning("Voice input failed: %s — try again.", e)
    except RepoOperationError as e:
        logger.error("Repo operation failed: %s", e)
    except ClaudeAPIError as e:
        logger.error("Claude API error: %s", e)
    except TTSError as e:
        logger.error("TTS error: %s", e)
    except Exception as e:
        logger.error("Session turn failed: %s", e)


if __name__ == "__main__":
    main()
