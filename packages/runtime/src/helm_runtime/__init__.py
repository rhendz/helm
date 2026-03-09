from __future__ import annotations

__all__ = ["RuntimeAppSettings", "RuntimeSettings", "runtime_settings_config"]


def __getattr__(name: str):  # noqa: ANN201
    if name in __all__:
        from helm_runtime.config import RuntimeAppSettings, RuntimeSettings, runtime_settings_config

        return {
            "RuntimeAppSettings": RuntimeAppSettings,
            "RuntimeSettings": RuntimeSettings,
            "runtime_settings_config": runtime_settings_config,
        }[name]
    raise AttributeError(name)
