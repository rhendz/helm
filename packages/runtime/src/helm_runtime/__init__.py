from __future__ import annotations

__all__ = [
    "RuntimeAppSettings",
    "RuntimeSettings",
    "build_email_agent_runtime",
    "runtime_settings_config",
]


def __getattr__(name: str):  # noqa: ANN201
    if name in __all__:
        from helm_runtime.config import RuntimeAppSettings, RuntimeSettings, runtime_settings_config
        from helm_runtime.email_agent import build_email_agent_runtime

        return {
            "RuntimeAppSettings": RuntimeAppSettings,
            "RuntimeSettings": RuntimeSettings,
            "build_email_agent_runtime": build_email_agent_runtime,
            "runtime_settings_config": runtime_settings_config,
        }[name]
    raise AttributeError(name)
