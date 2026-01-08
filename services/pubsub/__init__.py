"""
Pub/Sub service for event broadcasting.

This service provides a unified interface for publishing and subscribing to events
using either Redis or PostgreSQL as the backend.
"""

from .client import (
    PubSubClient,
    PostgresPubSubClient,
    RedisPubSubClient,
    create_pubsub_client,
    get_default_client,
    set_default_client
)

__all__ = [
    'PubSubClient',
    'PostgresPubSubClient',
    'RedisPubSubClient',
    'create_pubsub_client',
    'get_default_client',
    'set_default_client',
]

