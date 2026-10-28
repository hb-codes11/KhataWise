import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
import settings

logger = logging.getLogger("log_watcher")

class LogWatcher:
    """
    Monitors error.log, input.log, output.log, and server.log.
    Maintains byte offsets to detect newly added content continuously.
    """
    def __init__(self, watched_files: Optional[Dict[str, str]] = None):
        self.watched_files = watched_files or settings.WATCHED_LOGS
        self.offsets: Dict[str, int] = {}
        self.identities = {}
        self._initialize_offsets()

    def _initialize_offsets(self):
        """Initialize offsets to the current end of each existing file (or 0)."""
        for name, path_str in self.watched_files.items():
            path = Path(path_str)
            if not path.exists():
                # Create the file if missing
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                self.offsets[name] = 0
            else:
                self.offsets[name] = path.stat().st_size
            stat = path.stat()
            self.identities[name] = (stat.st_dev, stat.st_ino)

    def check_updates(self) -> Dict[str, List[str]]:
        """
        Scans all watched files for newly appended lines.
        Returns a dict of file_key -> list of new non-empty lines.
        """
        updates: Dict[str, List[str]] = {}

        for name, path_str in self.watched_files.items():
            path = Path(path_str)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                self.offsets[name] = 0
                self.identities.pop(name, None)
                continue

            stat = path.stat()
            identity = (stat.st_dev, stat.st_ino)
            current_size = stat.st_size
            last_offset = self.offsets.get(name, 0)

            # Handle file truncation/rotation
            if current_size < last_offset or self.identities.get(name) != identity:
                logger.info(f"Log file '{name}' was truncated or rotated. Resetting offset.")
                last_offset = 0

            self.identities[name] = identity
            self.offsets[name] = last_offset
            if current_size > last_offset:
                try:
                    with open(path, "rb") as f:
                        f.seek(last_offset)
                        new_content = f.read().decode("utf-8", errors="replace")
                        self.offsets[name] = f.tell()

                    new_lines = [line.strip() for line in new_content.splitlines() if line.strip()]
                    if new_lines:
                        updates[name] = new_lines
                        logger.info(f"Detected {len(new_lines)} new lines in {name} log ({path_str})")
                except Exception as e:
                    logger.error(f"Error reading {name} log at {path_str}: {e}")

        return updates

    def get_tail(self, name: str, lines: int = 50) -> List[str]:
        """Reads the last N lines of a specified log."""
        path_str = self.watched_files.get(name)
        if not path_str:
            return []
        path = Path(path_str)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                return [line.rstrip() for line in all_lines[-lines:]]
        except Exception as e:
            logger.error(f"Failed to read tail of {name}: {e}")
            return []

    def get_status(self) -> Dict[str, Dict]:
        """Returns file existence, size, and current offset information."""
        status = {}
        for name, path_str in self.watched_files.items():
            p = Path(path_str)
            exists = p.exists()
            size = p.stat().st_size if exists else 0
            status[name] = {
                "address": path_str,
                "exists": exists,
                "size_bytes": size,
                "offset": self.offsets.get(name, 0)
            }
        return status

