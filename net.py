# File: urix/utils/net.py

from __future__ import annotations
import http.client


def is_online(timeout: float = 1.5) -> bool:
   
    try:
        conn = http.client.HTTPSConnection("clients3.google.com", timeout=timeout)
        conn.request("GET", "/generate_204")
        resp = conn.getresponse()
        return resp.status == 204
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


