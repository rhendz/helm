"""Root conftest: inject required env vars before any test module imports settings."""
import os

# Must be set before any settings class is instantiated.
# All RuntimeAppSettings subclasses (WorkerSettings, BotSettings, APISettings)
# require OPERATOR_TIMEZONE. Setting it here covers unit and integration tests.
os.environ.setdefault("OPERATOR_TIMEZONE", "America/Los_Angeles")
