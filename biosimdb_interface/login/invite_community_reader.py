#!/usr/bin/env python
"""Automatically invite logged in user to BioSimDB."""

import requests
from flask import current_app


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
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()

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
    user_id = _fetch_user_id(access_token)
    api_base = current_app.config.get("API_BASE", "").rstrip("/")
    headers = {"Authorization": f"Bearer {access_token}"}

    r = requests.get(api_base + "/communities/" + slug, headers=headers)
    community_id = r.json()["id"]

    r = requests.get(
        api_base + "/communities/" + community_id + "/members",
        params={"size": 1000},
        headers=headers,
    )
    found = False
    for m in r.json()["hits"]["hits"]:
        if m["member"]["id"] == str(user_id):
            found = True
    if found:
        pass
    else:
        data = {"members": [{"id": user_id, "type": "user"}], "role": "reader"}
        requests.post(
            api_base + "/communities/" + community_id + "/invitations",
            json=data,
            headers=headers,
        )
