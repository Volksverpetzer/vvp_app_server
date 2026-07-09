"""Helper to create tasks on the Asana board."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

ASANA_TASKS_URL = "https://app.asana.com/api/1.0/tasks"

# Optional per-category section gids; when set, tasks are placed in the
# matching section (column) of the board instead of the default one.
SECTION_ENV_VARS = {
    "report_fake": "ASANA_SECTION_REPORT_FAKE",
    "app_feedback": "ASANA_SECTION_APP_FEEDBACK",
    "other": "ASANA_SECTION_OTHER",
}


def create_asana_task(name: str, notes: str, category: str | None = None) -> bool:
    """Create a task on the configured Asana project.

    Requires the environment variables ASANA_TOKEN (personal access token)
    and ASANA_PROJECT_GID (gid of the board the task is added to). When a
    category is given and its ASANA_SECTION_* env var is set, the task is
    placed in that section of the board.

    Returns:
        True if the task was created successfully, False otherwise.
    """
    token = os.environ.get("ASANA_TOKEN")
    project_gid = os.environ.get("ASANA_PROJECT_GID")
    if not token or not project_gid:
        logger.error("Asana is not configured (ASANA_TOKEN / ASANA_PROJECT_GID)")
        return False

    data: dict = {
        "name": name,
        "notes": notes,
        "projects": [project_gid],
    }
    section_env = SECTION_ENV_VARS.get(category or "")
    section_gid = os.environ.get(section_env) if section_env else None
    if section_gid:
        data["memberships"] = [{"project": project_gid, "section": section_gid}]

    try:
        response = requests.post(
            ASANA_TASKS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"data": data},
            timeout=10,
        )
    except requests.RequestException as error:
        logger.error("Error creating Asana task: %s", error)
        return False

    if response.status_code != 201:
        # Don't log the response body at error level: Asana can echo
        # submitted fields (task notes/email) back in its error payload.
        logger.error("Asana task creation failed (status %s)", response.status_code)
        logger.debug("Asana error response body: %s", response.text[:500])
        return False
    return True
