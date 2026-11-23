"""Reviewed user goals, acceptance conditions, public setup and program checks.

Reference recipes implement these specifications for the pinned standard answer. Goals are authored here and are never
produced by translating a recorded click trace. Every episode's runtime has its own exchange folders: the inputs are
uploaded into the inbox before the first goal, outputs are saved into the outbox, and goals name exact paths and values.
"""
import spec_accounts
import spec_transactions
import spec_managers
import spec_program
import spec_finance
import spec_reports
import spec_exchange
import spec_settings
import spec_lifecycle
import spec_views
import spec_extended


def build():
    episodes = []
    for module in (spec_accounts, spec_transactions, spec_managers, spec_program, spec_finance, spec_reports, spec_exchange, spec_settings, spec_lifecycle, spec_views, spec_extended):
        episodes.extend(module.build())
    return episodes
