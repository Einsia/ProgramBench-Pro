from evaluation.contract import manifest,load_frozen
import program_accounts,program_state,program_metadata,program_search,program_lists,program_permissions,program_media,program_catalogs,program_protocols,program_filesystem,program_scanner,program_kobo,program_extended


def build():
    episodes=[]
    for module in (program_accounts,program_state,program_metadata,program_search,program_lists,program_permissions,program_media,program_catalogs,program_protocols,program_filesystem,program_scanner,program_kobo,program_extended):episodes+=module.build()
    try:
        import specification
        episodes+=specification.build()
    except ModuleNotFoundError:
        pass
    return manifest(episodes)


def load(directory):return load_frozen(directory,build())
