import builtins
from typing import Any, Callable

import numpy as np
from PySide6.QtGui import QColor, QDoubleValidator, QIntValidator
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    QAbstractTableModel, 
    QEventLoop,
    QModelIndex, 
    QPersistentModelIndex
)

from PySide6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QLabel,
    QMainWindow,
    QLineEdit,
    QScrollArea,
    QTableView,
    QVBoxLayout,
)

from tomdemos.common.parameters import Parameter, Parameters


CLEAR_FIELD_STYLE = ""
INVALID_FIELD_STYLE = "background-color: rgb(128, 96, 96);"
INVALID_TABLE_STYLE = "QTableView { border: 1px solid rgb(160, 64, 64); }"

# 50 pixels less than an 800px wide host window
MAX_LABEL_WIDTH = 750

# starting width in px
PARAM_WINDOW_WIDTH = 500
PARAM_WINDOW_HEIGHT = 800


def color_invalid_field(control: QLineEdit, param: Parameter, parser: Callable[[str], Any]) -> None:
    if not control.hasAcceptableInput():
        control.setStyleSheet(INVALID_FIELD_STYLE)
        return

    value = parser(control.text())
    if not param.accepts(value):
        control.setStyleSheet(INVALID_FIELD_STYLE)
        return

    control.setStyleSheet(CLEAR_FIELD_STYLE)


def color_invalid_table(control: QTableView, invalid: bool) -> None:
    control.setStyleSheet(INVALID_TABLE_STYLE if invalid else CLEAR_FIELD_STYLE)


def single_field_write(control: QLineEdit, param: Parameter, parser: Callable[[str], Any]) -> None:
    value = parser(control.text())

    if not param.accepts(value):
        return

    param.value = value
    param.dirty()


