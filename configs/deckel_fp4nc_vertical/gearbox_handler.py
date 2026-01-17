from PyQt5.QtCore import pyqtSlot
from qtvcp.core import Qhal

class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.paths = paths
        self.qhal = Qhal()
        self.qhal.load_hal_file = False

    def initialized__(self):
        self.qhal.connect('spindle_cmd_rpm', self.update_label_spindle_requested)
        self.qhal.connect('spindle_actual_rpm', self.update_label_spindle_actual)
        self.qhal.connect('gearbox_nominal_rpm', self.update_label_spindle_nominal)


    @pyqtSlot(float)
    def update_label_spindle_requested(self, value):
        self.w.label_spindle_requested.setText(f"{value:.0f} RPM")

    @pyqtSlot(float)
    def update_label_spindle_actual(self, value):
        self.w.label_spindle_actual.setText(f"{value:.0f} RPM")

    @pyqtSlot(float)
    def update_label_spindle_nominal(self, value):
        self.w.label_spindle_nominal.setText(f"{value:.0f} RPM")

