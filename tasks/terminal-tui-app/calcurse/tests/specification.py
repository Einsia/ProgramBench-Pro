"""Public-interface episodes for calcurse 4.8.2."""
import spec_cli
import spec_recurrence
import spec_exchange
import spec_gui
import spec_interaction
import spec_offline

def build():
    return spec_cli.build() + spec_recurrence.build() + spec_exchange.build() + spec_interaction.build() + spec_gui.build() + spec_offline.build()
