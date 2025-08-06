"""
Configuration management using Dynaconf.
"""

from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="SPEEDDATING",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    validators=[
        # Basic validation rules
        {"name": "SECRET_KEY", "must_exist": True},
        {"name": "DATABASE_URL", "default": "sqlite+aiosqlite:///./speed_dating.db"},
        {"name": "DEBUG", "default": False, "cast": bool},
    ],
)
