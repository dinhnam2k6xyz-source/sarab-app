import pytest
from app.core.security import validate_url_ssrf, is_ip_blocked
import ipaddress


def test_ssrf_blocked_ips():
    assert is_ip_blocked(ipaddress.ip_address("127.0.0.1")) is True
    assert is_ip_blocked(ipaddress.ip_address("10.0.0.5")) is True
    assert is_ip_blocked(ipaddress.ip_address("192.168.1.1")) is True
    assert is_ip_blocked(ipaddress.ip_address("172.16.0.1")) is True
    assert is_ip_blocked(ipaddress.ip_address("169.254.169.254")) is True
    assert is_ip_blocked(ipaddress.ip_address("::1")) is True


def test_ssrf_blocked_hostnames():
    # Localhost
    safe, msg = validate_url_ssrf("http://localhost/chapter1")
    assert safe is False
    assert "nội bộ" in msg or "bị từ chối" in msg

    # Metadata
    safe, msg = validate_url_ssrf("http://metadata.google.internal/computeMetadata/v1")
    assert safe is False

    # 127.0.0.1
    safe, msg = validate_url_ssrf("http://127.0.0.1:8000/api")
    assert safe is False

    # Private IP
    safe, msg = validate_url_ssrf("http://192.168.1.100/novel")
    assert safe is False


def test_ssrf_invalid_schemes():
    safe, msg = validate_url_ssrf("ftp://example.com/novel.txt")
    assert safe is False
    assert "giao thức" in msg.lower() or "scheme" in msg.lower()

    safe, msg = validate_url_ssrf("file:///etc/passwd")
    assert safe is False


def test_ssrf_valid_public_domain():
    safe, msg = validate_url_ssrf("https://ncode.syosetu.com/n1234ab/")
    assert safe is True
    assert msg == ""
