import re
import subprocess


def test_no_secret_file_is_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    forbidden = re.compile(r"(^|/)\.env$|\.pem$|id_rsa|\.key$")

    assert not [path for path in tracked if forbidden.search(path)]
