"""Tests for the BYD config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pybyd import BydAuthenticationError, BydError
import pytest

from custom_components.byd.const import (
    CONF_CONTROL_PIN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

USER_INPUT = {
    CONF_USERNAME: "driver@example.com",
    CONF_PASSWORD: "hunter2",
    CONF_CONTROL_PIN: "1234",
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """A valid login creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.byd.config_flow._validate_login",
        new=AsyncMock(return_value=None),
    ), patch(
        "custom_components.byd.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_USERNAME]
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "driver@example.com"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (BydAuthenticationError("bad creds"), "invalid_auth"),
        (BydError("network"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Login failures surface the correct error and keep the form open."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "custom_components.byd.config_flow._validate_login",
        new=AsyncMock(side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
