#!/usr/bin/env python
"""Automatically invite logged in user to BioSimDB."""

import requests
from flask import current_app

from biosimdb_interface.core.errors import ExternalAPIError

INVITE_ALREADY_MEMBER = "already_member"
INVITE_SENT = "invited"
INVITE_FAILED = "invite_failed"
INVITE_PENDING = "invite_pending"


def _fetch_user_id(access_token: str):
    """
    Fetch the logged in user ID.
    Args:
        access_token (str): OAuth2 bearer token for the authenticated user.

    Returns:
        int | None: Invenio instance user ID if found, or None.

    """
    api_base = current_app.config.get("API_BASE", "").rstrip("/")
    url = f"{api_base}/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict):
        if data.get("id"):
            return data["id"]
    else:
        return None


def invite_user(slug: str, access_token: str):
    """
    Check if a logged in user is a member of an Invenio instance community.
    Add the user if they are not a member of biosimdb.

    Args:
        user_id (int): Invenio instance user ID.
        slug (str): Name of the community in the Invenio instance.
        access_token (str): OAuth2 bearer token for the authenticated user.
    """
    try:
        user_id = _fetch_user_id(access_token)
        api_base = current_app.config.get("API_BASE", "").rstrip("/")

        service_headers = {
            "Authorization": f"Bearer {current_app.config['BIOSIMDB_SERVICE_TOKEN']}"
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        r = requests.get(api_base + "/communities/" + slug, headers=headers, timeout=10)
        r.raise_for_status()
        community_id = r.json()["id"]

        r = requests.get(
            api_base + "/communities/" + community_id + "/members",
            params={"size": 10000},
            headers=service_headers,
            timeout=10,
        )
        r.raise_for_status()

        found = any(m["member"]["id"] == str(user_id) for m in r.json()["hits"]["hits"])
        if found:
            return INVITE_ALREADY_MEMBER

        data = {"members": [{"id": str(user_id), "type": "user"}], "role": "reader"}
        r = requests.post(
            api_base + "/communities/" + community_id + "/invitations",
            json=data,
            headers=service_headers,
            timeout=10,
        )
        if r.ok:
            return INVITE_SENT
        if r.status_code == 400 and "already added or invited" in r.text:
            current_app.logger.debug("User %s already invited to %s", user_id, slug)
            return INVITE_PENDING

        current_app.logger.error(
            "Community invitation failed: %s %s", r.status_code, r.text
        )
        return INVITE_FAILED

    except requests.HTTPError as exc:
        current_app.logger.error(
            "Request failed: %s %s", exc.response.status_code, exc.response.text
        )
        raise ExternalAPIError(
            f"Community service returned {exc.response.status_code}"
        ) from exc
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        current_app.logger.exception("Community service request failed")
        raise ExternalAPIError("Could not reach the community service") from exc
