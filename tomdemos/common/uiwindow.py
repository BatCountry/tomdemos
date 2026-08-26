import builtins
from typing import Any, Callable

import numpy as np
from PySide6.QtGui import QDoubleValidator, QIntValidator
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
    if param.validator is not None and not param.validator(value):
        control.setStyleSheet(INVALID_FIELD_STYLE)
        return

    control.setStyleSheet(CLEAR_FIELD_STYLE)


def single_field_write(control: QLineEdit, param: Parameter, parser: Callable[[str], Any]) -> None:
    value = parser(control.text())

    if param.validator is not None and not param.validator(value):
        return

    param.value = value


class TableModel(QAbstractTableModel):
    _data: list[list[float]]

    def __init__(self, data: list[list[float]]) -> None:
        super().__init__()
        self._data = data

    def data(self, index, role=0):
        # Qt::DisplayRole, apparently the actual textual data for an ItemDataRole, don't ask
        if role == 0:
            return self._data[index.row()][index.column()]

    # huge fucking weird folderol here just to make the base type interface happy
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() or not self._data else len(self._data[0])


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
            new_control = None

            match type(param.value):
                case builtins.list | builtins.tuple:
                    new_control = QTableView()
                    new_control.setModel(TableModel(param.value))
                    new_control.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
                    new_control.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    new_control.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    new_control.adjustSize()

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
