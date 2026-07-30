"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/TableStyle.py
*
*  Shared helpers for how the tables look.
*
*  Copyright (C) 2026 AtmanActive
"""

from PyQt5.QtWidgets import QComboBox

# extra pixels of room, above and below the content, in each cell and the header
CELL_PADDING = 3


class NoScrollComboBox(QComboBox):
    """A drop down that does not react to the mouse wheel while it sits in a cell.

    A plain QComboBox changes its value on every wheel notch, even when it is
    only along for the ride inside a scrolling table. That means scrolling the
    table silently rewrites the values of every drop down the pointer passes
    over. Ignoring the wheel event lets it bubble up to the table, which scrolls
    as the user expects, and leaves the drop down's value alone. The popup list
    is a separate widget, so it still scrolls normally once opened.
    """

    def wheelEvent(self, event):
        event.ignore()


def add_table_padding(table, padding=CELL_PADDING):
    """Give a table's rows and header a little more height, for readability.

    Done through geometry, never a style sheet. A style sheet on a QTableWidget
    switches the whole widget to style-sheet rendering, and on some Linux styles
    that blanks the cell backgrounds to white while the rest of the app stays
    dark. Growing the row and header heights avoids touching any colour.
    """
    extra = 2 * padding

    vertical_header = table.verticalHeader()
    vertical_header.setDefaultSectionSize(vertical_header.defaultSectionSize() + extra)

    horizontal_header = table.horizontalHeader()
    horizontal_header.setMinimumHeight(horizontal_header.sizeHint().height() + extra)
