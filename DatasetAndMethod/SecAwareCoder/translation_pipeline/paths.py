from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_work_dir() -> Path:
    return get_project_root() / "translation_work"


def ensure_work_dirs() -> dict[str, Path]:
    work_dir = get_work_dir()
    dirs = {
        "work": work_dir,
        "cache": work_dir / "cache",
        "temp": work_dir / "temp",
        "sandbox": work_dir / "sandbox",
        "logs": work_dir / "logs",
        "outputs": work_dir / "outputs",
        "downloads": work_dir / "downloads",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
