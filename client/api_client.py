"""REST-Client für The Bus Tracker Backend."""

from __future__ import annotations

from datetime import datetime

import httpx

from shared import LOCAL_API_URL


def format_api_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json().get("detail", "")
            if detail:
                if isinstance(detail, list):
                    parts = []
                    for item in detail:
                        msg = item.get("msg", str(item))
                        loc = ".".join(str(x) for x in item.get("loc", []))
                        parts.append(f"{loc}: {msg}" if loc else msg)
                    return "\n".join(parts) or exc.response.text
                return str(detail)
        except Exception:
            pass
        return f"Server {exc.response.status_code}: {exc.response.reason_phrase}"
    return str(exc)


class ApiClient:
    def __init__(self, base_url: str = LOCAL_API_URL):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.user_id: int | None = None
        self.username: str = ""
        self.display_name: str = ""
        self._client = httpx.Client(timeout=8.0)

    def close(self):
        self._client.close()

    def _headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> bool:
        try:
            r = self._client.get(self._url("/health"))
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def register(self, username: str, password: str, display_name: str = "") -> dict:
        r = self._client.post(
            self._url("/auth/register"),
            json={"username": username, "password": password, "display_name": display_name},
        )
        r.raise_for_status()
        data = r.json()
        self._apply_auth(data)
        return data

    def login(self, username: str, password: str) -> dict:
        r = self._client.post(
            self._url("/auth/login"),
            json={"username": username, "password": password},
        )
        r.raise_for_status()
        data = r.json()
        self._apply_auth(data)
        return data

    def _apply_auth(self, data: dict):
        self.token = data["access_token"]
        self.user_id = data["user_id"]
        self.username = data["username"]
        self.display_name = data["display_name"]

    def create_spedition(self, name: str, description: str = "") -> dict:
        r = self._client.post(
            self._url("/speditions"),
            json={"name": name.strip(), "description": description.strip()},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def list_speditions(self) -> list[dict]:
        r = self._client.get(self._url("/speditions"), headers=self._headers())
        r.raise_for_status()
        return r.json()

    def join_spedition(self, invite_code: str) -> dict:
        body = {"invite_code": invite_code.strip()}
        last_err: Exception | None = None
        for path in ("/speditions/join", "/join"):
            try:
                r = self._client.post(
                    self._url(path),
                    json=body,
                    headers=self._headers(),
                )
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code == 404 and path == "/speditions/join":
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("Beitritt fehlgeschlagen")

    def delete_spedition(self, spedition_id: int):
        r = self._client.delete(
            self._url(f"/speditions/{spedition_id}"),
            headers=self._headers(),
        )
        r.raise_for_status()

    def update_live(self, payload: dict):
        try:
            self._client.post(
                self._url("/live"),
                json=payload,
                headers=self._headers(),
                timeout=3.0,
            )
        except httpx.HTTPError:
            pass

    def get_live_drivers(self, spedition_id: int) -> list[dict]:
        r = self._client.get(
            self._url(f"/speditions/{spedition_id}/live"),
            headers=self._headers(),
            timeout=8.0,
        )
        r.raise_for_status()
        return r.json()

    def submit_trip(self, trip: dict, spedition_id: int | None = None) -> dict:
        body = {**trip, "spedition_id": spedition_id}
        for key in ("started_at", "ended_at"):
            if body.get(key) and isinstance(body[key], str):
                body[key] = datetime.fromisoformat(body[key].replace("Z", "+00:00"))
        r = self._client.post(
            self._url("/trips"),
            json=body,
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def get_stats(self, spedition_id: int) -> dict:
        r = self._client.get(
            self._url(f"/speditions/{spedition_id}/stats"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def get_app_version(self) -> dict | None:
        try:
            r = self._client.get(self._url("/app/version"), timeout=5.0)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        return None

    def get_my_bank(self) -> dict:
        r = self._client.get(self._url("/users/me/bank"), headers=self._headers())
        r.raise_for_status()
        return r.json()

    def get_spedition_bank(self, spedition_id: int) -> dict:
        r = self._client.get(
            self._url(f"/speditions/{spedition_id}/bank"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def get_members(self, spedition_id: int) -> list[dict]:
        r = self._client.get(
            self._url(f"/speditions/{spedition_id}/members"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def get_ranking(self, spedition_id: int) -> list[dict]:
        r = self._client.get(
            self._url(f"/speditions/{spedition_id}/ranking"),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()
