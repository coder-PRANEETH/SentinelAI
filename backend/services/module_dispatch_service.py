import os
import requests

from typing import Dict, Any


def dispatch_incident_to_modules(incident: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Dispatch a prepared incident to SentinelAI modules or webhook endpoints.

    If a module webhook URL is configured via environment variables, the incident is POSTed
    as JSON to the webhook. Otherwise the incident is marked as queued.
    """
    module_endpoints = {
        "city_memory_engine": {
            "webhook_env": "CITY_MEMORY_WEBHOOK_URL",
            "name": "City Memory Engine",
        },
        "risk_intelligence_engine": {
            "webhook_env": "RISK_INTELLIGENCE_WEBHOOK_URL",
            "name": "Risk Intelligence Engine",
        },
        "resource_command_center": {
            "webhook_env": "RESOURCE_COMMAND_WEBHOOK_URL",
            "name": "Resource Command Center",
        },
    }

    result = {}

    for module_key, module_info in module_endpoints.items():
        webhook_url = os.getenv(module_info["webhook_env"], "").strip()
        module_name = module_info["name"]

        if not webhook_url:
            result[module_key] = {
                "status": "queued",
                "message": f"Incident ready for {module_name}",
            }
            continue

        try:
            response = requests.post(webhook_url, json=incident, timeout=10)
            if 200 <= response.status_code < 300:
                result[module_key] = {
                    "status": "sent",
                    "message": f"Incident sent to {module_name}",
                }
            else:
                result[module_key] = {
                    "status": "failed",
                    "message": (
                        f"Failed to send incident to {module_name}: "
                        f"HTTP {response.status_code}"
                    ),
                }
        except Exception as exc:
            result[module_key] = {
                "status": "failed",
                "message": f"Failed to send incident to {module_name}: {str(exc)}",
            }

    return result
