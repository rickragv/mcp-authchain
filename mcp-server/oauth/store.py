"""In-memory OAuth storage for client registrations, auth codes, and refresh tokens."""

import secrets
import time
from dataclasses import dataclass, field


@dataclass
class ClientRegistration:
    client_id: str
    client_secret: str | None
    redirect_uris: list[str]
    client_name: str
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str
    created_at: float = field(default_factory=time.time)


@dataclass
class AuthorizationCode:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    firebase_uid: str
    firebase_email: str | None
    firebase_role: str
    firebase_scopes: list[str]
    created_at: float = field(default_factory=time.time)
    used: bool = False


@dataclass
class RefreshTokenRecord:
    token: str
    client_id: str
    firebase_uid: str
    firebase_email: str | None
    firebase_role: str
    firebase_scopes: list[str]
    created_at: float = field(default_factory=time.time)


class OAuthStore:
    """Thread-safe in-memory store. Replace with Firestore for production."""

    def __init__(self):
        self._clients: dict[str, ClientRegistration] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._refresh_tokens: dict[str, RefreshTokenRecord] = {}

    def register_client(
        self,
        client_name: str,
        redirect_uris: list[str],
        grant_types: list[str] | None = None,
        response_types: list[str] | None = None,
        token_endpoint_auth_method: str = "none",
    ) -> ClientRegistration:
        client_id = secrets.token_urlsafe(32)
        client_secret = secrets.token_urlsafe(48) if token_endpoint_auth_method != "none" else None
        reg = ClientRegistration(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=redirect_uris,
            client_name=client_name,
            grant_types=grant_types or ["authorization_code", "refresh_token"],
            response_types=response_types or ["code"],
            token_endpoint_auth_method=token_endpoint_auth_method,
        )
        self._clients[client_id] = reg
        return reg

    def get_client(self, client_id: str) -> ClientRegistration | None:
        return self._clients.get(client_id)

    def store_auth_code(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        firebase_uid: str,
        firebase_email: str | None,
        firebase_role: str,
        firebase_scopes: list[str],
    ) -> AuthorizationCode:
        code = secrets.token_urlsafe(48)
        record = AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            firebase_uid=firebase_uid,
            firebase_email=firebase_email,
            firebase_role=firebase_role,
            firebase_scopes=firebase_scopes,
        )
        self._auth_codes[code] = record
        return record

    def consume_auth_code(self, code: str, ttl: int = 300) -> AuthorizationCode | None:
        record = self._auth_codes.get(code)
        if not record:
            return None
        if record.used:
            return None
        if time.time() - record.created_at > ttl:
            del self._auth_codes[code]
            return None
        record.used = True
        return record

    def store_refresh_token(
        self,
        client_id: str,
        firebase_uid: str,
        firebase_email: str | None,
        firebase_role: str,
        firebase_scopes: list[str],
    ) -> RefreshTokenRecord:
        token = secrets.token_urlsafe(64)
        record = RefreshTokenRecord(
            token=token,
            client_id=client_id,
            firebase_uid=firebase_uid,
            firebase_email=firebase_email,
            firebase_role=firebase_role,
            firebase_scopes=firebase_scopes,
        )
        self._refresh_tokens[token] = record
        return record

    def consume_refresh_token(self, token: str, ttl: int = 86400) -> RefreshTokenRecord | None:
        record = self._refresh_tokens.pop(token, None)
        if not record:
            return None
        if time.time() - record.created_at > ttl:
            return None
        return record
