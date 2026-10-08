from pathlib import Path

from pulse.config.project_config import init_project_config, load_project_config
from pulse.store.db import connect, default_db_path


def test_sqlite_file_is_created_on_init(tmp_path: Path):
    init_project_config(tmp_path)
    assert default_db_path().is_file()
    assert not (tmp_path / ".pulse" / "config.yaml").exists()
    config = load_project_config(tmp_path)
    assert config is not None
    connection = connect(default_db_path())
    row = connection.execute(
        "SELECT root_path FROM projects WHERE id = ?",
        (config.project_id,),
    ).fetchone()
    connection.close()
    assert Path(row["root_path"]) == tmp_path.resolve()
