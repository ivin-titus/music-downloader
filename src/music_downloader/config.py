from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime paths and configuration for the archive."""

    root_dir: Path

    @property
    def app_data_dir(self) -> Path:
        return self.root_dir / "app_data"

    @property
    def music_dir(self) -> Path:
        return self.root_dir / "music_files"

    @property
    def cache_dir(self) -> Path:
        return self.app_data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.app_data_dir / "logs"

    @property
    def state_dir(self) -> Path:
        return self.app_data_dir / "state"

    @property
    def database_path(self) -> Path:
        return self.app_data_dir / "music_downloader.db"

    def ensure_directories(self) -> None:
        for directory in (
            self.app_data_dir,
            self.music_dir,
            self.cache_dir,
            self.logs_dir,
            self.state_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def default_settings() -> Settings:
    return Settings(
        root_dir=Path.home() / "music_downloader",
    )
