"""
Intelligent File Organizer
--------------------------
A modular, extensible file organization engine built for reliability,
scalability, and future AI-powered sorting capabilities.

Package layout:
    config_manager  – Loads, validates, and merges JSON/YAML configs
    logger          – Structured logging (console + optional file)
    scanner         – Directory traversal and file discovery
    categorizer     – Extension/MIME-based file classification
    duplicate_handler – Safe conflict resolution strategies
    mover           – Atomic file move with rollback support
    core            – Orchestrator that wires all components together
"""

from .core import FileOrganizer

__all__ = ["FileOrganizer"]
__version__ = "1.0.0"
