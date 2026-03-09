from helm_runtime import RuntimeAppSettings, runtime_settings_config


class APISettings(RuntimeAppSettings):
    model_config = runtime_settings_config()

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = APISettings()
