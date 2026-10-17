"""The SDK's checks for a data plugin of an event-contract venue, run
unchanged against this plugin's own conversion
(`meridian.roles.data.testing.EventContractsChecks`): the data suite, the
venue's work past the suite's cases, its outcomes, and the pages.
tests/venue_cases.py names Polymarket's synthetic exchange for each."""

from __future__ import annotations

from meridian.roles.data.testing import EventContractsChecks

import venue_cases


class TestEventContracts(EventContractsChecks):
    venue = venue_cases
