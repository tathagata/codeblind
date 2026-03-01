import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class VSCodeIntegration:
    """Hooks for opening files in VSCode and displaying Claude-generated code."""

    def open_file(self, file_path):
        """Open a file in VSCode for optional manual inspection."""
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            logger.error("File not found: %s", abs_path)
            return False
        logger.info("Opening %s in VSCode...", abs_path)
        try:
            subprocess.run(["code", abs_path], check=True)
            return True
        except FileNotFoundError:
            logger.warning(
                "VSCode 'code' command not found. Is VSCode installed and in PATH?"
            )
            return False
        except subprocess.CalledProcessError as e:
            logger.error("Failed to open file in VSCode: %s", e)
            return False

    def display_code(self, code, label="Generated Code"):
        """Log code line-by-line for interactive inspection."""
        logger.info("--- %s ---", label)
        for i, line in enumerate(code.splitlines(), start=1):
            logger.info("%4d: %s", i, line)
        logger.info("--- End of %s ---", label)
