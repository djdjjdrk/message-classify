from pathlib import Path
import subprocess
import sys


def test_frontend_starts_without_project_root_on_python_path(tmp_path):
    entrypoint = Path(__file__).resolve().parents[2] / "frontend" / "main.py"
    script = """
import sys
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(sys.argv[1], default_timeout=10).run()
assert not app.exception, [e.message for e in app.exception]
assert app.title[0].value == '登录'
app.switch_page('app_pages/register.py').run()
assert not app.exception, [e.message for e in app.exception]
assert app.title[0].value == '注册'
"""
    # 独立进程且禁用 cwd/PYTHONPATH，避免 pytest 的导入路径掩盖 CLI 启动错误。
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(entrypoint)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
