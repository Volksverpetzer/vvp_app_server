"""Helper to create tasks on the Asana board."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

ASANA_TASKS_URL = "https://app.asana.com/api/1.0/tasks"


def create_asana_task(name: str, notes: str) -> bool:
    """Create a task on the configured Asana project.

    Requires the environment variables ASANA_TOKEN (personal access token)
    and ASANA_PROJECT_GID (gid of the board the task is added to).

    Returns:
        True if the task was created successfully, False otherwise.
    """
    token = os.environ.get("ASANA_TOKEN")
    project_gid = os.environ.get("ASANA_PROJECT_GID")
    if not token or not project_gid:
        logger.error("Asana is not configured (ASANA_TOKEN / ASANA_PROJECT_GID)")
        return False

    try:
        response = requests.post(
            ASANA_TASKS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "data": {
                    "name": name,
                    "notes": notes,
                    "projects": [project_gid],
                }
            },
            timeout=10,
        )
    except requests.RequestException as error:
        logger.error("Error creating Asana task: %s", error)
        return False

    if response.status_code != 201:
        logger.error(
            "Asana task creation failed (%s): %s",
            response.status_code,
            response.text[:500],
        )
        return False
    return True