class TableModel(QAbstractTableModel):
    _working_data: list[list[Any]]
    _committed_data: list[list[Any]]

    def __init__(self, param: Parameter, set_invalid_style: Callable[[bool], None] | None = None) -> None:
        super().__init__()
        self._param = param
        self._set_invalid_style = set_invalid_style
        self._working_data = self._mutable_table_data(param.value)
        self._committed_data = self._mutable_table_data(param.value)
        self._dirty_cells: set[tuple[int, int]] = set()
        self._invalid_cells: set[tuple[int, int]] = set()

    @classmethod
    def _copy_cell_value(cls, value: Any) -> Any:
        if type(value) is list:
            return [cls._copy_cell_value(item) for item in value]

        if type(value) is tuple:
            return tuple(cls._copy_cell_value(item) for item in value)

        if type(value) is dict:
            return {key: cls._copy_cell_value(item) for key, item in value.items()}

        return value

    @classmethod
    def _mutable_table_data(cls, data: Any) -> list[list[Any]]:
        return [
            [cls._copy_cell_value(cell) for cell in row]
            for row in data
        ]

    @classmethod
    def _coerce_value(cls, template: Any, value: Any) -> Any:
        if type(template) is list:
            if type(value) not in (builtins.list, builtins.tuple):
                raise ValueError(value)

            items = list(value)
            if len(template) != len(items):
                raise ValueError(value)

            return [cls._coerce_value(child_template, item) for child_template, item in zip(template, items, strict=True)]

        if type(template) is tuple:
            if type(value) not in (builtins.list, builtins.tuple):
                raise ValueError(value)

            items = list(value)
            if len(template) != len(items):
                raise ValueError(value)

            return tuple(cls._coerce_value(child_template, item) for child_template, item in zip(template, items, strict=True))

        if type(template) is dict:
            if type(value) is not dict:
                raise ValueError(value)
            return {key: cls._copy_cell_value(item) for key, item in value.items()}

        if type(template) is str:
            return str(value)

        return type(template)(value)

    @staticmethod
    def _strip_optional_wrappers(raw_value: str) -> str:
        stripped = raw_value.strip()
        if len(stripped) >= 2 and ((stripped[0], stripped[-1]) in (("[", "]"), ("(", ")"))):
            return stripped[1:-1].strip()
        return stripped

    @staticmethod
    def _split_collection_text(raw_value: str) -> list[str]:
        if not raw_value:
            return []

        parts: list[str] = []
        current: list[str] = []
        closing_by_opening = {"[": "]", "(": ")", "{": "}"}
        stack: list[str] = []
        quote: str | None = None
        escape = False

        for char in raw_value:
            if quote is not None:
                current.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if char in ('"', "'"):
                quote = char
                current.append(char)
                continue

            if char in closing_by_opening:
                stack.append(closing_by_opening[char])
                current.append(char)
                continue

            if stack and char == stack[-1]:
                stack.pop()
                current.append(char)
                continue

            if char == "," and not stack:
                parts.append("".join(current).strip())
                current = []
                continue

            current.append(char)

        if quote is not None or stack:
            raise ValueError(raw_value)

        last = "".join(current).strip()
        if last or parts:
            parts.append(last)
        return parts

    @classmethod
    def _parse_text_value(cls, raw_value: str, template: Any) -> Any:
        if type(template) is list:
            items = cls._split_collection_text(cls._strip_optional_wrappers(raw_value))
            if len(items) != len(template):
                raise ValueError(raw_value)
            return [cls._parse_text_value(item, child_template) for child_template, item in zip(template, items, strict=True)]

        if type(template) is tuple:
            items = cls._split_collection_text(cls._strip_optional_wrappers(raw_value))
            if len(items) != len(template):
                raise ValueError(raw_value)
            return tuple(cls._parse_text_value(item, child_template) for child_template, item in zip(template, items, strict=True))

        if type(template) is dict:
            raise ValueError(raw_value)

        if type(template) is str:
            stripped = raw_value.strip()
            if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
                return stripped[1:-1]
            return raw_value

        return type(template)(raw_value.strip())

    @classmethod
    def _freeze_table_data(cls, template: Any, rows: list[list[Any]]) -> Any:
        frozen_rows = []
        for template_row, row in zip(template, rows, strict=True):
            frozen_row = [
                cls._coerce_value(template_cell, cell)
                for template_cell, cell in zip(template_row, row, strict=True)
            ]
            frozen_rows.append(tuple(frozen_row) if type(template_row) is tuple else frozen_row)

        return tuple(frozen_rows) if type(template) is tuple else frozen_rows

    def _refresh_invalid_style(self) -> None:
        if self._set_invalid_style is not None:
            self._set_invalid_style(bool(self._dirty_cells or self._invalid_cells))

    def _emit_all_data_changed(self) -> None:
        row_count = self.rowCount()
        column_count = self.columnCount()
        if row_count == 0 or column_count == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(row_count - 1, column_count - 1),
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
                Qt.ItemDataRole.BackgroundRole,
            ],
        )

    def _parse_value(self, raw_value: str, current_value: Any) -> Any:
        return self._parse_text_value(raw_value, current_value)

    def data(self, index, role=0):
        if not index.isValid():
            return None

        value = self._working_data[index.row()][index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return str(value)

        if role == Qt.ItemDataRole.BackgroundRole and (index.row(), index.column()) in self._invalid_cells.union(self._dirty_cells):
            return QColor(128, 96, 96)

        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def setData(self, index, value, role: int = int(Qt.ItemDataRole.EditRole)):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        row = index.row()
        column = index.column()
        cell = (row, column)

        try:
            parsed_value = self._parse_value(str(value), self._working_data[row][column])
        except (SyntaxError, TypeError, ValueError):
            self._invalid_cells.add(cell)
            self._refresh_invalid_style()
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.BackgroundRole])
            return False

        self._invalid_cells.discard(cell)
        self._working_data[row][column] = parsed_value

        if parsed_value == self._committed_data[row][column]:
            self._dirty_cells.discard(cell)
        else:
            self._dirty_cells.add(cell)

        candidate_value = self._freeze_table_data(self._param.value, self._working_data)
        if self._param.accepts(candidate_value):
            self._param.value = candidate_value
            self._committed_data = self._mutable_table_data(candidate_value)
            self._working_data = self._mutable_table_data(candidate_value)
            self._dirty_cells.clear()
            self._param.dirty()

        self._refresh_invalid_style()
        self._emit_all_data_changed()
        return True

    # huge fucking weird folderol here just to make the base type interface happy
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._working_data)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or not self._working_data else len(self._working_data[0])


