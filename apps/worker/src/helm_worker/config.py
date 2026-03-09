from helm_runtime import RuntimeAppSettings, runtime_settings_config


class WorkerSettings(RuntimeAppSettings):
    model_config = runtime_settings_config()

    worker_poll_seconds: int = 30


settings = WorkerSettings()
