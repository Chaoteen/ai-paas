from __future__ import annotations


class ModelError(Exception):
    """Base exception for model layer errors."""


class ModelConfigurationError(ModelError):
    """Raised when model configuration is invalid."""


class ModelRegistryError(ModelError):
    """Raised for registry lookup/registration failures."""


class ModelRequestValidationError(ModelError):
    """Raised when a model request is invalid for the target adapter."""


class ModelProviderError(ModelError):
    """Raised when the upstream model provider returns an error."""


class ModelTimeoutError(ModelProviderError):
    """Raised when the upstream provider times out."""


class ModelAuthenticationError(ModelProviderError):
    """Raised when authentication to the upstream provider fails."""


class ModelCapabilityError(ModelError):
    """Raised when the model does not support a requested capability."""