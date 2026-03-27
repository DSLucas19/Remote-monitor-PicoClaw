import http.client
import socket


def probe_http_then_tcp(host: str, port: int, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        connection = http.client.HTTPConnection(host=host, port=port, timeout=timeout)
        connection.request("GET", "/")
        response = connection.getresponse()
        response.read()
        connection.close()
        return True, f"http:{response.status}"
    except Exception as http_exc:
        http_error = str(http_exc)

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "tcp:open"
    except Exception as tcp_exc:
        return False, f"http:{http_error}; tcp:{tcp_exc}"

