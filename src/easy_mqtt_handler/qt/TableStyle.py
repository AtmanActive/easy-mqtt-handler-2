"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/TableStyle.py
*
*  Shared helpers for how the tables look.
*
*  Copyright (C) 2026 AtmanActive
"""

# extra pixels of room, above and below the content, in each cell and the header
CELL_PADDING = 3


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
