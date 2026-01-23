"""
Services Package

Provides core service classes for the application.
"""

from .vectordb_manager import VectorDBManager, vectordb_manager

__all__ = [
    'VectorDBManager',
    'vectordb_manager'
]
