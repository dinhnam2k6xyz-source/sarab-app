import ipaddress
import socket
from urllib.parse import urlparse, urljoin
from typing import Tuple, Optional
import httpx
from app.core.config import settings


# Cloud metadata endpoints and dangerous hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "metadata",
}

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local & cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),              # Loopback
    ipaddress.ip_network("::ffff:0:0/96"),        # IPv4-mapped IPv6
    ipaddress.ip_network("100::/64"),
    ipaddress.ip_network("2001:db8::/32"),
    ipaddress.ip_network("fc00::/7"),             # Unique local
    ipaddress.ip_network("fe80::/10"),            # Link-local
    ipaddress.ip_network("ff00::/8"),             # Multicast
]


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked private/internal/cloud metadata range."""
    # Check if IPv6 is an IPv4-mapped address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return True

    for net in BLOCKED_IP_NETWORKS:
        if ip in net:
            return True
    return False


_DNS_SSRF_CACHE: dict = {}

def validate_url_ssrf(url_str: str) -> Tuple[bool, str]:
    """
    Validate that a URL is safe to fetch and does not attempt SSRF attack
    against private networks, localhost, or cloud metadata endpoints.
    Returns (is_safe, error_message).
    """
    if not url_str or not isinstance(url_str, str):
        return False, "URL không hợp lệ hoặc để trống."

    url_str = url_str.strip()
    try:
        parsed = urlparse(url_str)
    except Exception as e:
        return False, f"Không thể phân tích định dạng URL: {str(e)}"

    # 1. Validate scheme
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Giao thức '{parsed.scheme}' không được hỗ trợ. Chỉ hỗ trợ HTTP và HTTPS."

    # 2. Validate hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL thiếu tên miền (hostname)."

    hostname_lower = hostname.lower()

    if (
        hostname_lower in BLOCKED_HOSTNAMES
        or hostname_lower.endswith(".localhost")
        or hostname_lower.endswith(".local")
        or hostname_lower.endswith(".internal")
        or hostname_lower.endswith(".corp")
    ):
        return False, f"Tên miền '{hostname}' thuộc mạng nội bộ và bị từ chối vì lý do bảo mật."

    # 3. Check port if specified
    port = parsed.port
    if port and port not in (80, 443, 8080, 8443):
        return False, f"Cổng mạng '{port}' không được phép truy cập."

    # Check cache for previously validated hostname
    cache_key = f"{hostname_lower}:{port or (443 if parsed.scheme == 'https' else 80)}"
    if cache_key in _DNS_SSRF_CACHE:
        return _DNS_SSRF_CACHE[cache_key]

    # 4. Resolve DNS and check all IP addresses
    try:
        # Check direct IP literals first
        try:
            direct_ip = ipaddress.ip_address(hostname_lower)
            if is_ip_blocked(direct_ip):
                res = (False, f"Địa chỉ IP '{hostname}' là IP nội bộ/riêng tư, bị từ chối.")
                _DNS_SSRF_CACHE[cache_key] = res
                return res
        except ValueError:
            pass  # Not an IP literal, continue to DNS resolution

        addr_info = socket.getaddrinfo(hostname, port or (443 if parsed.scheme == "https" else 80), socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            res = (False, f"Không thể giải giải mã DNS cho tên miền '{hostname}'.")
            return res

        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if is_ip_blocked(ip_obj):
                res = (False, f"Tên miền '{hostname}' trỏ tới địa chỉ IP nội bộ ({ip_str}), bị từ chối bảo mật.")
                _DNS_SSRF_CACHE[cache_key] = res
                return res

        _DNS_SSRF_CACHE[cache_key] = (True, "")
        return True, ""
    except socket.gaierror:
        return False, f"Không tìm thấy máy chủ cho tên miền '{hostname}' (DNS failure)."
    except Exception as e:
        return False, f"Lỗi kiểm tra bảo mật máy chủ: {str(e)}"


async def safe_fetch_url(
    url: str,
    headers: Optional[dict] = None,
    timeout: Optional[float] = None,
    max_redirects: int = 5,
) -> httpx.Response:
    """
    Safely fetch a URL with SSRF checks on initial URL and each redirected URL.
    Enforces maximum payload size and timeout limits.
    """
    current_url = url
    redirect_count = 0
    timeout_val = timeout or float(settings.SCRAPER_TIMEOUT_SECONDS)

    default_headers = {
        "User-Agent": settings.SCRAPER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8,ja;q=0.7,zh-CN;q=0.6",
    }
    if headers:
        default_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout_val, follow_redirects=False) as client:
        while True:
            # Check SSRF on current target
            is_safe, error_msg = validate_url_ssrf(current_url)
            if not is_safe:
                raise ValueError(f"Chặn truy cập bảo mật SSRF: {error_msg}")

            response = await client.get(current_url, headers=default_headers)

            if response.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ValueError(f"Vượt quá số lần chuyển hướng cho phép ({max_redirects}).")
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Nhận được mã chuyển hướng nhưng thiếu Header Location.")
                current_url = urljoin(current_url, location)
                continue

            # Check response size
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > settings.SCRAPER_MAX_BODY_BYTES:
                raise ValueError("Nội dung phản hồi vượt quá kích thước tối đa cho phép (15MB).")

            return response