class ParametersWindow(QMainWindow):
    parameters: Parameters

    @staticmethod
    def un_numpy(value: Any) -> Any:
        try:
            return value.item()
        except:
            return value


    def __init__(self, parameters: Parameters):
        super().__init__()
        self.parameters = parameters

        self.setWindowTitle("Demo Parameters")
        self.resize(PARAM_WINDOW_WIDTH, PARAM_WINDOW_HEIGHT)

        widget = QWidget()
        layout = QVBoxLayout()

        for param in self.parameters:
            new_control: QWidget

            match type(param.value):
                case builtins.list | builtins.tuple:
                    table_control = QTableView()
                    table_control.setModel(
                        TableModel(
                            param,
                            lambda invalid, control=table_control: color_invalid_table(control, invalid),
                        )
                    )
                    table_control.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
                    table_control.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    table_control.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    table_control.adjustSize()
                    new_control = table_control

                case builtins.int | np.uint8 | np.uint16 | np.uint32 | np.uint64:
                    new_control = QLineEdit()
                    value = self.un_numpy(param.value)
                    new_control.setValidator(QIntValidator(new_control))
                    new_control.setText(str(value))
                    new_control.textEdited.connect(
                        lambda _text, control=new_control, param=param: color_invalid_field(control, param, int))
                    new_control.editingFinished.connect(
                        lambda control=new_control, 
                        param=param: single_field_write(control, param, int))

                case builtins.float | np.float16 | np.float32 | np.float64:
                    new_control = QLineEdit()
                    value = self.un_numpy(param.value)
                    validator = QDoubleValidator(new_control)
                    validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                    new_control.setValidator(validator)
                    new_control.setText(str(value))
                    new_control.textEdited.connect(
                        lambda _text, control=new_control, param=param: color_invalid_field(control, param, float))
                    new_control.editingFinished.connect(
                        lambda control=new_control, 
                        param=param: single_field_write(control, param, float))

                case builtins.dict | builtins.str | _:
                    new_control = QLineEdit()
                    new_control.setText(str(param.value))
                    new_control.textEdited.connect(
                        lambda _text, control=new_control, param=param: color_invalid_field(control, param, str))
                    new_control.editingFinished.connect(
                        lambda control=new_control, 
                        param=param: single_field_write(control, param, str))
                    if type(param.value) is dict:
                        raise NotImplemented("TODO: support freeform edits")

            new_container = QWidget()

            new_layout = QVBoxLayout()
            new_layout.addWidget(QLabel(param.name))
            if param.description:
                new_label = QLabel(param.description)
                new_label.setWordWrap(True)
                new_label.setMaximumWidth(MAX_LABEL_WIDTH)
                new_layout.addWidget(new_label)

            new_layout.addWidget(new_control)
            new_container.setLayout(new_layout)
            new_layout.activate()
            new_container.adjustSize()

            layout.addWidget(new_container)

        widget.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)

        self.setCentralWidget(scroll)
        self.resize(
            PARAM_WINDOW_WIDTH, 
            min(
                layout.sizeHint().height(), 
                PARAM_WINDOW_HEIGHT))


class Application:
    application: QApplication
    event_loop: QEventLoop

    @classmethod
    def create(cls):
        cls.application = QApplication()

    @classmethod
    def tick(cls):
        cls.event_loop.processEvents(
            QEventLoop.ProcessEventsFlag.AllEvents,
            2 # 2ms
        )

    @classmethod
    def start_window(cls, window: ParametersWindow):
        cls.application.setActiveWindow(window)
        cls.event_loop = QEventLoop(cls.application)
        window.show()
