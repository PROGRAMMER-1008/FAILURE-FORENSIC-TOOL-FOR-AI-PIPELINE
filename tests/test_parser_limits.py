import sys
import pytest
from ffv2.uploads import isolated_extract


@pytest.mark.enable_socket
def test_bounded_parser_process_extracts_text():
    assert (
        isolated_extract(b"Invented parser resource test", "text/plain", 100, 128)
        == "Invented parser resource test"
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="RLIMIT enforcement is Linux-only; hosted target is Linux"
)
def test_linux_memory_limit_denies_large_allocation():
    import subprocess

    program = """
from ffv2 import uploads
class Connection:
    def send(self, value):
        assert value == (False, 'Document parser resource limit exceeded')
    def close(self):
        pass
uploads.extract = lambda *args: bytearray(256 * 1024 * 1024)
uploads._child(Connection(), b'', 'text/plain', 100, 128)
print('resource-limit-enforced')
"""
    result = subprocess.run([sys.executable, "-c", program], capture_output=True)
    assert result.returncode == 0
    assert b"resource-limit-enforced" in result.stdout
