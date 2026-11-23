import gui_calc
import gui_dev
import gui_encode
import gui_format
import gui_measure
import gui_more
import gui_shell
import gui_text
import gui_tools


def build():
    return (gui_shell.build() + gui_tools.build() + gui_dev.build() + gui_text.build() + gui_more.build() + gui_encode.build()
            + gui_format.build() + gui_calc.build() + gui_measure.build())
