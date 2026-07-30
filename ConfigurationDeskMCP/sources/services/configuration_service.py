# -*- coding: utf-8 -*-
"""Application configuration service."""

from __future__ import annotations

from configurationdesk_com_bridge import get_connection
from configurationdesk_com_bridge.domains import configuration_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.services._pagination import DEFAULT_PAGE_LIMIT, paginate
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def list_configuration(offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT) -> str:
    try:
        conn = get_connection()
        config = await dispatch_observation(configuration_com.list_configuration, conn)
        page = paginate(config, offset=offset, limit=limit)
        return success_response(configuration=page.items, **page.response_metadata())
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing configuration")
        return error_response(str(e), transient=False)
