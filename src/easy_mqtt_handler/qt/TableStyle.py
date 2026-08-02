"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/TableStyle.py
*
*  Shared helpers for how the tables look.
*
*  Copyright (C) 2026 AtmanActive
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QComboBox, QLineEdit

# extra pixels of room, above and below the content, in each cell and the header
CELL_PADDING = 3


class RowJumpBox(QLineEdit):
    """A narrow box that jumps the selection to a row by its number.

    Type a row number and press Return: if the table has that row (counting the
    first row as 1), it is scrolled into view and selected, and the number is
    left in the box. Anything that does not name an existing row — an empty box,
    stray characters, a number past the last row — is silently ignored and the
    box is cleared. The caller supplies the (already translated) tool tip, so
    this stays free of any gettext domain.
    """

    def __init__(self, table, tooltip=""):
        super().__init__()
        self._table = table
        # three digits is plenty of rows, and keeps the box narrow
        self.setMaxLength(3)
        self.setFixedWidth(48)
        self.setAlignment(Qt.AlignRight)
        if tooltip:
            self.setToolTip(tooltip)
        self.returnPressed.connect(self.jump_to_row)

    def jump_to_row(self):
        text = self.text().strip()
        # an empty box, stray characters or a row that does not exist all end the
        # same way: clear the box and do nothing
        if not text.isdigit():
            self.clear()
            return
        number = int(text)
        if number < 1 or number > self._table.rowCount():
            self.clear()
            return

        row = number - 1
        self._table.selectRow(row)
        # scroll through the model index, which works whether or not the first
        # cell holds a QTableWidgetItem (some columns are cell widgets)
        index = self._table.model().index(row, 0)
        self._table.scrollTo(index, QAbstractItemView.PositionAtCenter)


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
