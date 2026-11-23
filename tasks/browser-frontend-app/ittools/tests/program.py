'''Program episodes of ittools (no evaluator): one module per family of tools, collected here.'''
import fam_encode
import fam_ref
import fam_editors
import fam_misc
import fam_shell
import fam_files
import fam_dev
import fam_conv
import fam_format
import fam_gen
import fam_hash
import fam_network
import fam_parse
import fam_text
import fam_time
import fam_web

MODULES = [fam_hash, fam_encode, fam_format, fam_network, fam_parse, fam_text, fam_web, fam_gen, fam_time, fam_dev, fam_conv, fam_files, fam_misc, fam_ref, fam_editors, fam_shell]


def build():
    return [w for module in MODULES for w in module.build()]
