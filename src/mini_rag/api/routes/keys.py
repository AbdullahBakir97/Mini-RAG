from fastapi import APIRouter, Response, status

from mini_rag.api.dependencies import ADMIN, AuthServiceDep, PrincipalDep, SettingsDep
from mini_rag.api.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyRequest,
    ApiKeyResponse,
    KeyIdPath,
    MeResponse,
    error_responses,
)
from mini_rag.core.errors import ApiKeyNotFound
from mini_rag.domain.models import ApiKey

router = APIRouter(prefix="/api/v1", tags=["keys"])


def _key(key: ApiKey) -> dict:
    return {"id": key.id, "name": key.name, "prefix": key.prefix, "scopes": list(key.scopes),
            "created_at": key.created_at, "last_used_at": key.last_used_at,
            "revoked_at": key.revoked_at}


@router.get("/me", summary="The tenant and scopes of the API key used")
async def me(principal: PrincipalDep, settings: SettingsDep) -> MeResponse:
    return MeResponse(tenant=principal.tenant_name, scopes=sorted(principal.scopes),
                      key_id=principal.key_id, auth_enabled=settings.AUTH_ENABLED)


@router.get("/keys", dependencies=[ADMIN], summary="The tenant's API keys, newest first")
async def list_keys(principal: PrincipalDep, service: AuthServiceDep) -> list[ApiKeyResponse]:
    return [ApiKeyResponse(**_key(key)) for key in await service.list_keys(principal.tenant_id)]


@router.post("/keys", dependencies=[ADMIN], status_code=status.HTTP_201_CREATED,
             summary="Create an API key for the tenant",
             description="The key is returned only once; only a hash of it is stored.")
async def create_key(request: ApiKeyRequest, principal: PrincipalDep,
                     service: AuthServiceDep) -> ApiKeyCreatedResponse:
    record, key = await service.create_key(principal.tenant_id, request.name, request.scopes)
    return ApiKeyCreatedResponse(**_key(record), key=key)


@router.delete("/keys/{key_id}", dependencies=[ADMIN], status_code=status.HTTP_204_NO_CONTENT,
               summary="Revoke an API key", description="It stops working at once.",
               responses=error_responses(ApiKeyNotFound))
async def revoke_key(key_id: KeyIdPath, principal: PrincipalDep,
                     service: AuthServiceDep) -> Response:
    await service.revoke_key(principal.tenant_id, str(key_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
