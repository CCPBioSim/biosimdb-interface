#!/usr/bin/env python
"""OAuth2 login services for BioSimDB."""

import secrets
from urllib.parse import urlencode

import requests
from flask import current_app, session


def fetch_user_email(access_token: str):
    """
    The function calls the configured user endpoint using the provided OAuth2
    access token and returns the email address when present in the response.

    Args:
        access_token (str): OAuth2 bearer token for the authenticated user.

    Returns:
        str | None: User email if found, otherwise None.
    """
    api_base = current_app.config.get("API_BASE", "").rstrip("/")
    urls = [f"{api_base}/me"]

    headers = {"Authorization": f"Bearer {access_token}"}

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()

            if isinstance(data, dict):
                if data.get("email"):
                    return data["email"]

        except Exception:
            continue

    return None


def authz_url() -> str:
    """
    Build the OAuth2 authorization URL with a secure random state parameter.

    Stores the state in the session for later verification in the callback.

    Returns:
        str: The full authorization URL to redirect the user to.
    """
    state = secrets.token_urlsafe(32)  # secure random string
    session["oauth_state"] = state  # store in session
    params = {
        "response_type": "code",
        "client_id": current_app.config["CLIENT_ID"],
        "redirect_uri": current_app.config["REDIRECT_URI"],
        "scope": current_app.config["SCOPES"],
        "state": state,
    }
    return f"{current_app.config['AUTH_URL']}?{urlencode(params)}"


def is_logged_in():
    """
    Check whether the user has an active access token in the session.

    Returns:
        bool: True if the user is logged in, False otherwise.
    """
    return "access_token" in session
