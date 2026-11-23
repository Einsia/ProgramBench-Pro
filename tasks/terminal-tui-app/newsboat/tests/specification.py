"""Authored episodes; observations are frozen only after reference validation."""
import spec_parsing
import spec_filters
import spec_config
import spec_ui
import spec_rendering
import spec_storage
import spec_behavior
import spec_local
import spec_http


def build():
    return (spec_parsing.build() + spec_filters.build() + spec_config.build() + spec_ui.build()
            + spec_rendering.build() + spec_storage.build() + spec_behavior.build() + spec_local.build() + spec_http.build())
