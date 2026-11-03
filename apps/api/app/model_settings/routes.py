from fastapi import APIRouter, Request

from app.http.dependencies import SessionDep
from app.model_settings.service import (
    ModelSettingsInput,
    ProfileInput,
    RevisionInput,
    activate_profile,
    delete_profile,
    draft_settings,
    list_profiles,
    probe_connection,
    profile_draft,
    public_settings,
    save_profile,
    save_settings,
)

router = APIRouter(prefix="/api")


@router.get("/settings/models")
def get_model_settings(request: Request, session: SessionDep):
    return public_settings(session, request.app.state.settings)


@router.post("/settings/models")
def update_model_settings(payload: ModelSettingsInput, request: Request, session: SessionDep):
    return save_settings(session, request.app.state.settings, payload)


@router.post("/settings/models/test")
def test_model_settings(payload: ModelSettingsInput, request: Request, session: SessionDep):
    candidate = draft_settings(session, request.app.state.settings, payload)
    return probe_connection(candidate)


@router.get("/settings/models/profiles")
def model_profiles(request: Request, session: SessionDep):
    return list_profiles(session, request.app.state.settings)


@router.post("/settings/models/profiles", status_code=201)
def create_model_profile(payload: ProfileInput, request: Request, session: SessionDep):
    return save_profile(session, request.app.state.settings, payload)


@router.post("/settings/models/profiles/test")
def test_new_profile(payload: ProfileInput, request: Request, session: SessionDep):
    return probe_connection(profile_draft(session, request.app.state.settings, payload))


@router.post("/settings/models/profiles/{profile_id}/update")
def update_model_profile(
    profile_id: str, payload: ProfileInput, request: Request, session: SessionDep
):
    return save_profile(session, request.app.state.settings, payload, profile_id)


@router.post("/settings/models/profiles/{profile_id}/test")
def test_saved_profile(
    profile_id: str, payload: ProfileInput, request: Request, session: SessionDep
):
    return probe_connection(profile_draft(session, request.app.state.settings, payload, profile_id))


@router.post("/settings/models/profiles/{profile_id}/activate")
def activate_model_profile(
    profile_id: str, payload: RevisionInput, request: Request, session: SessionDep
):
    return activate_profile(session, request.app.state.settings, profile_id, payload.revision)


@router.post("/settings/models/profiles/{profile_id}/delete")
def delete_model_profile(
    profile_id: str, payload: RevisionInput, request: Request, session: SessionDep
):
    return delete_profile(session, request.app.state.settings, profile_id, payload.revision)
