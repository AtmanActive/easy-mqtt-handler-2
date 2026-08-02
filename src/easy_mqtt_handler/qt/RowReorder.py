"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/RowReorder.py
*
*  Shared "move the selected row" controls for the editor tables.
*
*  Copyright (C) 2026 AtmanActive
"""

from PyQt5.QtWidgets import QPushButton

from easy_mqtt_handler.qt.TableStyle import NarrowNumberBox


class RowReorderMixin:
    """Adds "move the selected row" buttons and a position box to a table tab.

    Reordering goes through the saved data and a full rebuild, exactly as the
    Duplicate button does, so the cell widgets never end up bound to the wrong
    row. A tab mixes this in and provides four small hooks onto its own data
    store: ``_capture_rows`` (snapshot the table into the store), ``_get_rows``
    (a list copy of the stored rows), ``_set_rows`` (write a list back) and
    ``_changed`` (announce an edit). It also has a ``self.table``.
    """

    # --- controls -----------------------------------------------------------

    def build_reorder_controls(self, up_tip, down_tip, top_tip, bottom_tip, position_tip):
        """Create the four move buttons and the position box, wired up.

        Returns them in the order they should sit in the button bar, so the tab
        can drop them straight into its layout.
        """
        self.move_up_button = self._reorder_button("▲", up_tip, self.move_row_up)
        self.move_down_button = self._reorder_button("▼", down_tip, self.move_row_down)
        self.move_top_button = self._reorder_button("╤", top_tip, self.move_row_to_top)
        self.move_bottom_button = self._reorder_button("╧", bottom_tip, self.move_row_to_bottom)

        self.position_box = NarrowNumberBox(position_tip)
        self.position_box.returnPressed.connect(self.move_row_to_position)

        return [self.move_up_button, self.move_down_button, self.move_top_button,
                self.move_bottom_button, self.position_box]

    @staticmethod
    def _reorder_button(glyph, tooltip, handler):
        button = QPushButton(glyph)
        button.setFixedWidth(32)
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        return button

    # --- moves --------------------------------------------------------------

    def move_row_up(self):
        source = self.table.currentRow()
        if source >= 0:
            self._apply_move(source, source - 1)

    def move_row_down(self):
        source = self.table.currentRow()
        if source >= 0:
            self._apply_move(source, source + 1)

    def move_row_to_top(self):
        source = self.table.currentRow()
        if source >= 0:
            self._apply_move(source, 0)

    def move_row_to_bottom(self):
        source = self.table.currentRow()
        if source >= 0:
            self._apply_move(source, self.table.rowCount() - 1)

    def move_row_to_position(self):
        source = self.table.currentRow()
        number = self.position_box.value()
        # a move needs a selected row and a position that exists; otherwise the
        # request cannot be satisfied, so clear the box and do nothing
        if source < 0 or number is None or number < 1 or number > self.table.rowCount():
            self.position_box.clear()
            return
        # a satisfiable request leaves the number in the box, whether or not the
        # row actually had to move (asking for its current position is a no-op)
        self._apply_move(source, number - 1)

    def _apply_move(self, source, destination):
        """Move the row at ``source`` to ``destination``, rebuilding the table.

        Returns True if a move happened. A destination that clamps to where the
        row already is (moving up from the top, down from the bottom, or to its
        own position) does nothing and does not mark the settings as changed.
        """
        self._capture_rows()
        rows = self._get_rows()
        if source < 0 or source >= len(rows):
            return False

        destination = max(0, min(destination, len(rows) - 1))
        if destination == source:
            return False

        rows.insert(destination, rows.pop(source))
        self._set_rows(rows)

        self.reload_from_settings()
        self.table.selectRow(destination)
        self._changed()
        return True
