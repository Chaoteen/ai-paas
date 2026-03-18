from __future__ import annotations


class GenerationError(Exception):
    """Base exception for generation layer errors."""


class GenerationConfigurationError(GenerationError):
    """Raised when generation provider configuration is invalid."""


class GenerationRegistryError(GenerationError):
    """Raised for registry lookup/registration failures."""


class GenerationRequestValidationError(GenerationError):
    """Raised when a generation request is invalid."""


class GenerationProviderError(GenerationError):
    """Raised when the upstream generation provider fails."""


class GenerationTimeoutError(GenerationProviderError):
    """Raised when the upstream generation provider times out."""


class GenerationAuthenticationError(GenerationProviderError):
    """Raised on provider authentication failure."""


class GenerationCapabilityError(GenerationError):
    """Raised when requested task cannot be served by provider."""