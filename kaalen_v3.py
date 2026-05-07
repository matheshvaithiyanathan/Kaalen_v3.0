# Copyright (c) [2026] [Mathesh Vaithiyanathan]
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import os
import sys
import time
import ctypes
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap, QColor, QIcon, QFont, QPalette
from PyQt6.QtCore import Qt

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == '__main__':
    if sys.platform == 'win32':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('dataviewer2D.Kaalen_app.3.0')
        except AttributeError:
            pass

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.blue)
    palette.setColor(QPalette.ColorRole.Highlight, Qt.GlobalColor.lightGray)
    app.setPalette(palette)

    app.setWindowIcon(QIcon(resource_path('icon.ico')))

    splash_pixmap = QPixmap(resource_path('icon.png'))

    splash_pixmap = splash_pixmap.scaled(
        500, 500,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

    splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)

    splash_font = QFont()
    splash_font.setPointSize(12)
    splash_font.setBold(True)
    splash.setFont(splash_font)

    splash.showMessage(
        "Loading Kaalen v3.0...\nDeveloped by InstrumentsResponse",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        QColor("black")
    )

    splash.show()
    app.processEvents()


import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*sipPyTypeDict.*")
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import lmfit
from scipy.linalg import lstsq
from scipy.optimize import curve_fit, least_squares
from scipy.special import erf, voigt_profile, erfc, erfcx
from scipy.ndimage import gaussian_filter
from functools import partial
import scipy
import re
import json
import ctypes

import pyqtgraph as pg

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

import pandas as pd
from scipy.interpolate import RectBivariateSpline, UnivariateSpline, interp1d, griddata
from lmfit.printfuncs import report_fit

from PyQt6.QtWidgets import (QApplication, QWidget, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QCheckBox, QMessageBox, QVBoxLayout, QHBoxLayout, QTextEdit, QSpinBox,
                             QMainWindow, QSlider, QDialog, QSplitter, QDialogButtonBox, QInputDialog, QDoubleSpinBox,
                             QMenu, QFileDialog, QComboBox, QTabWidget, QGroupBox, QTabBar, QFormLayout)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QDoubleValidator, QIntValidator, QIcon, QAction, QTransform, QPalette
from PyQt6 import uic

# Matplotlib PyQt6 Backend
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

print(f"Pandas Version: {pd.__version__}")
print(f"NumPy Version: {np.__version__}")
print(f"PyQtGraph Version: {pg.__version__}")
print(f"Scipy Version: {scipy.__version__}")
print(f"LMFIT Version: {lmfit.__version__}")


def symlog_transform(data, linthresh=1.0):
    return np.sign(data) * np.log10(1 + np.abs(data) / linthresh)


def inverse_symlog(data, linthresh=1.0):
    return np.sign(data) * linthresh * (10 ** np.abs(data) - 1)


def patch_curve_symlog(curve, x_axis, y_axis):
    if getattr(curve, '_symlog_patched', False): return
    curve._symlog_patched = True
    curve._original_setData = curve.setData
    curve._raw_x = None
    curve._raw_y = None

    def new_setData(*args, **kwargs):
        x = kwargs.get('x', None)
        y = kwargs.get('y', None)

        if len(args) == 1:
            if isinstance(args[0], np.ndarray) and args[0].ndim == 2:
                x = args[0][:, 0]
                y = args[0][:, 1]
            else:
                y = args[0]
        elif len(args) >= 2:
            x = args[0]
            y = args[1]

        if x is not None:
            curve._raw_x = np.array(x, copy=True)
        elif curve._raw_x is None:
            cx, cy = curve.getData()
            if cx is not None: curve._raw_x = np.array(cx, copy=True)

        if y is not None:
            curve._raw_y = np.array(y, copy=True)
        elif curve._raw_y is None:
            cx, cy = curve.getData()
            if cy is not None: curve._raw_y = np.array(cy, copy=True)

        plot_x = curve._raw_x
        plot_y = curve._raw_y

        if plot_x is not None and getattr(x_axis, 'symlog_mode', False):
            plot_x = symlog_transform(plot_x, x_axis.linthresh)
        if plot_y is not None and getattr(y_axis, 'symlog_mode', False):
            plot_y = symlog_transform(plot_y, y_axis.linthresh)

        if plot_x is not None and plot_y is not None:
            return curve._original_setData(x=plot_x, y=plot_y)
        elif plot_y is not None:
            return curve._original_setData(y=plot_y)
        else:
            return curve._original_setData(*args, **kwargs)

    curve.setData = new_setData

    def refresh_symlog():
        if curve._raw_x is not None or curve._raw_y is not None:
            new_setData(x=curve._raw_x, y=curve._raw_y)

    curve.refresh_symlog = refresh_symlog


def add_symlog_to_plot_widget(plot_widget, linthresh=1.0, on_toggle_callback=None):
    plot_item = plot_widget.getPlotItem()
    vb = plot_item.getViewBox()
    x_axis = plot_item.getAxis('bottom')
    y_axis = plot_item.getAxis('left')

    x_axis.symlog_mode = False
    x_axis.linthresh = linthresh
    y_axis.symlog_mode = False
    y_axis.linthresh = linthresh

    def make_symlog_tickStrings(axis):
        orig_ticks = axis.tickStrings

        def symlog_tickStrings(values, scale, spacing):
            if getattr(axis, 'symlog_mode', False):
                orig_vals = inverse_symlog(np.array(values), axis.linthresh)
                return [f"{v:.2g}" if abs(v) > 1e-4 else "0" for v in orig_vals]
            return orig_ticks(values, scale, spacing)

        return symlog_tickStrings

    x_axis.tickStrings = make_symlog_tickStrings(x_axis)
    y_axis.tickStrings = make_symlog_tickStrings(y_axis)

    if vb.menu is None:
        vb.getMenu()

    def toggle_symlog_x(checked):
        x_axis.symlog_mode = checked
        refresh_all_curves()
        plot_item.update()
        if on_toggle_callback: on_toggle_callback()

    def toggle_symlog_y(checked):
        y_axis.symlog_mode = checked
        refresh_all_curves()
        plot_item.update()
        if on_toggle_callback: on_toggle_callback()

    if vb.menu is not None:
        symlog_action_x = QAction("SymLog X", vb.menu)
        symlog_action_x.setCheckable(True)
        symlog_action_x.triggered.connect(toggle_symlog_x)
        vb.menu.addAction(symlog_action_x)

        symlog_action_y = QAction("SymLog Y", vb.menu)
        symlog_action_y.setCheckable(True)
        symlog_action_y.triggered.connect(toggle_symlog_y)
        vb.menu.addAction(symlog_action_y)

    orig_plot = plot_item.plot

    def new_plot(*args, **kwargs):
        curve = orig_plot(*args, **kwargs)
        patch_curve_symlog(curve, x_axis, y_axis)
        return curve

    plot_item.plot = new_plot

    orig_addItem = plot_item.addItem

    def new_addItem(item, *args, **kwargs):
        orig_addItem(item, *args, **kwargs)
        if isinstance(item, pg.PlotDataItem):
            patch_curve_symlog(item, x_axis, y_axis)

    plot_item.addItem = new_addItem

    def refresh_all_curves():
        for item in plot_item.items:
            if isinstance(item, pg.PlotDataItem) and hasattr(item, 'refresh_symlog'):
                item.refresh_symlog()

    for item in plot_item.items:
        if isinstance(item, pg.PlotDataItem):
            patch_curve_symlog(item, x_axis, y_axis)


# --- END SYMLOG HELPER FUNCTIONS ---


def find(in_array, target_value):
    array = in_array
    nearest_index = np.abs(array - target_value).argmin()
    nearest_value = array[nearest_index]
    return nearest_index


def simple_multi_exponential_gf(time, taus):
    return np.exp(-time[:, None] / taus)


def convolved_exponential_analytical(time, tau, t0, delta):
    k = 1.0 / tau
    mu = t0
    delta_tilde = delta / (2 * np.sqrt(2 * np.log(2)))
    term1 = -k * time + k * mu + (k ** 2 * delta_tilde ** 2) / 2
    term2 = 1 + erf((time - (mu + k * delta_tilde ** 2)) / (np.sqrt(2) * delta_tilde))
    term1_clipped = np.clip(term1, -np.inf, 700)

    model = 0.5 * np.exp(term1_clipped) * term2
    model[time < t0 - 5 * delta_tilde] = 0

    return model


# --- MATHEMATICAL FUNCTIONS FOR LUIS PAPER FIT ---

def luis_G(t, d):
    return (1 / np.sqrt(2 * np.pi * d ** 2)) * np.exp(-0.5 * (t / d) ** 2)


def luis_G_prime(t, d):
    return -(t / d ** 2) * luis_G(t, d)


def luis_G_double_prime(t, d):
    return ((t ** 2 / d ** 4) - (1 / d ** 2)) * luis_G(t, d)


def luis_CS(t, d):
    return 0.5 * erfc(-t / (np.sqrt(2) * d))


def luis_CExp(t, d, k):
    # Mathematically stable formulation avoiding 0.0 * inf (NaN) for large positive t
    x = (d ** 2 * k - t) / (np.sqrt(2) * d)

    # Case for x >= 0
    term_pos = 0.5 * np.exp(-0.5 * (t / d) ** 2) * erfcx(np.clip(x, 0, np.inf))

    # Case for x < 0 (Uses the identity erfc(x) = 2 - erfc(-x) to prevent erfcx from returning inf)
    exp_arg = np.clip(0.5 * (d * k) ** 2 - k * t, -np.inf, 700)
    term_neg = np.exp(exp_arg) - 0.5 * np.exp(-0.5 * (t / d) ** 2) * erfcx(np.clip(-x, 0, np.inf))

    return np.where(x >= 0, term_pos, term_neg)


# -------------------------------------------------

def _format_unit_for_display(unit_string):
    unit_string = unit_string.replace("^-1", "\u207B\u00B9")
    unit_string = unit_string.replace("^-2", "\u207B\u00B2")
    unit_string = unit_string.replace("^2", "\u00B2")
    unit_string = unit_string.replace("^3", "\u00B3")
    unit_string = unit_string.replace("^-3", "\u207B\u00B3")
    unit_string = unit_string.replace("^-4", "\u207B\u2074")
    unit_string = unit_string.replace("_1", "\u2081")
    unit_string = unit_string.replace("_2", "\u2082")
    unit_string = unit_string.replace("_3", "\u2083")
    return unit_string


def _parse_label_and_unit(label_string):
    match = re.search(r'^(.*?)\s*\[(.*?)\]', label_string)
    if match:
        label = match.group(1).strip()
        unit = match.group(2).strip()
        return label, unit
    return label_string, ''


def _build_single_component_pfid_terms(T_new, ν, T2, ν10, ν21, r):
    c = 2.998e10
    T_sec = T_new * 1e-12
    T2_sec = T2 * 1e-12

    exp_factor = np.exp(-T_sec[:, None] / T2_sec)

    term1_numerator = (1 / (T2 * 1e-12)) * np.cos(2 * np.pi * c * (ν - ν10) * T_sec[:, None]) - \
                      2 * np.pi * c * (ν - ν10) * np.sin(2 * np.pi * c * (ν - ν10) * T_sec[:, None])
    term1_denominator = (2 * np.pi * c * (ν - ν10)) ** 2 + (1 / T2_sec) ** 2
    term1 = exp_factor * (term1_numerator / term1_denominator)

    term2_numerator_orig = (1 / (T2 * 1e-12)) * np.cos(2 * np.pi * c * (ν - ν10) * T_sec[:, None]) - \
                           2 * np.pi * c * (ν - ν21) * np.sin(2 * np.pi * c * (ν - ν10) * T_sec[:, None])
    term2_denominator_orig = (2 * np.pi * c * (ν - ν21)) ** 2 + (1 / T2_sec) ** 2

    term2 = -r * exp_factor * (term2_numerator_orig / term2_denominator_orig)

    return term1.ravel(), term2.ravel()


def build_design_matrix_pfid(T_new, ν, component_params, r_values):
    all_terms = []
    for i, (T2, ν10, ν21) in enumerate(component_params):
        r = r_values[i]
        term1_ravel, term2_ravel = _build_single_component_pfid_terms(T_new, ν, T2, ν10, ν21, r)
        all_terms.append(term1_ravel)
        all_terms.append(term2_ravel)

    n_T = T_new.size
    n_ν = ν.size
    offset_term = np.ones((n_T, n_ν)).ravel()
    all_terms.append(offset_term)

    return np.column_stack(all_terms)


def residual_pfid(params, T_new, ν, data, num_components):
    component_params = []
    r_values = []
    for i in range(num_components):
        comp_idx = i + 1
        T2 = params[f'T2_{comp_idx}'].value
        ν10 = params[f'ν10_{comp_idx}'].value
        ν21 = params[f'ν21_{comp_idx}'].value
        r_values.append(params[f'r_{comp_idx}'].value)
        component_params.append((T2, ν10, ν21))

    A = build_design_matrix_pfid(T_new, ν, component_params, r_values)
    y = data.ravel()
    amplitudes = lstsq(A, y)[0]
    model = A @ amplitudes
    return (model - y)


class AnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            results = self.run_global_fit_analysis(**self.params)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

    def run_global_fit_analysis(self, time_min, time_max, probe_min, probe_max,
                                manual_num_components, probes_to_plot, use_convolved_model,
                                use_svd_initial_guess, manual_tau_guesses,
                                manual_t0_guess, manual_fwhm_guess, fix_t0, fix_fwhm,
                                x_axis, y_axis, two_d_spectrum, fixed_tau_indices, fixed_long_tau):
        if x_axis is None or y_axis is None or two_d_spectrum is None:
            self.error.emit("Data not provided to the analysis worker.")
            return

        try:
            time_min_idx = find(y_axis, time_min)
            time_max_idx = find(y_axis, time_max)
            probe_min_idx = find(x_axis, probe_min)
            probe_max_idx = find(x_axis, probe_max)

            t_start, t_end = min(time_min_idx, time_max_idx), max(time_min_idx, time_max_idx)
            p_start, p_end = min(probe_min_idx, probe_max_idx), max(probe_min_idx, probe_max_idx)

            data_sliced = two_d_spectrum[t_start:t_end + 1, p_start:p_end + 1]
            time_sliced = y_axis[t_start:t_end + 1]
            probe_sliced = x_axis[p_start:p_end + 1]

            if data_sliced.size == 0:
                raise IndexError("Sliced data is empty. Check min/max bounds.")
        except IndexError as e:
            self.error.emit(f"Error: Bounding issue. {str(e)}")
            return

        initial_tau_guesses = [fixed_long_tau]
        warnings_list = []

        if use_svd_initial_guess:
            U, S, Vt = np.linalg.svd(data_sliced, full_matrices=False)
            num_components_to_fit = manual_num_components
            for i in range(num_components_to_fit):
                initial_amp = np.sign(U[0, i])
                p0 = [initial_amp, 10.0]

                def mono_exponential_model(t, amplitude, tau):
                    return amplitude * np.exp(-t / tau)

                try:
                    popt, _ = curve_fit(mono_exponential_model, time_sliced, U[:, i], p0=p0, maxfev=5000)
                    initial_tau_guesses.append(popt[1])
                except RuntimeError:
                    warnings_list.append(f"Warning: Fit for component {i + 1} failed. Skipping...")

            initial_tau_guesses = [fixed_long_tau] + sorted([tau for tau in initial_tau_guesses[1:] if tau > 0])
            initial_tau_guesses_for_print = initial_tau_guesses[:]
            if not initial_tau_guesses:
                self.error.emit("SVD-based initial guess generation failed.")
                return
        else:
            if manual_tau_guesses is None or len(manual_tau_guesses) != manual_num_components:
                self.error.emit("manual_tau_guesses must be a list with length equal to manual_num_components.")
                return
            initial_tau_guesses = [fixed_long_tau] + manual_tau_guesses
            initial_tau_guesses_for_print = initial_tau_guesses[:]

        def build_design_matrix(time, taus, t0, fwhm):
            if use_convolved_model:
                A_columns = [convolved_exponential_analytical(time, tau, t0, fwhm) for tau in taus]
            else:
                A_columns = [simple_multi_exponential_gf(time, np.array([tau])).flatten() for tau in taus]
            return np.stack(A_columns, axis=1)

        def objective_function(params, time, data):
            taus = [params[f'tau_{i}'].value for i in range(len(initial_tau_guesses))]
            t0 = params['t0'].value if use_convolved_model else None
            fwhm = params['fwhm'].value if use_convolved_model else None

            A = build_design_matrix(time, taus, t0, fwhm)
            amplitudes, _, _, _ = lstsq(A, data)
            model = A @ amplitudes
            return (model - data).ravel()

        params = lmfit.Parameters()
        for i, tau_val in enumerate(initial_tau_guesses):
            if i == 0:
                vary_tau = False
            else:
                vary_tau = i - 1 not in fixed_tau_indices
            params.add(f'tau_{i}', value=tau_val, min=0.01, max=np.inf, vary=vary_tau)

        if use_convolved_model:
            params.add('t0', value=manual_t0_guess, min=-5, max=5, vary=not fix_t0)
            params.add('fwhm', value=manual_fwhm_guess, min=0.01, max=4, vary=not fix_fwhm)

        minimizer = lmfit.Minimizer(objective_function, params, fcn_args=(time_sliced, data_sliced))
        result = minimizer.minimize(method='leastsq')

        ss_res = np.sum(result.residual ** 2)
        ss_tot = np.sum((data_sliced - np.mean(data_sliced)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        best_taus = [result.params[f'tau_{i}'].value for i in range(len(initial_tau_guesses))]
        best_t0 = result.params['t0'].value if use_convolved_model else None
        best_fwhm = result.params['fwhm'].value if use_convolved_model else None

        A_final = lstsq(build_design_matrix(time_sliced, best_taus, best_t0, best_fwhm), data_sliced)[0]
        best_fit = (build_design_matrix(time_sliced, best_taus, best_t0, best_fwhm) @ A_final)

        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            report_fit(result)
            fit_report_string = buffer.getvalue()
        finally:
            sys.stdout = old_stdout

        return (
            best_fit, A_final, best_taus, r_squared, probe_sliced, time_sliced, data_sliced, probes_to_plot, best_t0,
            best_fwhm, None, use_convolved_model, initial_tau_guesses_for_print, fit_report_string, warnings_list)


class PFIDFitWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            results = self.run_pfid_fit_analysis(**self.params)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(f"PFID Fit Error: {e}")

    def run_pfid_fit_analysis(self, time_min, time_max, probe_min, probe_max,
                              num_components, T2_params, nu10_params, nu21_params, r_params,
                              interp_method, num_interp_points,
                              x_axis, y_axis, two_d_spectrum):

        if x_axis is None or y_axis is None or two_d_spectrum is None:
            raise ValueError("Data not provided to the analysis worker.")

        T2_guesses, T2_fix_flags = T2_params
        nu10_guesses, nu10_fix_flags = nu10_params
        nu21_guesses, nu21_fix_flags = nu21_params
        r_guesses, r_fix_flags = r_params

        try:
            t_idx1 = find(y_axis, time_min)
            t_idx2 = find(y_axis, time_max)
            t_start, t_end = min(t_idx1, t_idx2), max(t_idx1, t_idx2)

            p_idx1 = find(x_axis, probe_min)
            p_idx2 = find(x_axis, probe_max)
            p_start, p_end = min(p_idx1, p_idx2), max(p_idx1, p_idx2)

            data_raw_sliced = two_d_spectrum[t_start:t_end + 1, p_start:p_end + 1]
            time_raw_sliced = y_axis[t_start:t_end + 1]
            probe_raw_sliced = x_axis[p_start:p_end + 1]

            if data_raw_sliced.size == 0:
                raise IndexError("Selected data slice is empty. Adjust Time/Probe Min/Max bounds.")
        except IndexError as e:
            raise IndexError(f"Slicing Error: {str(e)}")

        T_orig = np.abs(time_raw_sliced)
        ω_orig = probe_raw_sliced
        data_orig = data_raw_sliced

        if interp_method.lower() == 'none' or num_interp_points < 2:
            T_new = T_orig
            ω_new = ω_orig
            data_interp = data_orig
        else:
            sort_x = np.argsort(ω_orig)
            sort_y = np.argsort(T_orig)
            sorted_x_vals = ω_orig[sort_x]
            sorted_y_vals = T_orig[sort_y]
            sorted_z_data = data_orig[sort_y, :][:, sort_x]

            T_new = np.linspace(np.min(T_orig), np.max(T_orig), num_interp_points)
            ω_new = np.linspace(np.min(ω_orig), np.max(ω_orig), num_interp_points)

            kx, ky = 3, 3
            if interp_method.lower() == 'linear':
                kx, ky = 1, 1

            interp_func = RectBivariateSpline(sorted_y_vals, sorted_x_vals, sorted_z_data, kx=kx, ky=ky)
            data_interp_sorted = interp_func(np.sort(T_new), np.sort(ω_new))

            T_new = np.sort(T_new)
            ω_new = np.sort(ω_new)
            data_interp = data_interp_sorted

        params = lmfit.Parameters()
        for i in range(num_components):
            comp_idx = i + 1
            params.add(f'T2_{comp_idx}', value=T2_guesses[i], min=0.01, max=30, vary=not T2_fix_flags[i])
            params.add(f'ν10_{comp_idx}', value=nu10_guesses[i], min=np.min(ω_new), max=np.max(ω_new), vary=not nu10_fix_flags[i])
            params.add(f'ν21_{comp_idx}', value=nu21_guesses[i], min=np.min(ω_new), max=np.max(ω_new), vary=not nu21_fix_flags[i])
            params.add(f'r_{comp_idx}', value=r_guesses[i], min=0.0, max=1.0, vary=not r_fix_flags[i])

        minimizer = lmfit.Minimizer(residual_pfid, params, fcn_args=(T_new, ω_new, data_interp, num_components))
        result = minimizer.minimize(method='leastsq')

        best_params_list = []
        best_r_list = []
        for i in range(num_components):
            comp_idx = i + 1
            best_T2 = result.params[f'T2_{comp_idx}'].value
            best_nu10 = result.params[f'ν10_{comp_idx}'].value
            best_nu21 = result.params[f'ν21_{comp_idx}'].value
            best_r = result.params[f'r_{comp_idx}'].value
            best_params_list.append((best_T2, best_nu10, best_nu21))
            best_r_list.append(best_r)

        A_final = lstsq(build_design_matrix_pfid(T_new, ω_new, best_params_list, best_r_list), data_interp.ravel())[0]
        best_fit_flat = build_design_matrix_pfid(T_new, ω_new, best_params_list, best_r_list) @ A_final
        best_fit = best_fit_flat.reshape(data_interp.shape)

        ss_res = np.sum((best_fit_flat - data_interp.ravel()) ** 2)
        ss_tot = np.sum((data_interp - np.mean(data_interp)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            report_fit(result)
            fit_report_string = buffer.getvalue()
        finally:
            sys.stdout = old_stdout

        return (best_fit, A_final, r_squared, ω_new, T_new, data_interp, fit_report_string, result, num_components)


class LuisFitWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            results = self.run_luis_fit_analysis(**self.params)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

    def build_luis_design_matrix(self, time, t0, d, k_vals):
        t_shifted = time - t0
        G = luis_G(t_shifted, d)
        Gp = luis_G_prime(t_shifted, d)
        Gdp = luis_G_double_prime(t_shifted, d)
        CS = luis_CS(t_shifted, d)
        cols = [G, Gp, Gdp, CS]
        for k in k_vals:
            cols.append(luis_CExp(t_shifted, d, k))
        return np.stack(cols, axis=1)

    def run_luis_fit_analysis(self, time_min, time_max, probe_min, probe_max,
                              d_guess, tau_guesses, probes_to_plot,
                              x_axis, y_axis, two_d_spectrum):
        if x_axis is None or y_axis is None or two_d_spectrum is None:
            self.error.emit("Data not provided to the analysis worker.")
            return

        try:
            time_min_idx = find(y_axis, time_min)
            time_max_idx = find(y_axis, time_max)
            probe_min_idx = find(x_axis, probe_min)
            probe_max_idx = find(x_axis, probe_max)

            t_start, t_end = min(time_min_idx, time_max_idx), max(time_min_idx, time_max_idx)
            p_start, p_end = min(probe_min_idx, probe_max_idx), max(probe_min_idx, probe_max_idx)

            data_sliced = two_d_spectrum[t_start:t_end + 1, p_start:p_end + 1]
            time_sliced = y_axis[t_start:t_end + 1]
            probe_sliced = x_axis[p_start:p_end + 1]

            if data_sliced.size == 0:
                raise IndexError("Sliced data is empty. Check min/max bounds.")
        except IndexError as e:
            self.error.emit(f"Error: Bounding issue. {str(e)}")
            return

        def objective_function(params, time, data):
            t0 = params['t0'].value
            d = params['d'].value
            tau_vals = [params[f'tau_{i}'].value for i in range(len(tau_guesses))]
            k_vals = [1.0 / t if t != 0 else 1e6 for t in tau_vals]
            A = self.build_luis_design_matrix(time, t0, d, k_vals)
            amplitudes, _, _, _ = lstsq(A, data)
            model = A @ amplitudes
            return (model - data).ravel()

        params = lmfit.Parameters()
        params.add('t0', value=0.0, min=-5.0, max=5.0)  # Add floating time zero
        params.add('d', value=d_guess, min=0.001, max=10.0)
        for i, tau_val in enumerate(tau_guesses):
            params.add(f'tau_{i}', value=tau_val, min=0.001, max=100000.0)

        minimizer = lmfit.Minimizer(objective_function, params, fcn_args=(time_sliced, data_sliced))
        result = minimizer.minimize(method='leastsq')

        ss_res = np.sum(result.residual ** 2)
        ss_tot = np.sum((data_sliced - np.mean(data_sliced)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        best_t0 = result.params['t0'].value
        best_d = result.params['d'].value
        best_taus = [result.params[f'tau_{i}'].value for i in range(len(tau_guesses))]
        best_ks = [1.0 / t if t != 0 else 1e6 for t in best_taus]

        A_final = lstsq(self.build_luis_design_matrix(time_sliced, best_t0, best_d, best_ks), data_sliced)[0]
        best_fit = (self.build_luis_design_matrix(time_sliced, best_t0, best_d, best_ks) @ A_final)

        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            report_fit(result)
            fit_report_string = buffer.getvalue()
        finally:
            sys.stdout = old_stdout

        return (best_fit, A_final, best_t0, best_d, best_taus, r_squared, probe_sliced, time_sliced, data_sliced, probes_to_plot, fit_report_string)


class PFIDFitterApp(QMainWindow):
    def __init__(self, main_window, x_axis_label='Probe wavenumber', y_axis_label='Time', z_axis_label='ΔOD', x_axis_unit='cm\u207B\u00B9',
                 y_axis_unit='ps', z_axis_unit='mOD', font_size=12):
        super().__init__(main_window)
        uic.loadUi(resource_path('pfid_tab.ui'), self)

        self.setWindowTitle("PFID (Photon-Frequency-ID) Fitting Analysis")
        self.setObjectName("PFID Fit")

        self.main_window = main_window
        self.x_axis_label = x_axis_label
        self.y_axis_label = y_axis_label
        self.z_axis_label = z_axis_label
        self.x_axis_unit = x_axis_unit
        self.y_axis_unit = y_axis_unit
        self.z_axis_unit = z_axis_unit
        self.font_size = font_size
        self.worker_thread = None

        self.x_axis_data = None
        self.y_axis_data = None
        self.two_d_spectrum_data = None
        self.results_data = None

        self.map_ui()
        self.update_axis_labels(self.x_axis_label, self.x_axis_unit, self.y_axis_label, self.y_axis_unit, self.z_axis_label, self.z_axis_unit)

    def update_axis_labels(self, x_label, x_unit, y_label, y_unit, z_label, z_unit):
        self.x_axis_label = x_label
        self.x_axis_unit = x_unit
        self.y_axis_label = y_label
        self.y_axis_unit = y_unit
        self.z_axis_label = z_label
        self.z_axis_unit = z_unit

        if hasattr(self, 'time_min_label') and self.time_min_label:
            self.time_min_label.setText(f"{y_label} min ({y_unit}):")
        if hasattr(self, 'time_max_label') and self.time_max_label:
            self.time_max_label.setText(f"{y_label} max ({y_unit}):")
        if hasattr(self, 'probe_min_label') and self.probe_min_label:
            self.probe_min_label.setText(f"{x_label} min ({x_unit}):")
        if hasattr(self, 'probe_max_label') and self.probe_max_label:
            self.probe_max_label.setText(f"{x_label} max ({x_unit}):")

        if hasattr(self, 'results_data') and self.results_data is not None:
            self.plot_results(self.results_data)

    def map_ui(self):
        self.time_min_input = self.lineEdit_PD
        self.time_max_input = self.lineEdit_2_PD
        self.probe_min_input = self.lineEdit_3_PD
        self.probe_max_input = self.lineEdit_4_PD
        self.num_components_input = self.lineEdit_6_PD

        # Dynamic label mappings
        self.time_min_label = getattr(self, 'label_2_PD', None)
        self.time_max_label = getattr(self, 'label_3_PD', None)
        self.probe_min_label = getattr(self, 'label_4_PD', None)
        self.probe_max_label = getattr(self, 'label_5_PD', None)

        self.T2_guess_input = self.lineEdit_7_PD
        self.nu10_guess_input = self.lineEdit_8_PD
        self.nu21_guess_input = self.lineEdit_9_PD

        # Fallback handling for "r" guess input
        self.r_guess_input = getattr(self, 'lineEdit_10_PD', getattr(self, 'lineEdit_10', None))

        self.interp_method_combo = self.comboBox_PD
        self.interp_points_input = self.spinBox_PD
        self.interp_points_input.setRange(10, 1000)
        self.interp_points_input.setValue(100)
        self.run_button = self.pushButton_PD
        self.export_button = self.pushButton_2_PD
        self.results_text_edit = self.textEdit_PD

        self.plot1_vbox = QVBoxLayout(self.widget_PD_2)
        self.plot2_vbox = QVBoxLayout(self.widget_2_PD_2)
        self.plot3_vbox = QVBoxLayout(self.widget_4_PD_2)

        self.run_button.clicked.connect(self.run_pfid_fit)
        self.export_button.clicked.connect(self.export_fit_results)
        self.export_button.setDisabled(True)

        if self.main_window and hasattr(self.main_window, 'data_loaded') and self.main_window.data_loaded:
            x_data = self.main_window.current_x_values
            y_data = self.main_window.current_y_values
            if x_data is not None and len(x_data) > 0:
                self.probe_min_input.setText(f"{np.min(x_data):.2f}")
                self.probe_max_input.setText(f"{np.max(x_data):.2f}")
            else:
                self.probe_min_input.setText("1775")
                self.probe_max_input.setText("1850")
            if y_data is not None and len(y_data) > 0:
                self.time_min_input.setText(f"{np.min(y_data):.2f}")
                self.time_max_input.setText(f"{np.max(y_data):.2f}")
            else:
                self.time_min_input.setText("-15.0")
                self.time_max_input.setText("-0.5")
        else:
            self.time_min_input.setText("-15.0")
            self.time_max_input.setText("-0.5")
            self.probe_min_input.setText("1775")
            self.probe_max_input.setText("1850")

        self.num_components_input.setText("1")
        self.T2_guess_input.setText("2.0")
        self.nu10_guess_input.setText("1810")
        self.nu21_guess_input.setText("1785")
        if hasattr(self, 'r_guess_input') and self.r_guess_input:
            self.r_guess_input.setText("0.2")

    def parse_fixed_float_list_gui(self, text, name, num_components):
        vals_str = [v.strip() for v in text.split(',') if v.strip()]
        if len(vals_str) != num_components:
            raise ValueError(f"Number of {name} guesses ({len(vals_str)}) must match number of components ({num_components}).")
        values = []
        fix_flags = []
        for v_str in vals_str:
            is_fixed = False
            v_str_clean = v_str
            if v_str.endswith(':'):
                is_fixed = True
                v_str_clean = v_str[:-1]
            try:
                values.append(float(v_str_clean))
                fix_flags.append(is_fixed)
            except ValueError:
                raise ValueError(f"Invalid number format in {name}: '{v_str}' is not a valid float.")
        return values, fix_flags

    def run_pfid_fit(self):
        if self.main_window and hasattr(self.main_window, 'data_loaded') and self.main_window.data_loaded:
            self.x_axis_data = self.main_window.current_x_values
            self.y_axis_data = self.main_window.current_y_values
            self.two_d_spectrum_data = self.main_window.current_signal_data

        if self.x_axis_data is None:
            QMessageBox.critical(self, "No Data", "No 2D data is currently loaded.")
            return

        try:
            num_components = int(self.num_components_input.text())
            if num_components < 1:
                raise ValueError("Number of PFID Components must be 1 or greater.")

            T2_params = self.parse_fixed_float_list_gui(self.T2_guess_input.text(), "T2", num_components)
            nu10_params = self.parse_fixed_float_list_gui(self.nu10_guess_input.text(), "ν10", num_components)
            nu21_params = self.parse_fixed_float_list_gui(self.nu21_guess_input.text(), "ν21", num_components)
            r_params = self.parse_fixed_float_list_gui(self.r_guess_input.text(), "r", num_components)

            params = {
                "time_min": float(self.time_min_input.text()),
                "time_max": float(self.time_max_input.text()),
                "probe_min": float(self.probe_min_input.text()),
                "probe_max": float(self.probe_max_input.text()),
                "num_components": num_components,
                "T2_params": T2_params,
                "nu10_params": nu10_params,
                "nu21_params": nu21_params,
                "r_params": r_params,
                "interp_method": self.interp_method_combo.currentText(),
                "num_interp_points": self.interp_points_input.value(),
                "x_axis": self.x_axis_data,
                "y_axis": self.y_axis_data,
                "two_d_spectrum": self.two_d_spectrum_data,
            }

            if params["time_min"] >= 0 or params["time_max"] >= 0:
                QMessageBox.warning(self, "Input Warning", "PFID fit typically requires a negative time range.")

            self.results_text_edit.setText("Running fit... Please wait.")
            self.run_button.setDisabled(True)
            self.export_button.setDisabled(True)

            self.worker_thread = PFIDFitWorker(params)
            self.worker_thread.finished.connect(self.plot_results)
            self.worker_thread.error.connect(self.handle_error)
            self.worker_thread.start()

        except ValueError as ve:
            QMessageBox.critical(self, "Input Error", f"Invalid format: {ve}")
            self.run_button.setDisabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {e}")
            self.run_button.setDisabled(False)

    def plot_results(self, results):
        self.run_button.setDisabled(False)
        self.export_button.setDisabled(False)

        (best_fit, A_final, r_squared, probe, time, data_interp, fit_report_string, result, num_components) = results
        self.results_data = results
        A_offset = A_final[-1]

        output_text = "--- PFID Fit Results ---\n\n"
        output_text += f"Number of Components Fitted: {num_components}\n"
        output_text += f"Overall R-squared value: {r_squared:.4f}\n"

        for i in range(num_components):
            A1 = A_final[i * 2]
            A2 = A_final[i * 2 + 1]
            output_text += f"Component {i + 1} Amplitudes: A₁ = {A1:.2g}, A₂ = {A2:.2g}\n"

        output_text += f"Overall Offset: {A_offset:.2g}\n\n--- Full lmfit Report ---\n"
        output_text += fit_report_string
        self.results_text_edit.setText(output_text)

        def clear_layout(layout):
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        clear_layout(self.plot1_vbox)
        clear_layout(self.plot2_vbox)
        clear_layout(self.plot3_vbox)

        font_size = self.font_size
        plt.rcParams.update({'font.size': font_size})
        formatted_x_unit = _format_unit_for_display(self.x_axis_unit)
        formatted_y_unit = _format_unit_for_display(self.y_axis_unit)
        formatted_z_unit = _format_unit_for_display(self.z_axis_unit)

        vmin, vmax = data_interp.min(), data_interp.max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)

        fig1 = Figure(figsize=(5, 5), dpi=100)
        canvas1 = FigureCanvas(fig1)
        toolbar1 = NavigationToolbar(canvas1, self.widget_PD_2)
        ax1 = fig1.add_subplot(111)
        im1 = ax1.pcolormesh(probe, time, data_interp, cmap='seismic', shading='auto', norm=norm)
        ax1.set_title('Interpolated Original Data')
        ax1.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        ax1.set_ylabel(f'|{self.y_axis_label}| ({formatted_y_unit})')
        fig1.colorbar(im1, ax=ax1, label=f'{self.z_axis_label} ({formatted_z_unit})')
        fig1.tight_layout()
        self.plot1_vbox.addWidget(toolbar1)
        self.plot1_vbox.addWidget(canvas1)

        fig2 = Figure(figsize=(5, 5), dpi=100)
        canvas2 = FigureCanvas(fig2)
        toolbar2 = NavigationToolbar(canvas2, self.widget_2_PD_2)
        ax2 = fig2.add_subplot(111)
        im2 = ax2.pcolormesh(probe, time, best_fit, cmap='seismic', shading='auto', norm=norm)
        ax2.set_title('Fitted Model')
        ax2.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        fig2.colorbar(im2, ax=ax2, label=f'{self.z_axis_label} ({formatted_z_unit})')
        fig2.tight_layout()
        self.plot2_vbox.addWidget(toolbar2)
        self.plot2_vbox.addWidget(canvas2)

        residuals = data_interp - best_fit
        fig3 = Figure(figsize=(5, 5), dpi=100)
        canvas3 = FigureCanvas(fig3)
        toolbar3 = NavigationToolbar(canvas3, self.widget_4_PD_2)
        ax3 = fig3.add_subplot(111)
        res_max_abs = np.abs(residuals).max()
        res_norm = plt.Normalize(vmin=-res_max_abs, vmax=res_max_abs)
        im3 = ax3.pcolormesh(probe, time, residuals, cmap='seismic', shading='auto', norm=res_norm)
        ax3.set_title('Residuals (Data - Fit)')
        ax3.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        fig3.colorbar(im3, ax=ax3, label=f'Residual {self.z_axis_label} ({formatted_z_unit})')
        fig3.tight_layout()
        self.plot3_vbox.addWidget(toolbar3)
        self.plot3_vbox.addWidget(canvas3)

    def handle_error(self, message):
        self.run_button.setDisabled(False)
        self.export_button.setDisabled(True)
        QMessageBox.critical(self, "PFID Analysis Error", message)
        self.results_text_edit.setText(f"ERROR: {message}")

    def export_fit_results(self):
        if self.results_data is None:
            QMessageBox.warning(self, "No Data", "Please run the PFID fit analysis before exporting.")
            return

        (best_fit, A_final, r_squared, probe, time, data_interp, fit_report_string, result, num_components) = self.results_data
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PFID Fit Data", "", "CSV Files (*.csv)")
        if not file_path: return

        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path).split('.')[0]

        try:
            report_path = os.path.join(dir_name, f"{base_name}_PFID_report.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(fit_report_string)

            header = ["Time (abs_ps)"] + [f"{p:.2f}" for p in probe]
            data_to_export = np.hstack((time[:, np.newaxis], data_interp))
            fit_to_export = np.hstack((time[:, np.newaxis], best_fit))
            pd.DataFrame(data_to_export, columns=header).to_csv(os.path.join(dir_name, f"{base_name}_PFID_interpolated_data.csv"), index=False)
            pd.DataFrame(fit_to_export, columns=header).to_csv(os.path.join(dir_name, f"{base_name}_PFID_fitted_data.csv"), index=False)
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{dir_name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error during export: {e}")


class GlobalFitApp(QMainWindow):
    def __init__(self, x_axis_data=None, y_axis_data=None, two_d_spectrum_data=None, parent=None,
                 x_axis_label='Probe wavenumber', y_axis_label='Time', z_axis_label='ΔOD',
                 x_axis_unit='cm\u207B\u00B9', y_axis_unit='ps', z_axis_unit='mOD', font_size=12):
        super().__init__(parent)
        uic.loadUi(resource_path('global_fit.ui'), self)

        self.setWindowTitle("Global Fitting Analysis")
        self.setObjectName("Global Fit")

        self.x_axis_data = x_axis_data
        self.y_axis_data = y_axis_data
        self.two_d_spectrum_data = two_d_spectrum_data
        self.x_axis_label = x_axis_label
        self.y_axis_label = y_axis_label
        self.z_axis_label = z_axis_label
        self.x_axis_unit = x_axis_unit
        self.y_axis_unit = y_axis_unit
        self.z_axis_unit = z_axis_unit
        self.font_size = font_size
        self.worker_thread = None

        self.map_ui()
        self.update_axis_labels(self.x_axis_label, self.x_axis_unit, self.y_axis_label, self.y_axis_unit, self.z_axis_label, self.z_axis_unit)

    def update_axis_labels(self, x_label, x_unit, y_label, y_unit, z_label, z_unit):
        self.x_axis_label = x_label
        self.x_axis_unit = x_unit
        self.y_label_unit = y_unit
        self.y_label_label = y_label
        self.z_label_label = z_label
        self.z_label_unit = z_unit

        if hasattr(self, 'time_min_label') and self.time_min_label:
            self.time_min_label.setText(f"{y_label} min ({y_unit}):")
        if hasattr(self, 'time_max_label') and self.time_max_label:
            self.time_max_label.setText(f"{y_label} max ({y_unit}):")
        if hasattr(self, 'probe_min_label') and self.probe_min_label:
            self.probe_min_label.setText(f"{x_label} min ({x_unit}):")
        if hasattr(self, 'probe_max_label') and self.probe_max_label:
            self.probe_max_label.setText(f"{x_label} max ({x_unit}):")
        if hasattr(self, 'probe_units_plot_label') and self.probe_units_plot_label:
            self.probe_units_plot_label.setText(f"{x_label} to plot ({x_unit}, comma separated):")

        if hasattr(self, 'last_results') and self.last_results is not None:
            self.plot_results(self.last_results)

    def map_ui(self):
        self.time_min_input = self.lineEdit_GF
        self.time_max_input = self.lineEdit_2_GF
        self.probe_min_input = self.lineEdit_3_GF
        self.probe_max_input = self.lineEdit_4_GF

        self.time_min_label = getattr(self, 'label_2_GF', None)
        self.time_max_label = getattr(self, 'label_3_GF', None)
        self.probe_min_label = getattr(self, 'label_4_GF', None)
        self.probe_max_label = getattr(self, 'label_5_GF', None)
        self.probe_units_plot_label = getattr(self, 'label_13_GF', None)

        self.convolved_checkbox = self.checkBox_GF
        self.num_components_input = self.lineEdit_5_GF
        self.t0_input = self.lineEdit_6_GF
        self.fix_t0_checkbox = self.checkBox_2_GF
        self.fwhm_input = self.lineEdit_7_GF
        self.fix_fwhm_checkbox = self.checkBox_3_GF

        self.svd_checkbox = self.checkBox_4_GF
        self.manual_guess_input = self.lineEdit_8_GF
        self.fixed_long_tau_input = self.lineEdit_9_GF
        self.probes_input = self.lineEdit_10_GF

        self.das_interp_method_combo = self.comboBox_GF
        self.das_interp_multiplier_combo = self.comboBox_2_GF

        self.run_button = self.pushButton_GF
        self.export_button = getattr(self, 'pushButton_2_GF', getattr(self, 'pushButton_2', None))
        self.results_text_edit = getattr(self, 'results_edit_GF_2', getattr(self, 'results_edit_GF', None))

        self.plot1_vbox = QVBoxLayout(self.widget_GF)
        self.plot2_vbox = QVBoxLayout(self.widget_2_GF)
        self.plot3_vbox = QVBoxLayout(self.widget_3_GF)

        self.run_button.clicked.connect(self.run_analysis)
        self.export_button.clicked.connect(self.export_fit_results)
        self.convolved_checkbox.stateChanged.connect(self.toggle_convolved_options)
        self.svd_checkbox.stateChanged.connect(lambda: self.manual_guess_input.setDisabled(self.svd_checkbox.isChecked()))

        self.das_interp_method_combo.currentIndexChanged.connect(self._replot_das)
        self.das_interp_multiplier_combo.currentIndexChanged.connect(self._replot_das)

        if self.x_axis_data is not None and len(self.x_axis_data) > 0:
            self.probe_min_input.setText(f"{np.min(self.x_axis_data):.2f}")
            self.probe_max_input.setText(f"{np.max(self.x_axis_data):.2f}")
        else:
            self.probe_min_input.setText("1900")
            self.probe_max_input.setText("2100")

        if self.y_axis_data is not None and len(self.y_axis_data) > 0:
            self.time_min_input.setText(f"{np.min(self.y_axis_data):.2f}")
            self.time_max_input.setText(f"{np.max(self.y_axis_data):.2f}")
        else:
            self.time_min_input.setText("1.0")
            self.time_max_input.setText("80.0")

        self.num_components_input.setText("2")
        self.t0_input.setText("0")
        self.fwhm_input.setText("0.15")
        self.manual_guess_input.setText("5, 20")
        self.fixed_long_tau_input.setText("1000")
        self.probes_input.setText("1970, 2015, 1950, 1940")

        self.toggle_convolved_options()

    def toggle_convolved_options(self):
        enabled = self.convolved_checkbox.isChecked()
        self.t0_input.setEnabled(enabled)
        self.fix_t0_checkbox.setEnabled(enabled)
        self.fwhm_input.setEnabled(enabled)
        self.fix_fwhm_checkbox.setEnabled(enabled)

    def _get_interpolated_1d_data(self, original_x, original_y, method, multiplier):
        if method == "None" or len(original_x) < 2:
            return np.copy(original_x), np.copy(original_y)
        try:
            target_n_points = int(len(original_x) * multiplier)
            if target_n_points < 2:
                target_n_points = 2
            x_interp = np.linspace(original_x.min(), original_x.max(), target_n_points)
            f_interp = interp1d(original_x, original_y, kind=method.lower(), fill_value="extrapolate")
            y_interp = f_interp(x_interp)
            return x_interp, y_interp
        except Exception as e:
            return np.copy(original_x), np.copy(original_y)

    def _replot_das(self):
        if not hasattr(self, 'last_results') or not self.last_results:
            return
        self.plot_results(self.last_results)

    def export_fit_results(self):
        if getattr(self, 'best_fit_data', None) is None:
            QMessageBox.warning(self, "No Data", "Please run the global fit analysis before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Global Fit Data", "", "CSV Files (*.csv)")
        if not file_path: return
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path).split('.')[0]

        try:
            pd.DataFrame(self.A_final_data.T, index=self.probe_data, columns=[f"τ = {tau:.2f}" for tau in self.best_taus_data]).to_csv(os.path.join(dir_name, f"{base_name}_DAS.csv"))
            pd.DataFrame(self.best_fit_data, index=self.time_data, columns=self.probe_data).to_csv(os.path.join(dir_name, f"{base_name}_2D_fitted_data.csv"))
            traces_df = pd.DataFrame({"Time": self.time_data})
            for probe_val in self.probes_to_plot_data:
                probe_idx = np.argmin(np.abs(self.probe_data - probe_val))
                traces_df[f"Trace at {probe_val}"] = self.data_sliced_for_export[:, probe_idx]
                traces_df[f"{probe_val} (Fit)"] = self.best_fit_data[:, probe_idx]
            traces_df.to_csv(os.path.join(dir_name, f"{base_name}_time_traces.csv"), index=False)
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{dir_name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error: {e}")

    def run_analysis(self):
        try:
            manual_tau_guesses = []
            fixed_tau_indices = []
            if not self.svd_checkbox.isChecked():
                raw_guesses = [t.strip() for t in self.manual_guess_input.text().split(',') if t.strip()]
                for idx, val_str in enumerate(raw_guesses):
                    if val_str.endswith(':'):
                        manual_tau_guesses.append(float(val_str[:-1]))
                        fixed_tau_indices.append(idx)
                    else:
                        manual_tau_guesses.append(float(val_str))
            else:
                manual_tau_guesses = None

            params = {
                "time_min": float(self.time_min_input.text()), "time_max": float(self.time_max_input.text()),
                "probe_min": float(self.probe_min_input.text()), "probe_max": float(self.probe_max_input.text()),
                "manual_num_components": int(self.num_components_input.text()),
                "probes_to_plot": [float(p.strip()) for p in self.probes_input.text().split(',') if p.strip()],
                "use_convolved_model": self.convolved_checkbox.isChecked(),
                "use_svd_initial_guess": self.svd_checkbox.isChecked(),
                "manual_tau_guesses": manual_tau_guesses,
                "manual_t0_guess": float(self.t0_input.text()) if self.convolved_checkbox.isChecked() else None,
                "manual_fwhm_guess": float(self.fwhm_input.text()) if self.convolved_checkbox.isChecked() else None,
                "fix_t0": self.fix_t0_checkbox.isChecked() if self.convolved_checkbox.isChecked() else False,
                "fix_fwhm": self.fix_fwhm_checkbox.isChecked() if self.convolved_checkbox.isChecked() else False,
                "x_axis": self.x_axis_data, "y_axis": self.y_axis_data, "two_d_spectrum": self.two_d_spectrum_data,
                "fixed_tau_indices": fixed_tau_indices, "fixed_long_tau": float(self.fixed_long_tau_input.text())
            }
            self.results_text_edit.clear()
            self.run_button.setDisabled(True)
            self.worker_thread = AnalysisWorker(params)
            self.worker_thread.finished.connect(self.plot_results)
            self.worker_thread.error.connect(self.handle_error)
            self.worker_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Input Error", f"Check inputs. Error: {e}")
            self.run_button.setDisabled(False)

    def plot_results(self, results):
        self.run_button.setDisabled(False)
        if not results: return
        self.last_results = results
        (best_fit, A_final, best_taus, r_squared, probe, time, data_sliced, probes_to_plot, best_t0,
         best_fwhm, best_offset, use_convolved_model, initial_tau_guesses_for_print, fit_report_string, warnings) = results

        self.best_fit_data = best_fit;
        self.A_final_data = A_final;
        self.best_taus_data = best_taus
        self.probe_data = probe;
        self.time_data = time;
        self.data_sliced_for_export = data_sliced
        self.probes_to_plot_data = probes_to_plot

        output_text = f"--- Global Fit Results ---\n\nOverall R-squared: {r_squared:.4f}\nInitial Tau Guesses: {initial_tau_guesses_for_print}\n\n--- Full lmfit Report ---\n{fit_report_string}"
        if warnings:
            output_text += "\n--- Warnings ---\n" + "\n".join([f"- {w}" for w in warnings])
        self.results_text_edit.setText(output_text)

        def clear_layout(layout):
            while layout.count():
                child = layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()

        clear_layout(self.plot1_vbox);
        clear_layout(self.plot2_vbox);
        clear_layout(self.plot3_vbox)

        plt.rcParams.update({'font.size': self.font_size})
        formatted_x_unit = _format_unit_for_display(self.x_axis_unit)
        formatted_y_unit = _format_unit_for_display(self.y_label_unit)
        formatted_z_unit = _format_unit_for_display(self.z_label_unit)

        fig1 = Figure(figsize=(6, 6), dpi=100)
        canvas1 = FigureCanvas(fig1)
        ax1 = fig1.add_subplot(111)
        norm = TwoSlopeNorm(vmin=best_fit.min(), vcenter=0, vmax=best_fit.max())
        ax1.contourf(probe, time, best_fit, cmap='seismic', norm=norm, levels=100)
        ax1.set_title(f'Fitted data' if use_convolved_model else 'Fit data')
        ax1.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        ax1.set_ylabel(f'{self.y_label_label} ({formatted_y_unit})')
        fig1.tight_layout();
        ax1.minorticks_on()
        self.plot1_vbox.addWidget(NavigationToolbar(canvas1, self.widget_GF));
        self.plot1_vbox.addWidget(canvas1)

        fig2 = Figure(figsize=(6, 6), dpi=100)
        canvas2 = FigureCanvas(fig2)
        ax2 = fig2.add_subplot(111)

        method = self.das_interp_method_combo.currentText()
        try:
            multiplier = int(self.das_interp_multiplier_combo.currentText().replace('x', ''))
        except ValueError:
            multiplier = 1

        for i in range(A_final.shape[0]):
            interp_probe, interp_A = self._get_interpolated_1d_data(probe, A_final[i, :], method, multiplier)
            ax2.plot(interp_probe, interp_A, linewidth=2, label=f'τ = {best_taus[i]:.2g} {formatted_y_unit}')

        ax2.set_title('DAS spectra')
        ax2.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        ax2.set_ylabel(f'{self.z_label_label} ({formatted_z_unit})')
        ax2.legend()
        ax2.grid(True)
        fig2.tight_layout()
        ax2.minorticks_on()
        self.plot2_vbox.addWidget(NavigationToolbar(canvas2, self.widget_2_GF))
        self.plot2_vbox.addWidget(canvas2)

        fig3 = Figure(figsize=(6, 6), dpi=100)
        canvas3 = FigureCanvas(fig3)
        ax3 = fig3.add_subplot(111)
        for p_val in probes_to_plot:
            idx = find(probe, p_val)
            ax3.plot(time, data_sliced[:, idx], '-', linewidth=2, label=f'{p_val} {formatted_x_unit}')
            ax3.plot(time, best_fit[:, idx], '-', linewidth=1, color='k')
        ax3.set_title('Time Traces with Fits')
        ax3.set_xlabel(f'{self.y_label_label} ({formatted_y_unit})')
        ax3.set_ylabel(f'{self.z_label_label} ({formatted_z_unit})')
        ax3.legend()
        ax3.grid(True)
        fig3.tight_layout()
        ax3.minorticks_on()
        self.plot3_vbox.addWidget(NavigationToolbar(canvas3, self.widget_3_GF))
        self.plot3_vbox.addWidget(canvas3)

    def handle_error(self, message):
        self.run_button.setDisabled(False)
        QMessageBox.critical(self, "Analysis Error", message)

    def export_fit_results(self):
        if getattr(self, 'best_fit_data', None) is None:
            QMessageBox.warning(self, "No Data", "Please run the global fit analysis before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Artifact Global Fit Data", "", "CSV Files (*.csv)")
        if not file_path: return
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path).split('.')[0]

        try:
            pd.DataFrame(self.A_final_data.T, index=self.probe_data, columns=self.labels).to_csv(os.path.join(dir_name, f"{base_name}_DAS.csv"))
            pd.DataFrame(self.best_fit_data, index=self.time_data, columns=self.probe_data).to_csv(os.path.join(dir_name, f"{base_name}_2D_fitted_data.csv"))
            traces_df = pd.DataFrame({"Time": self.time_data})
            for p_val in self.probes_to_plot_data:
                idx = find(self.probe_data, p_val)
                traces_df[f"Trace at {p_val}"] = self.data_sliced_for_export[:, idx]
                traces_df[f"{p_val} (Fit)"] = self.best_fit_data[:, idx]
            traces_df.to_csv(os.path.join(dir_name, f"{base_name}_time_traces.csv"), index=False)
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{dir_name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error: {e}")


def multi_gaussian(x, *params):
    y = np.zeros_like(x)
    for i in range(0, len(params), 3):
        amp, pos, fwhm = params[i:i + 3]
        fwhm = max(1e-9, abs(fwhm))
        y += amp * np.exp(-(x - pos) ** 2 / (2 * (fwhm / (2 * np.sqrt(2 * np.log(2)))) ** 2))
    return y


def multi_lorentzian(x, *params):
    y_sum = np.zeros_like(x, dtype=float)
    for i in range(0, len(params), 3):
        amp, mean, fwhm = params[i:i + 3]
        fwhm = max(1e-9, abs(fwhm))
        gamma = fwhm / 2.0
        y_sum += amp * (gamma ** 2 / ((x - mean) ** 2 + gamma ** 2))
    return y_sum


def multi_voigt(x, *params):
    y_sum = np.zeros_like(x, dtype=float)
    for i in range(0, len(params), 3):
        amp, pos, fwhm = params[i:i + 3]
        fwhm = max(1e-9, abs(fwhm))
        sigma = fwhm / 3.6013
        gamma = fwhm / 3.6013
        vp = voigt_profile(x - pos, sigma, gamma)
        vp0 = voigt_profile(0, sigma, gamma)
        if vp0 > 0:
            y_sum += amp * (vp / vp0)
    return y_sum


def exponential(x, amp, tau): return amp * np.exp(-x / tau)


def multi_exponential(x, *params):
    offset = params[-1]
    y = np.full_like(x, offset, dtype=float)
    for i in range(0, len(params) - 1, 2): y += exponential(x, params[i], params[i + 1])
    return y


class BaseFitterApp(QMainWindow):
    """
    A base class handling all the UI boilerplate, plot injection, and standard
    button connections for the various 1D fitting modules.
    """

    def __init__(self, parent=None, x_data=None, y_data=None, xlabel="X-axis", ylabel="Y-axis", title_prefix="Fitter", slice_axis_name="", slice_value=None, slice_unit=""):
        super().__init__(parent)
        self.x_data = np.array(x_data) if x_data is not None else np.array([])
        self.y_data = np.array(y_data) if y_data is not None else np.array([])
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.slice_axis_name = slice_axis_name
        self.slice_value = slice_value
        self.slice_unit = slice_unit
        self.is_guessing_mode_active = False

        title_parts = [title_prefix]
        if slice_axis_name and slice_value is not None:
            title_parts.append(f"{slice_axis_name} = {slice_value:.1f}{slice_unit}")
        title = " ".join(title_parts)
        self.setWindowTitle(title)
        self.setObjectName(title)

        # Colors for individual fit components
        self.component_colors = [
            (255, 0, 0, 200),  # Red
            (0, 0, 255, 200),  # Blue
            (255, 165, 0, 200),  # Orange
            (128, 0, 128, 200),  # Purple
            (0, 200, 200, 200),  # Cyan
            (255, 20, 147, 200),  # Pink
            (139, 69, 19, 200)  # Brown
        ]

    def _get_true_mouse_coords(self, event_scene_pos):
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event_scene_pos)
        x_val, y_val = mouse_point.x(), mouse_point.y()
        x_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.plot_widget.getPlotItem().getAxis('left')
        if getattr(x_axis, 'symlog_mode', False): x_val = inverse_symlog(x_val, x_axis.linthresh)
        if getattr(y_axis, 'symlog_mode', False): y_val = inverse_symlog(y_val, y_axis.linthresh)
        return x_val, y_val

    def setup_base_ui(self, plot_widget_to_replace, start_btn, fit_btn, clear_btn, export_btn, text_edit):
        """Standardizes the UI mapping and sets up the PyQtGraph plot."""
        self.start_guess_button = start_btn
        self.fit_button = fit_btn
        self.clear_button = clear_btn
        self.export_button = export_btn
        self.params_text_edit = text_edit

        layout = plot_widget_to_replace.parentWidget().layout()
        idx = layout.indexOf(plot_widget_to_replace)
        layout.removeWidget(plot_widget_to_replace)
        plot_widget_to_replace.deleteLater()

        self.plot_widget = pg.PlotWidget(background='w')
        self.plot_widget.setLabel('bottom', self.xlabel)
        self.plot_widget.setLabel('left', self.ylabel)
        add_symlog_to_plot_widget(self.plot_widget)
        self.legend = self.plot_widget.addLegend()

        layout.insertWidget(idx, self.plot_widget)

        self.start_guess_button.clicked.connect(self._toggle_guessing_mode)
        self.fit_button.clicked.connect(self.on_fit)
        self.export_button.clicked.connect(self.export_fit_data)
        self.clear_button.clicked.connect(self.on_clear_guesses)
        self.plot_widget.scene().sigMouseClicked.connect(self.on_click)
        self.plot_widget.scene().sigMouseMoved.connect(self.on_motion)

    def _toggle_guessing_mode(self):
        self.is_guessing_mode_active = not self.is_guessing_mode_active
        self.start_guess_button.setText("Stop Initial Guess" if self.is_guessing_mode_active else "Start Initial Guess")
        self.reset_current_guess()
        self.update_plot()

    def reset_current_guess(self):
        pass

    def on_click(self, event):
        pass

    def on_motion(self, event):
        pass

    def on_fit(self):
        pass

    def on_clear_guesses(self):
        pass

    def export_fit_data(self):
        pass

    def update_plot(self):
        pass


class ExponentialFitterApp(BaseFitterApp):
    def __init__(self, parent=None, x_data=None, y_data=None, xlabel="X-axis", ylabel="Y-axis", slice_axis_name="", slice_value=None, slice_unit="", is_spline_corrected=False):
        super().__init__(parent, x_data, y_data, xlabel, ylabel, "Exponential:", slice_axis_name, slice_value, slice_unit)
        uic.loadUi(resource_path('exponential_fit_UI.ui'), self)

        self.setup_base_ui(
            plot_widget_to_replace=self.widget_3_EF,
            start_btn=self.pushButton_EF,
            fit_btn=self.pushButton_2_EF,
            clear_btn=self.pushButton_3_EF,
            export_btn=self.pushButton_4_EF,
            text_edit=self.textEdit_EF
        )

        self.init_fitter_variables()
        self.export_button.setDisabled(True)
        self.update_plot()

    def init_fitter_variables(self):
        self.current_component = None
        self.start_x = None
        self.fixed_components = []
        self.fitted_params = None
        self.fitted_errors = None

    def reset_current_guess(self):
        self.current_component = None

    def on_click(self, event):
        if not self.is_guessing_mode_active: return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.plot_widget.sceneBoundingRect().contains(event.scenePos()):
                x_val, y_val = self._get_true_mouse_coords(event.scenePos())
                if self.current_component is None:
                    self.current_component = [y_val, 1.0]
                    self.start_x = x_val
                else:
                    self.fixed_components.append(tuple(self.current_component))
                    self.current_component = None
                self.update_plot()

    def on_motion(self, event):
        if not self.is_guessing_mode_active or self.current_component is None: return
        if self.plot_widget.sceneBoundingRect().contains(event):
            x_val, y_val = self._get_true_mouse_coords(event)
            self.current_component[1] = max(0.01, abs(x_val - self.start_x))
            self.update_plot()

    def on_fit(self):
        if not self.fixed_components: return
        try:
            p0 = np.append(np.array(self.fixed_components).flatten(), 0.0)
            self.fitted_params, pcov = curve_fit(multi_exponential, self.x_data, self.y_data, p0=p0)
            self.fitted_errors = np.sqrt(np.diag(pcov))
            self.display_fitted_parameters()
            self.update_plot()
            self.export_button.setDisabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Fitting Error", str(e))

    def on_clear_guesses(self):
        self.init_fitter_variables()
        self.params_text_edit.clear()
        self.export_button.setDisabled(True)
        self.update_plot()

    def export_fit_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Data", "", "CSV (*.csv)")
        if file_path:
            df = pd.DataFrame({self.xlabel: self.x_data, f"Data ({self.ylabel})": self.y_data, "Fit": multi_exponential(self.x_data, *self.fitted_params)})
            offset = self.fitted_params[-1]
            for i in range(0, len(self.fitted_params) - 1, 2):
                df[f"Component_{i // 2 + 1}"] = exponential(self.x_data, *self.fitted_params[i:i + 2])
            df["Global_Offset"] = offset
            df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Export", "Data successfully exported.")

    def display_fitted_parameters(self):
        if self.fitted_params is None or self.fitted_errors is None: return
        output = f"--- Exponential Fit Results ---\n\n"
        for i in range(0, len(self.fitted_params) - 1, 2):
            amp, tau = self.fitted_params[i:i + 2]
            amp_err, tau_err = self.fitted_errors[i:i + 2]
            output += f"Component {i // 2 + 1}:\n"
            output += f"  Amp: {amp:.4g} ± {amp_err:.4g}\n"
            output += f"  Tau: {tau:.4g} ± {tau_err:.4g}\n\n"

        offset = self.fitted_params[-1]
        offset_err = self.fitted_errors[-1]
        output += f"Global Offset:\n  {offset:.4g} ± {offset_err:.4g}\n\n"
        self.params_text_edit.setText(output)

    def update_plot(self):
        self.plot_widget.clear()
        sort_idx = np.argsort(self.x_data)
        xs = self.x_data[sort_idx]
        ys = self.y_data[sort_idx]

        self.plot_widget.plot(xs, ys, pen=pg.mkPen('b', width=2), name='Data')

        if self.fitted_params is None and (self.fixed_components or self.current_component):
            y_guess = np.zeros_like(xs, dtype=float)
            for amp, tau in self.fixed_components: y_guess += exponential(xs, amp, tau)
            if self.current_component: y_guess += exponential(xs, *self.current_component)
            self.plot_widget.plot(xs, y_guess, pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine), name='Guess')

        if self.fitted_params is not None:
            self.plot_widget.plot(xs, multi_exponential(xs, *self.fitted_params), pen=pg.mkPen('g', width=3), name='Total Fit')
            offset = self.fitted_params[-1]
            for i in range(0, len(self.fitted_params) - 1, 2):
                comp_idx = i // 2
                color = self.component_colors[comp_idx % len(self.component_colors)]
                self.plot_widget.plot(xs, exponential(xs, *self.fitted_params[i:i + 2]) + offset, pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine), name=f'Comp {comp_idx + 1}')

            y_axis = self.plot_widget.getPlotItem().getAxis('left')
            if getattr(y_axis, 'symlog_mode', False):
                offset_pos = symlog_transform(offset, y_axis.linthresh)
            else:
                offset_pos = offset

            offset_line = pg.InfiniteLine(angle=0, pos=offset_pos, pen=pg.mkPen('gray', width=2, style=Qt.PenStyle.DotLine), name='Offset')
            self.plot_widget.addItem(offset_line)


class GaussianFitterApp(BaseFitterApp):
    def __init__(self, parent=None, x_data=None, y_data=None, fitting_function_type="Gaussian", xlabel="X-axis", ylabel="Y-axis", slice_axis_name="", slice_value=None, slice_unit="", is_spline_corrected=False):
        self.fitting_function_type = fitting_function_type.capitalize()
        title_prefix = f"{self.fitting_function_type} Fitter:"

        super().__init__(parent, x_data, y_data, xlabel, ylabel, title_prefix, slice_axis_name, slice_value, slice_unit)
        uic.loadUi(resource_path('peak_fit_UI.ui'), self)

        self.setup_base_ui(
            plot_widget_to_replace=self.widget_4_PF,
            start_btn=self.pushButton_PF,
            fit_btn=self.pushButton_2_PF,
            clear_btn=self.pushButton_3_PF,
            export_btn=self.pushButton_4_PF,
            text_edit=self.textEdit
        )

        self.init_fitter_variables()
        self.export_button.setDisabled(True)
        self.update_plot()

    def init_fitter_variables(self):
        self.amp = None
        self.pos = None
        self.fwhm = None
        self.start_x = None
        self.fixed_peaks = []
        self.fitted_params = None
        self.fitted_errors = None

    def reset_current_guess(self):
        self.amp = None

    def get_func(self):
        if self.fitting_function_type == "Gaussian":
            return multi_gaussian
        elif self.fitting_function_type == "Lorentzian":
            return multi_lorentzian
        elif self.fitting_function_type == "Voigt":
            return multi_voigt
        return multi_gaussian

    def on_click(self, event):
        if not self.is_guessing_mode_active: return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.plot_widget.sceneBoundingRect().contains(event.scenePos()):
                x_val, y_val = self._get_true_mouse_coords(event.scenePos())
                if self.amp is None:
                    self.amp = y_val
                    self.pos = x_val
                    self.start_x = x_val
                    self.fwhm = (self.x_data.max() - self.x_data.min()) / 10 if len(self.x_data) > 0 else 1.0
                else:
                    self.fixed_peaks.append((self.amp, self.pos, self.fwhm))
                    self.amp = None
                self.update_plot()

    def on_motion(self, event):
        if not self.is_guessing_mode_active or self.amp is None: return
        if self.plot_widget.sceneBoundingRect().contains(event):
            x_val, y_val = self._get_true_mouse_coords(event)
            self.fwhm = max(0.001, 2 * abs(x_val - self.start_x))
            self.update_plot()

    def display_fitted_parameters(self):
        if self.fitted_params is None or self.fitted_errors is None: return
        output = f"--- {self.fitting_function_type} Fit Results ---\n\n"
        for i in range(0, len(self.fitted_params), 3):
            amp, pos, fwhm = self.fitted_params[i:i + 3]
            amp_err, pos_err, fwhm_err = self.fitted_errors[i:i + 3]
            output += f"Peak {i // 3 + 1}:\n"
            output += f"  Amp: {amp:.4g} ± {amp_err:.4g}\n"
            output += f"  Center: {pos:.4g} ± {pos_err:.4g}\n"
            output += f"  FWHM: {fwhm:.4g} ± {fwhm_err:.4g}\n\n"
        self.params_text_edit.setText(output)

    def on_fit(self):
        if not self.fixed_peaks: return
        try:
            func = self.get_func()
            p0 = np.array(self.fixed_peaks).flatten()
            self.fitted_params, pcov = curve_fit(func, self.x_data, self.y_data, p0=p0)
            self.fitted_errors = np.sqrt(np.diag(pcov))
            self.display_fitted_parameters()
            self.export_button.setDisabled(False)
            self.update_plot()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fit failed: {str(e)}")

    def on_clear_guesses(self):
        self.init_fitter_variables()
        self.params_text_edit.clear()
        self.export_button.setDisabled(True)
        self.update_plot()

    def export_fit_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Data", "", "CSV (*.csv)")
        if file_path:
            func = self.get_func()
            df = pd.DataFrame({self.xlabel: self.x_data, f"Data ({self.ylabel})": self.y_data, "Fit": func(self.x_data, *self.fitted_params)})
            for i in range(0, len(self.fitted_params), 3):
                df[f"Peak_{i // 3 + 1}"] = func(self.x_data, *self.fitted_params[i:i + 3])
            df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Export", "Data successfully exported.")

    def update_plot(self):
        self.plot_widget.clear()
        sort_idx = np.argsort(self.x_data)
        xs = self.x_data[sort_idx]
        ys = self.y_data[sort_idx]

        self.plot_widget.plot(xs, ys, pen=pg.mkPen('b', width=2), name='Data')
        func = self.get_func()

        if self.fitted_params is None and (self.fixed_peaks or self.amp is not None):
            y_guess = np.zeros_like(xs, dtype=float)
            for amp, pos, fwhm in self.fixed_peaks:
                y_guess += func(xs, amp, pos, fwhm)
            if self.amp is not None:
                y_guess += func(xs, self.amp, self.pos, self.fwhm)
            self.plot_widget.plot(xs, y_guess, pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine), name='Guess')

        if self.fitted_params is not None:
            self.plot_widget.plot(xs, func(xs, *self.fitted_params), pen=pg.mkPen('g', width=3), name='Total Fit')
            for i in range(0, len(self.fitted_params), 3):
                comp_idx = i // 3
                color = self.component_colors[comp_idx % len(self.component_colors)]
                self.plot_widget.plot(xs, func(xs, *self.fitted_params[i:i + 3]), pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine), name=f'Peak {comp_idx + 1}')


def signal_fitter_wrapper(parent, plot_data_item, is_x_slice, fitting_function_type, xlabel, ylabel, slice_axis_name, slice_value, slice_unit, is_spline_corrected):
    x_data, y_data = plot_data_item.getData()
    vrange = plot_data_item.getViewBox().viewRange()
    mask = (x_data >= vrange[0][0]) & (x_data <= vrange[0][1])
    if mask.sum() < 3: return None
    return GaussianFitterApp(parent, x_data[mask], y_data[mask], fitting_function_type, xlabel, ylabel, slice_axis_name, slice_value, slice_unit, is_spline_corrected)


def exponential_fitter_wrapper(parent, plot_data_item, xlabel, ylabel, slice_axis_name, slice_value, slice_unit, is_spline_corrected):
    x_data, y_data = plot_data_item.getData()
    vrange = plot_data_item.getViewBox().viewRange()
    mask = (x_data >= vrange[0][0]) & (x_data <= vrange[0][1])
    if mask.sum() < 2: return None
    return ExponentialFitterApp(parent, x_data[mask], y_data[mask], xlabel, ylabel, slice_axis_name, slice_value, slice_unit, is_spline_corrected)


# Auto dispersion correction math
def auto_find_rough_t0(times, data, method='diff', smooth=2):
    """Finds a rough time-zero for every wavelength column."""
    clean_data = np.nan_to_num(data, nan=0.0)

    if method == 'max':
        indices = np.argmax(np.abs(clean_data), axis=0)
    elif method == 'diff':
        smoothed_data = gaussian_filter(clean_data, sigma=(smooth, 0))
        derivative = np.diff(smoothed_data, axis=0)
        indices = np.argmax(np.abs(derivative), axis=0)
    else:
        indices = np.argmax(np.abs(clean_data), axis=0)

    return times[indices]


def fit_robust_dispersion_curve(wavelengths, t0_guesses, degree=2):
    """Fits a smooth polynomial through the guesses, ignoring outliers."""

    def calculate_residuals(coeffs):
        p = np.poly1d(coeffs)
        return t0_guesses - p(wavelengths)

    initial_coeffs = np.polyfit(wavelengths, t0_guesses, degree)
    result = least_squares(calculate_residuals, initial_coeffs, loss='cauchy')
    return np.poly1d(result.x)


class ChirpCorrectionApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(resource_path('dispersion_correction.ui'), self)

        self.setWindowTitle("Dispersion Correction")

        self.wavelengths = None
        self.times = None
        self.z_values = None
        self.corrected_z_cache = None
        self.current_corrected_z = None
        self.current_corrected_times = None
        self.current_corrected_wl = None
        self.current_wl_idx = 0
        self.manual_points = []
        self.coeffs = None

        self.map_ui()
        self.setup_plots()
        self.set_default_values()
        self.connect_logic_signals()

    def map_ui(self):
        self.step_input = self.chaning_every_click_DC
        self.t_min_input = self.time_range_min_DC
        self.t_max_input = self.time_range_max_DC
        self.poly_combo = self.comboBox_polynomial_order_DC
        self.wl_min_input = self.pixel_range_min_DC
        self.wl_max_input = self.pixel_range_max_DC

        self.crop_t_min = self.crop_time_from_DC
        self.crop_t_max = self.crop_time_to_DC
        self.crop_wl_min = self.crop_pixel_from_DC
        self.crop_wl_max = self.crop_pixel_to_DC

        self.bg_t_min = self.subtraction_from_DC
        self.bg_t_max = self.subtraction_to_DC

        self.shift_input = self.shift_time_delay_in_corrected_data_DC
        self.upload_loc_input = self.uploaded_location_chirp_DC

    def set_default_values(self):
        self.step_input.setText("20")
        self.t_min_input.setText("-1")
        self.t_max_input.setText("5")
        self.poly_combo.setCurrentIndex(1)
        self.wl_min_input.setText("400")
        self.wl_max_input.setText("800")

        self.crop_t_min.setText("-1")
        self.crop_t_max.setText("10")
        self.crop_wl_min.setText("400")
        self.crop_wl_max.setText("800")

        self.bg_t_min.setText("-10")
        self.bg_t_max.setText("-2")

        self.shift_input.setText("0")

        if hasattr(self, 'chirp_function_file_name_DC'):
            self.chirp_function_file_name_DC.setText("chirp_function.csv")
        if hasattr(self, 'corrected_data_file_name_DC'):
            self.corrected_data_file_name_DC.setText("corrected_data.csv")

    def setup_plots(self):
        self.Slice_along_time_DC.setBackground('w')
        self.Slice_along_time_DC.setLabel('bottom', 'Time')

        add_symlog_to_plot_widget(self.Slice_along_time_DC)

        self.slice_curve = self.Slice_along_time_DC.plot(pen=pg.mkPen('b', width=2))
        self.Slice_along_time_DC.scene().sigMouseClicked.connect(self.on_slice_clicked)

        self.contour_DC.setBackground('w')
        self.contour_DC.setLabel('bottom', 'Probe wavenumber')
        self.image_item_raw = pg.ImageItem()
        self.contour_DC.addItem(self.image_item_raw)
        self.contour_DC.scene().sigMouseClicked.connect(self.on_contour_clicked)

        self.scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen('k'), brush=pg.mkBrush(255, 0, 0, 255))
        self.contour_DC.addItem(self.scatter)
        self.fit_line = self.contour_DC.plot(pen=pg.mkPen('g', width=3, style=Qt.PenStyle.DashLine))

        self.dispersion_corrected_data_DC.setBackground('w')
        self.image_item_corr = pg.ImageItem()
        self.dispersion_corrected_data_DC.addItem(self.image_item_corr)

        self.dc_raw_zoom_timer = QTimer()
        self.dc_raw_zoom_timer.setSingleShot(True)
        self.dc_raw_zoom_timer.timeout.connect(self._recalculate_dc_raw)

        self.dc_corr_zoom_timer = QTimer()
        self.dc_corr_zoom_timer.setSingleShot(True)
        self.dc_corr_zoom_timer.timeout.connect(self._recalculate_dc_corr)

        self.contour_DC.getViewBox().sigRangeChanged.connect(lambda: self.dc_raw_zoom_timer.start(200))
        self.dispersion_corrected_data_DC.getViewBox().sigRangeChanged.connect(lambda: self.dc_corr_zoom_timer.start(200))

    def connect_logic_signals(self):
        self.finish_and_updade_corrected_data_DC.clicked.connect(self.finish_and_update)
        self.upload_chirp_DC.clicked.connect(self.select_chirp_file)
        self.chirp_upload_finish_button_DC.clicked.connect(self.apply_uploaded_chirp)
        self.revert_to_raw_data_DC.clicked.connect(self.clear_points)
        self.pushButton_5_DC.clicked.connect(self.crop_data_manually)
        self.subtract_background_button_DC.clicked.connect(self.subtract_background)

        self.pushButton_4_DC.clicked.connect(self.save_chirp_function)
        self.pushButton_2_DC.clicked.connect(self.save_corrected_data)

        self.wl_min_input.editingFinished.connect(self.update_start_index)
        self.t_min_input.editingFinished.connect(self.update_plot_limits)
        self.t_max_input.editingFinished.connect(self.update_plot_limits)

        if hasattr(self, 'auto_correct_dispersion_DC'):
            self.auto_correct_dispersion_DC.clicked.connect(self.run_auto_dispersion)

    def run_auto_dispersion(self):
        if self.z_values is None or self.times is None or self.wavelengths is None:
            QMessageBox.warning(self, "No Data", "No data available to auto-correct.")
            return

        try:
            rough_t0s = auto_find_rough_t0(self.times, self.z_values, method='diff', smooth=2)

            order_text = self.poly_combo.currentText()
            try:
                degree = int(order_text[0])
            except ValueError:
                degree = 2

            smart_chirp_func = fit_robust_dispersion_curve(self.wavelengths, rough_t0s, degree=degree)

            self.manual_points = [{'x': w, 'y': t} for w, t in zip(self.wavelengths, rough_t0s)]
            self.scatter.setData(pos=[(p['x'], p['y']) for p in self.manual_points])

            self.perform_correction_with_func(smart_chirp_func)
        except Exception as e:
            QMessageBox.critical(self, "Auto-Correct Error", f"Failed to perform auto-correction: {str(e)}")

    def _recalculate_dc_high_res(self, view_box, img_item, data, times, wavelengths):
        if data is None or times is None or wavelengths is None: return

        view_range = view_box.viewRange()
        x_min, x_max = view_range[0]
        y_min, y_max = view_range[1]

        clean_data = np.nan_to_num(data, nan=0.0)

        sort_x = np.argsort(wavelengths)
        sort_y = np.argsort(times)
        sorted_x = wavelengths[sort_x]
        sorted_y = times[sort_y]
        sorted_z = clean_data[sort_y, :][:, sort_x]

        x_mask = (sorted_x >= x_min) & (sorted_x <= x_max)
        y_mask = (sorted_y >= y_min) & (sorted_y <= y_max)

        if not np.any(x_mask) or not np.any(y_mask): return

        sliced_x = sorted_x[x_mask]
        sliced_y = sorted_y[y_mask]
        sliced_z = sorted_z[np.ix_(y_mask, x_mask)]

        if len(sliced_x) < 10 or len(sliced_y) < 10:
            img_item.setImage(sliced_z.T, autoLevels=False)
            img_item.setRect(pg.QtCore.QRectF(
                sliced_x[0], sliced_y[0],
                sliced_x[-1] - sliced_x[0],
                sliced_y[-1] - sliced_y[0]
            ))
            return

        zoom_x_interp = np.linspace(sliced_x.min(), sliced_x.max(), 1000)
        zoom_y_interp = np.linspace(sliced_y.min(), sliced_y.max(), 1000)

        try:
            interp_func = RectBivariateSpline(sliced_y, sliced_x, sliced_z)
            zoomed_z_interp = interp_func(zoom_y_interp, zoom_x_interp)

            img_item.setImage(zoomed_z_interp.T, autoLevels=False)
            img_item.setRect(pg.QtCore.QRectF(
                zoom_x_interp[0], zoom_y_interp[0],
                zoom_x_interp[-1] - zoom_x_interp[0],
                zoom_y_interp[-1] - zoom_y_interp[0]
            ))
        except Exception as e:
            pass

    def _recalculate_dc_raw(self):
        self._recalculate_dc_high_res(self.contour_DC.getViewBox(), self.image_item_raw, self.z_values, self.times, self.wavelengths)

    def _recalculate_dc_corr(self):
        self._recalculate_dc_high_res(self.dispersion_corrected_data_DC.getViewBox(), self.image_item_corr, self.current_corrected_z, self.current_corrected_times, self.current_corrected_wl)

    def update_heatmap(self, img_item, data, times=None, wavelengths=None):
        if data is None: return
        t_vec = times if times is not None else self.times
        wl_vec = wavelengths if wavelengths is not None else self.wavelengths

        clean_data = np.nan_to_num(data, nan=0.0)

        valid = clean_data[np.isfinite(clean_data)]
        lim = 1.0
        if valid.size > 0:
            lim = np.percentile(np.abs(valid), 98)
            if lim == 0:
                lim = 1e-6

        sort_x = np.argsort(wl_vec)
        sort_y = np.argsort(t_vec)
        sorted_x = wl_vec[sort_x]
        sorted_y = t_vec[sort_y]
        sorted_z = clean_data[sort_y, :][:, sort_x]

        x_interp = np.linspace(sorted_x.min(), sorted_x.max(), 1000)
        y_interp = np.linspace(sorted_y.min(), sorted_y.max(), 1000)

        try:
            interp_func = RectBivariateSpline(sorted_y, sorted_x, sorted_z)
            z_interp = interp_func(y_interp, x_interp)
        except Exception:
            z_interp = sorted_z
            x_interp = sorted_x
            y_interp = sorted_y

        img_item.setImage(z_interp.T, autoLevels=False, levels=[-lim, lim])
        rect = pg.QtCore.QRectF(x_interp[0], y_interp[0], x_interp[-1] - x_interp[0], y_interp[-1] - y_interp[0])
        img_item.setRect(rect)

        colors = [(0, 0, 255, 255), (255, 255, 255, 255), (255, 0, 0, 255)]
        pos = np.array([0.0, 0.5, 1.0])
        cmap = pg.ColorMap(pos, colors)
        img_item.setLookupTable(cmap.getLookupTable())

    def update_plot_limits(self):
        try:
            t_min, t_max = float(self.t_min_input.text()), float(self.t_max_input.text())
            self.Slice_along_time_DC.setXRange(t_min, t_max, padding=0)
            self.contour_DC.setYRange(t_min, t_max, padding=0)
        except:
            pass

    def update_start_index(self):
        if self.wavelengths is None: return
        try:
            val = float(self.wl_min_input.text())
            self.current_wl_idx = np.argmin(np.abs(self.wavelengths - val))
            self.update_slice()
        except:
            pass

    def update_slice(self):
        if self.z_values is None: return
        self.slice_curve.setData(self.times, self.z_values[:, self.current_wl_idx])
        self.Slice_along_time_DC.setTitle(f"Probe: {self.wavelengths[self.current_wl_idx]:.2f}")

    def on_slice_clicked(self, event):
        if self.z_values is None or event.button() != Qt.MouseButton.LeftButton: return
        pos = event.scenePos()
        if self.Slice_along_time_DC.sceneBoundingRect().contains(pos):
            mouse_point = self.Slice_along_time_DC.plotItem.vb.mapSceneToView(pos)
            x_val = mouse_point.x()
            x_axis = self.Slice_along_time_DC.getPlotItem().getAxis('bottom')
            if getattr(x_axis, 'symlog_mode', False): x_val = inverse_symlog(x_val, x_axis.linthresh)

            self.manual_points.append({'x': self.wavelengths[self.current_wl_idx], 'y': x_val})
            self.scatter.setData(pos=[(p['x'], p['y']) for p in self.manual_points])
            step = int(self.step_input.text()) if self.step_input.text().isdigit() else 20
            new_idx = self.current_wl_idx + step
            if new_idx < len(self.wavelengths): self.current_wl_idx = new_idx
            self.update_slice()

    def on_contour_clicked(self, event):
        if self.z_values is None or event.button() != Qt.MouseButton.LeftButton: return
        pos = event.scenePos()
        if self.contour_DC.sceneBoundingRect().contains(pos):
            pt = self.contour_DC.plotItem.vb.mapSceneToView(pos)
            self.manual_points.append({'x': pt.x(), 'y': pt.y()})
            self.scatter.setData(pos=[(p['x'], p['y']) for p in self.manual_points])

    def finish_and_update(self):
        if not self.manual_points: return
        order_text = self.poly_combo.currentText()
        try:
            order = int(order_text[0])
        except ValueError:
            order = 2
        x = [p['x'] for p in self.manual_points]
        y = [p['y'] for p in self.manual_points]
        self.coeffs = np.polyfit(x, y, order)
        self.perform_correction_with_func(np.poly1d(self.coeffs))

    def select_chirp_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Chirp File", "", "Text Files (*.txt *.csv)")
        if path: self.upload_loc_input.setText(path)

    def apply_uploaded_chirp(self):
        fname = self.upload_loc_input.text()
        if not os.path.exists(fname): return
        try:
            if fname.lower().endswith('.csv'):
                df = pd.read_csv(fname)
                x = df.iloc[:, 0].values
                y = df.iloc[:, 1].values
            else:
                data = np.loadtxt(fname, delimiter=",")
                if data.ndim == 1:
                    func = np.poly1d(data)
                    self.perform_correction_with_func(func)
                    return
                else:
                    x, y = data[:, 0], data[:, 1]

            valid = ~np.isnan(x) & ~np.isnan(y)
            x, y = x[valid], y[valid]
            sort_idx = np.argsort(x)
            x, y = x[sort_idx], y[sort_idx]

            func = interp1d(x, y, kind='cubic', bounds_error=False, fill_value="extrapolate")
            self.perform_correction_with_func(func)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply loaded chirp: {str(e)}")

    def perform_correction_with_func(self, func):
        self.current_chirp_func = func
        x_fit = np.linspace(self.wavelengths.min(), self.wavelengths.max(), 500)
        self.fit_line.setData(x_fit, func(x_fit))
        self.corrected_z_cache = np.zeros_like(self.z_values)

        t0_shifts = func(self.wavelengths)
        for i, wl in enumerate(self.wavelengths):
            t0_shift = t0_shifts[i]
            f_interp = interp1d(self.times, self.z_values[:, i], bounds_error=False, fill_value=0.0)
            self.corrected_z_cache[:, i] = f_interp(self.times + t0_shift)

        valid_t_min = np.max(self.times.min() - t0_shifts)
        valid_t_max = np.min(self.times.max() - t0_shifts)

        valid_t_min = max(valid_t_min, self.times.min())
        valid_t_max = min(valid_t_max, self.times.max())

        self.crop_t_min.setText(f"{valid_t_min:.3f}")
        self.crop_t_max.setText(f"{valid_t_max:.3f}")

        self.crop_wl_min.setText(f"{self.wavelengths.min():.1f}")
        self.crop_wl_max.setText(f"{self.wavelengths.max():.1f}")

        self.crop_data_manually()

    def save_chirp_function(self):
        if getattr(self, 'current_chirp_func', None) is None:
            QMessageBox.warning(self, "No Fit", "No chirp fit generated yet.")
            return

        default_name = self.chirp_function_file_name_DC.text().strip() or "chirp_function.csv"
        if not default_name.endswith('.csv'):
            default_name += '.csv'

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Chirp Function", default_name, "CSV Files (*.csv)")
        if not file_path: return

        try:
            wl_dense = np.linspace(self.wavelengths.min(), self.wavelengths.max(), 2000)
            shift_dense = self.current_chirp_func(wl_dense)
            df = pd.DataFrame({"Wavelength": wl_dense, "Time_Shift": shift_dense})
            df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Success", f"Chirp function saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving chirp function: {str(e)}")

    def save_corrected_data(self):
        if getattr(self, 'current_corrected_z', None) is None:
            QMessageBox.warning(self, "No Data", "No corrected data to save.")
            return

        default_name = self.corrected_data_file_name_DC.text().strip() or "corrected_data.csv"
        if not default_name.endswith('.csv'):
            default_name += '.csv'

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Corrected Data", default_name, "CSV Files (*.csv)")
        if not file_path: return

        try:
            df = pd.DataFrame(self.current_corrected_z, index=self.current_corrected_times, columns=self.current_corrected_wl)
            df.to_csv(file_path, index_label="Time")
            QMessageBox.information(self, "Success", f"Corrected data saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving corrected data: {str(e)}")

    def subtract_background(self):
        if self.corrected_z_cache is None: return
        try:
            t1, t2 = float(self.bg_t_min.text()), float(self.bg_t_max.text())
            mask = (self.times >= t1) & (self.times <= t2)
            bg = np.nanmean(self.corrected_z_cache[mask, :], axis=0)
            self.corrected_z_cache -= bg
            self.crop_data_manually()
        except Exception as e:
            print("Background Subtraction Error:", e)

    def crop_data_manually(self):
        if self.corrected_z_cache is None: return
        try:
            t1, t2 = float(self.crop_t_min.text()), float(self.crop_t_max.text())
            w1, w2 = float(self.crop_wl_min.text()), float(self.crop_wl_max.text())
            try:
                shift = float(self.shift_input.text())
            except:
                shift = 0.0
            tm = (self.times >= t1) & (self.times <= t2)
            wm = (self.wavelengths >= w1) & (self.wavelengths <= w2)
            self.current_corrected_times = self.times[tm] + shift
            self.current_corrected_wl = self.wavelengths[wm]
            self.current_corrected_z = self.corrected_z_cache[tm, :][:, wm]
            self.update_heatmap(self.image_item_corr, self.current_corrected_z,
                                self.current_corrected_times, self.current_corrected_wl)
        except Exception as e:
            print("Crop Error:", e)

    def sync_corrected_view(self):
        try:
            shift = float(self.shift_input.text())
        except:
            shift = 0.0
        self.current_corrected_z = self.corrected_z_cache.copy()
        self.current_corrected_times = self.times.copy() + shift
        self.current_corrected_wl = self.wavelengths.copy()
        self.update_heatmap(self.image_item_corr, self.current_corrected_z,
                            self.current_corrected_times, self.current_corrected_wl)

    def clear_points(self):
        self.manual_points = []
        self.scatter.setData(pos=[])
        self.current_corrected_z = None
        self.corrected_z_cache = None
        self.image_item_corr.clear()
        self.update_start_index()


class ArtifactGlobalFitApp(QMainWindow):
    def __init__(self, x_axis_data=None, y_axis_data=None, two_d_spectrum_data=None, parent=None,
                 x_axis_label='Probe wavenumber', y_axis_label='Time', z_axis_label='ΔOD',
                 x_axis_unit='cm\u207B\u00B9', y_axis_unit='ps', z_axis_unit='mOD', font_size=12):
        super().__init__(parent)
        uic.loadUi(resource_path('coherent_artifact_included_GF.ui'), self)

        self.setWindowTitle("Artifact included Global Fit")
        self.setObjectName("Artifact included Global Fit")

        self.x_axis_data = x_axis_data
        self.y_axis_data = y_axis_data
        self.two_d_spectrum_data = two_d_spectrum_data
        self.x_axis_label = x_axis_label
        self.y_axis_label = y_axis_label
        self.z_axis_label = z_axis_label
        self.x_axis_unit = x_axis_unit
        self.y_axis_unit = y_axis_unit
        self.z_axis_unit = z_axis_unit
        self.font_size = font_size
        self.worker_thread = None
        self.last_results = None

        self.map_ui()
        self.update_axis_labels(self.x_axis_label, self.x_axis_unit, self.y_axis_label, self.y_axis_unit, self.z_axis_label, self.z_axis_unit)

    def _get_interpolated_1d_data(self, original_x, original_y, method, multiplier):
        if method == "None" or len(original_x) < 2:
            return np.copy(original_x), np.copy(original_y)
        try:
            target_n_points = int(len(original_x) * multiplier)
            if target_n_points < 2:
                target_n_points = 2
            x_interp = np.linspace(original_x.min(), original_x.max(), target_n_points)
            f_interp = interp1d(original_x, original_y, kind=method.lower(), fill_value="extrapolate")
            y_interp = f_interp(x_interp)
            return x_interp, y_interp
        except Exception as e:
            return np.copy(original_x), np.copy(original_y)

    def _replot_das(self):
        if not hasattr(self, 'last_results') or not self.last_results:
            return
        self.plot_results(self.last_results)

    def map_ui(self):
        self.time_min_input = getattr(self, 'time_min_CA', getattr(self, 'lineEdit_CA', None))
        self.time_max_input = getattr(self, 'time_max_CA', getattr(self, 'lineEdit_2_CA', None))
        self.probe_min_input = getattr(self, 'probe_min_CA', getattr(self, 'lineEdit_3_CA', None))
        self.probe_max_input = getattr(self, 'probe_max_CA', getattr(self, 'lineEdit_4_CA', None))
        self.tau_guesses_input = getattr(self, 'Tau_initial_guesses_CA', getattr(self, 'lineEdit_5_CA', None))
        self.d_input = getattr(self, 'pulse_initial_guess_CA', getattr(self, 'lineEdit_6_CA', None))
        self.probes_input = self.lineEdit_7_CA

        self.das_interp_method_combo = getattr(self, 'comboBox_CA', None)
        self.das_interp_multiplier_combo = getattr(self, 'comboBox_2_CA', None)

        self.run_button = self.pushButton_CA
        self.export_button = self.pushButton_2_CA
        self.results_text_edit = self.textEdit_CA

        self.run_button.clicked.connect(self.run_analysis)
        self.export_button.clicked.connect(self.export_fit_results)
        self.export_button.setDisabled(True)

        if self.das_interp_method_combo:
            self.das_interp_method_combo.currentIndexChanged.connect(self._replot_das)
        if self.das_interp_multiplier_combo:
            self.das_interp_multiplier_combo.currentIndexChanged.connect(self._replot_das)

        layout_plots = self.widget_3_CA.layout()

        idx1 = layout_plots.indexOf(self.widget_6_CA)
        layout_plots.removeWidget(self.widget_6_CA)
        self.widget_6_CA.deleteLater()
        self.plot1_widget = QWidget()
        self.plot1_vbox = QVBoxLayout(self.plot1_widget)
        layout_plots.insertWidget(idx1, self.plot1_widget)

        idx2 = layout_plots.indexOf(self.widget_7_CA)
        layout_plots.removeWidget(self.widget_7_CA)
        self.widget_7_CA.deleteLater()
        self.plot2_widget = QWidget()
        self.plot2_vbox = QVBoxLayout(self.plot2_widget)
        layout_plots.insertWidget(idx2, self.plot2_widget)

        idx3 = layout_plots.indexOf(self.widget_8)
        layout_plots.removeWidget(self.widget_8)
        self.widget_8.deleteLater()
        self.plot3_widget = QWidget()
        self.plot3_vbox = QVBoxLayout(self.plot3_widget)
        layout_plots.insertWidget(idx3, self.plot3_widget)

        if self.x_axis_data is not None and len(self.x_axis_data) > 0:
            self.probe_min_input.setText(f"{np.min(self.x_axis_data):.2f}")
            self.probe_max_input.setText(f"{np.max(self.x_axis_data):.2f}")
        else:
            self.probe_min_input.setText("1900")
            self.probe_max_input.setText("2100")

        if self.y_axis_data is not None and len(self.y_axis_data) > 0:
            self.time_min_input.setText(f"{np.min(self.y_axis_data):.2f}")
            self.time_max_input.setText(f"{np.max(self.y_axis_data):.2f}")
        else:
            self.time_min_input.setText("1.0")
            self.time_max_input.setText("80.0")

        self.d_input.setText("0.028")
        self.tau_guesses_input.setText("0.11, 1.27, 8.33, 2.0, 20.0")
        self.probes_input.setText("420, 530, 640")

    def update_axis_labels(self, x_label, x_unit, y_label, y_unit, z_label, z_unit):
        self.x_axis_label = x_label
        self.x_axis_unit = x_unit
        self.y_axis_label = y_label
        self.y_axis_unit = y_unit
        self.z_axis_label = z_label
        self.z_axis_unit = z_unit
        if self.last_results is not None:
            self.plot_results(self.last_results)

    def run_analysis(self):
        try:
            tau_guesses = [float(t.strip()) for t in self.tau_guesses_input.text().split(',') if t.strip()]
            params = {
                "time_min": float(self.time_min_input.text()),
                "time_max": float(self.time_max_input.text()),
                "probe_min": float(self.probe_min_input.text()),
                "probe_max": float(self.probe_max_input.text()),
                "d_guess": float(self.d_input.text().strip()),
                "tau_guesses": tau_guesses,
                "probes_to_plot": [float(p.strip()) for p in self.probes_input.text().split(',') if p.strip()],
                "x_axis": self.x_axis_data, "y_axis": self.y_axis_data, "two_d_spectrum": self.two_d_spectrum_data
            }
            self.results_text_edit.clear()
            self.run_button.setDisabled(True)
            self.worker_thread = LuisFitWorker(params)
            self.worker_thread.finished.connect(self.plot_results)
            self.worker_thread.error.connect(self.handle_error)
            self.worker_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Input Error", f"Check inputs. Error: {e}")
            self.run_button.setDisabled(False)

    def plot_results(self, results):
        self.run_button.setDisabled(False)
        if not results: return
        self.last_results = results
        (best_fit, A_final, best_t0, best_d, best_taus, r_squared, probe, time, data_sliced, probes_to_plot, fit_report_string) = results

        self.best_fit_data = best_fit
        self.A_final_data = A_final
        self.probe_data = probe
        self.time_data = time
        self.data_sliced_for_export = data_sliced
        self.probes_to_plot_data = probes_to_plot
        self.export_button.setEnabled(True)

        formatted_y_unit = _format_unit_for_display(self.y_axis_unit)
        self.labels = ["G(t)", "G'(t)", "G''(t)", "Constant"]
        for tau in best_taus:
            self.labels.append(f"τ = {tau:.3g} {formatted_y_unit}")

        output_text = f"--- Artifact included Global Fit Results ---\n\nOverall R-squared: {r_squared:.4f}\nBest t0: {best_t0:.4g}\nBest d: {best_d:.4g}\nBest τ values ({formatted_y_unit}): {[f'{t:.3g}' for t in best_taus]}\n\n--- Full lmfit Report ---\n{fit_report_string}"
        self.results_text_edit.setText(output_text)

        def clear_layout(layout):
            while layout.count():
                child = layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()

        clear_layout(self.plot1_vbox)
        clear_layout(self.plot2_vbox)
        clear_layout(self.plot3_vbox)

        plt.rcParams.update({'font.size': self.font_size})
        formatted_x_unit = _format_unit_for_display(self.x_axis_unit)
        formatted_y_unit = _format_unit_for_display(self.y_axis_unit)
        formatted_z_unit = _format_unit_for_display(self.z_axis_unit)

        fig1 = Figure(figsize=(6, 6), dpi=100)
        canvas1 = FigureCanvas(fig1)
        ax1 = fig1.add_subplot(111)
        norm = TwoSlopeNorm(vmin=best_fit.min(), vcenter=0, vmax=best_fit.max())
        ax1.contourf(probe, time, best_fit, cmap='seismic', norm=norm, levels=100)
        ax1.set_title('Fitted data (Artifact Model)')
        ax1.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        ax1.set_ylabel(f'{self.y_axis_label} ({formatted_y_unit})')
        fig1.tight_layout()
        ax1.minorticks_on()
        self.plot1_vbox.addWidget(NavigationToolbar(canvas1, self.plot1_widget))
        self.plot1_vbox.addWidget(canvas1)

        fig2 = Figure(figsize=(6, 6), dpi=100)
        canvas2 = FigureCanvas(fig2)
        ax2 = fig2.add_subplot(111)

        method = self.das_interp_method_combo.currentText() if self.das_interp_method_combo else "None"
        try:
            multiplier = int(self.das_interp_multiplier_combo.currentText().replace('x', '')) if self.das_interp_multiplier_combo else 1
        except ValueError:
            multiplier = 1

        for i in range(3, A_final.shape[0]):
            interp_probe, interp_A = self._get_interpolated_1d_data(probe, A_final[i, :], method, multiplier)
            ax2.plot(interp_probe, interp_A, linewidth=2, label=self.labels[i])

        ax2.set_title('DAS spectra (Basis Amplitudes)')
        ax2.set_xlabel(f'{self.x_axis_label} ({formatted_x_unit})')
        ax2.set_ylabel(f'{self.z_axis_label} ({formatted_z_unit})')
        ax2.legend()
        ax2.grid(True)
        fig2.tight_layout()
        ax2.minorticks_on()
        self.plot2_vbox.addWidget(NavigationToolbar(canvas2, self.plot2_widget))
        self.plot2_vbox.addWidget(canvas2)

        fig3 = Figure(figsize=(6, 6), dpi=100)
        canvas3 = FigureCanvas(fig3)
        ax3 = fig3.add_subplot(111)
        for p_val in probes_to_plot:
            idx = find(probe, p_val)
            ax3.plot(time, data_sliced[:, idx], '-', linewidth=2, label=f'{p_val} {formatted_x_unit}')
            ax3.plot(time, best_fit[:, idx], '-', linewidth=1, color='k')
        ax3.set_title('Time Traces with Fits')
        ax3.set_xlabel(f'{self.y_axis_label} ({formatted_y_unit})')
        ax3.set_ylabel(f'{self.z_axis_label} ({formatted_z_unit})')
        ax3.legend()
        ax3.grid(True)
        fig3.tight_layout()
        ax3.minorticks_on()
        self.plot3_vbox.addWidget(NavigationToolbar(canvas3, self.plot3_widget))
        self.plot3_vbox.addWidget(canvas3)

    def handle_error(self, message):
        self.run_button.setDisabled(False)
        QMessageBox.critical(self, "Analysis Error", message)

    def export_fit_results(self):
        if getattr(self, 'best_fit_data', None) is None:
            QMessageBox.warning(self, "No Data", "Please run the global fit analysis before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Artifact Global Fit Data", "", "CSV Files (*.csv)")
        if not file_path: return
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path).split('.')[0]

        try:
            pd.DataFrame(self.A_final_data.T, index=self.probe_data, columns=self.labels).to_csv(os.path.join(dir_name, f"{base_name}_DAS.csv"))
            pd.DataFrame(self.best_fit_data, index=self.time_data, columns=self.probe_data).to_csv(os.path.join(dir_name, f"{base_name}_2D_fitted_data.csv"))
            traces_df = pd.DataFrame({"Time": self.time_data})
            for p_val in self.probes_to_plot_data:
                idx = find(self.probe_data, p_val)
                traces_df[f"Trace at {p_val}"] = self.data_sliced_for_export[:, idx]
                traces_df[f"{p_val} (Fit)"] = self.best_fit_data[:, idx]
            traces_df.to_csv(os.path.join(dir_name, f"{base_name}_time_traces.csv"), index=False)
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{dir_name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error: {e}")


class SignalPlotterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path('mainwindow.ui'), self)

        self.base_title = "Kaalen-v3.0"
        self._current_project_file = None
        self._data_modified = False
        self._update_window_title()

        self.held_x_slices_count = 0
        self.held_y_slices_count = 0
        self.held_x_curves = []
        self.held_y_curves = []

        self.plot_colors = [(255, 0, 0), (0, 0, 255), (0, 200, 0), (255, 165, 0), (128, 0, 128)]

        self.data_loaded = False
        self._initial_raw_signal_data = None
        self.is_spline_corrected = False
        self._current_interp_method = "None"
        self._current_interp_multiplier = 1

        self.active_fitter_tabs = []

        # Centralized UI Labels and Units. Can be changed in the Edit names if needed during analyss
        self.global_x_label = 'Probe wavenumber'
        self.global_x_unit = 'cm\u207B\u00B9'
        self.global_y_label = 'Time'
        self.global_y_unit = 'ps'
        self.global_z_label = 'ΔOD'
        self.global_z_unit = 'mOD'

        self.current_slice_linewidth = 2

        self.map_ui_and_reorganize()

    def _on_contour_symlog_toggled(self):
        if self.data_loaded:
            self._update_2d_contour(reset_levels=False)
            self.update_plots()

    def map_ui_and_reorganize(self):
        central_widget = self.centralwidget_MW
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.tab_widget.tabBar().tabBarDoubleClicked.connect(self.rename_tab)

        self.main_tab = QWidget()
        layout = QVBoxLayout(self.main_tab)
        layout.addWidget(central_widget)
        self.tab_widget.addTab(self.main_tab, "Main Plots")

        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        #  Read Me Tab
        self.notes_tab = QWidget()
        notes_layout = QVBoxLayout(self.notes_tab)

        # Font size controls
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        self.notes_font_spinbox = QSpinBox()
        self.notes_font_spinbox.setRange(8, 72)
        self.notes_font_spinbox.setValue(12)
        self.notes_font_spinbox.valueChanged.connect(self._change_notes_font_size)
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.notes_font_spinbox)
        font_layout.addStretch()
        notes_layout.addLayout(font_layout)

        self.notes_text_edit = QTextEdit()
        self.notes_text_edit.setPlaceholderText("Write your notes here...")

        font = self.notes_text_edit.font()
        font.setPointSize(12)
        self.notes_text_edit.setFont(font)

        self.notes_text_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_text_edit)
        self.tab_widget.addTab(self.notes_tab, "Read Me")

        self.tab_widget.tabBar().setTabButton(1, QTabBar.ButtonPosition.RightSide, None)
        self.tab_widget.tabBar().setTabButton(1, QTabBar.ButtonPosition.LeftSide, None)

        self.tab_widget.tabBar().tabMoved.connect(self._enforce_tab_pinning)

        self.setCentralWidget(self.tab_widget)

        self.signal_plot_widget = self.controur_MW

        # ADD SYMLOG TO MAIN 2D CONTOUR
        add_symlog_to_plot_widget(self.signal_plot_widget, on_toggle_callback=self._on_contour_symlog_toggled)

        self.x_slice_plot_widget = self.x_slice_plot_MW
        self.y_slice_plot_widget = self.y_slice_plot_MW

        add_symlog_to_plot_widget(self.x_slice_plot_widget)
        add_symlog_to_plot_widget(self.y_slice_plot_widget)

        self.x_slider = self.time_slider_MW
        self.y_slider = self.time_slider_MW_2
        self.x_input = self.probe_value_MW
        self.y_input = self.Delay_time_value_MW_2

        self.x_input.returnPressed.connect(self.update_slider_from_x_input)
        self.x_input.editingFinished.connect(self.update_slider_from_x_input)
        self.y_input.returnPressed.connect(self.update_slider_from_y_input)
        self.y_input.editingFinished.connect(self.update_slider_from_y_input)

        self.min_level_input = self.contour_min_lineedit_MW
        self.max_level_input = self.contour_max_lineedit_MW_2

        self.min_level_input.editingFinished.connect(self.update_contour_levels)
        self.max_level_input.editingFinished.connect(self.update_contour_levels)
        self.min_level_input.returnPressed.connect(self.update_contour_levels)
        self.max_level_input.returnPressed.connect(self.update_contour_levels)

        self.x_hold_button = self.hold_button_xslice_MW
        self.x_clear_button = self.clear_button_xslice_MW
        self.x_fit_button = self.fit_button_xslice_MW
        self.y_hold_button = self.hold_button_yslice_MW
        self.y_clear_button = self.clear_button_yslice_MW
        self.y_fit_button = self.fit_button_yslice_MW

        self.global_fit_button = self.global_fit_button_MW
        self.pfid_fit_button = self.pfid_fit_button_MW
        self.spline_baseline_button = self.spline_button_MW

        # Inject Artifact Global Fit Button into the same layout block
        parent_layout = self.global_fit_button.parentWidget().layout()
        if parent_layout:
            self.artifact_fit_button_MW = QPushButton("Artifact included Global fit")
            idx = parent_layout.indexOf(self.global_fit_button)
            if idx != -1:
                parent_layout.insertWidget(idx + 1, self.artifact_fit_button_MW)
            else:
                parent_layout.addWidget(self.artifact_fit_button_MW)
            self.artifact_fit_button_MW.clicked.connect(self._launch_artifact_fit_tab)

        self.y_fit_function_selector = self.comboBox_for_fit_function_MW
        if self.y_fit_function_selector.findText("Voigt") == -1:
            self.y_fit_function_selector.addItem("Voigt")

        self.interp_method_combo = self.interpolation_style_MW
        self.interp_multiplier_combo = self.interpolation_times_MW

        self.interp_method_combo.currentIndexChanged.connect(self._apply_interpolation_to_all_plots)
        self.interp_multiplier_combo.currentIndexChanged.connect(self._apply_interpolation_to_all_plots)
        self.spline_baseline_button.clicked.connect(self._toggle_spline_correction)
        self.dispersion_button_MW.clicked.connect(self.open_dispersion_correction)

        if hasattr(self, 'cursor_position_MW'):
            self.cursor_position_MW.setText("X: -, Y: -")

        self.image_item = pg.ImageItem()
        pos = np.array([0.0, 0.5, 1.0])
        color = np.array([[0, 0, 255, 255], [255, 255, 255, 255], [255, 0, 0, 255]], dtype=np.ubyte)
        cmap = pg.ColorMap(pos, color)
        self.image_item.setColorMap(cmap)
        self.signal_plot_widget.addItem(self.image_item)

        self.x_slice_curve = self.x_slice_plot_widget.plot(pen=pg.mkPen('b', width=2))
        self.x_slice_legend = self.x_slice_plot_widget.addLegend()

        self.y_slice_curve = self.y_slice_plot_widget.plot(pen=pg.mkPen('r', width=2))
        self.y_slice_legend = self.y_slice_plot_widget.addLegend()

        self.cursor_x_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('k', width=1, style=Qt.PenStyle.DotLine))
        self.cursor_y_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('k', width=1, style=Qt.PenStyle.DotLine))
        self.signal_plot_widget.addItem(self.cursor_x_line)
        self.signal_plot_widget.addItem(self.cursor_y_line)

        self.signal_plot_widget.scene().sigMouseMoved.connect(self.mouse_moved_contour)
        self.x_slice_plot_widget.scene().sigMouseMoved.connect(self.mouse_moved_x_slice)
        self.y_slice_plot_widget.scene().sigMouseMoved.connect(self.mouse_moved_y_slice)

        self.actionImport_Data_MW.triggered.connect(self.on_import_data_action_triggered)
        self.actionImport_Data_MW.setShortcut("Ctrl+I")

        self.actionExit_MW.triggered.connect(self._load_project)
        self.actionExit_MW.setShortcut("Ctrl+L")

        if hasattr(self, 'actionSave_Project_MW'):
            self.actionSave_Project_MW.triggered.connect(self._save_project)
            self.actionSave_Project_MW.setShortcut("Ctrl+S")

        if hasattr(self, 'actionExit_2_MW'):
            self.actionExit_2_MW.triggered.connect(self._save_project_as)
            self.actionExit_2_MW.setShortcut("Ctrl+Shift+S")

        self.actionExit_3_MW.triggered.connect(self.close)
        self.actionExit_3_MW.setShortcut("Ctrl+Q")

        if hasattr(self, 'actionEdit_Axis_Labels_MW'):
            self.actionEdit_Axis_Labels_MW.triggered.connect(self.edit_axis_labels)

        self.global_fit_button.clicked.connect(self._launch_global_fit_tab)
        self.pfid_fit_button.clicked.connect(self._launch_pfid_fit_tab)
        self.x_slider.valueChanged.connect(self.update_plots)
        self.y_slider.valueChanged.connect(self.update_plots)

        self.x_fit_button.clicked.connect(self._open_x_fitter_tab)
        self.y_fit_button.clicked.connect(self._open_y_fitter_tab)

        self.x_hold_button.clicked.connect(self.hold_x_slice)
        self.x_clear_button.clicked.connect(self.clear_x_slices)
        self.y_hold_button.clicked.connect(self.hold_y_slice)
        self.y_clear_button.clicked.connect(self.clear_y_slices)

        self._apply_axis_labels()

        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self._recalculate_high_res_contour)
        self.signal_plot_widget.getViewBox().sigRangeChanged.connect(self.on_view_changed)

    def _enforce_tab_pinning(self, from_index, to_index):
        """Prevents the Main Plots and Read Me tabs from being moved from their pinned positions (0 and 1)."""
        self.tab_widget.tabBar().blockSignals(True)
        main_idx = self.tab_widget.indexOf(self.main_tab)
        if main_idx != 0 and main_idx != -1:
            self.tab_widget.tabBar().moveTab(main_idx, 0)

        notes_idx = self.tab_widget.indexOf(self.notes_tab)
        if notes_idx != 1 and notes_idx != -1:
            self.tab_widget.tabBar().moveTab(notes_idx, 1)
        self.tab_widget.tabBar().blockSignals(False)

    def on_view_changed(self):
        if not self.data_loaded: return
        self.zoom_timer.start(200)

    def _recalculate_high_res_contour(self):
        if not self.data_loaded or self.current_signal_data is None: return

        view_box = self.signal_plot_widget.getViewBox()
        view_range = view_box.viewRange()
        x_min, x_max = view_range[0]
        y_min, y_max = view_range[1]

        sort_x = np.argsort(self.current_x_values)
        sort_y = np.argsort(self.current_y_values)
        sorted_x_vals = self.current_x_values[sort_x]
        sorted_y_vals = self.current_y_values[sort_y]
        sorted_z_data = self.current_signal_data[sort_y, :][:, sort_x]

        x_axis = self.signal_plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.signal_plot_widget.getPlotItem().getAxis('left')

        plot_x_vals = sorted_x_vals
        plot_y_vals = sorted_y_vals

        if getattr(x_axis, 'symlog_mode', False):
            plot_x_vals = symlog_transform(plot_x_vals, x_axis.linthresh)
        if getattr(y_axis, 'symlog_mode', False):
            plot_y_vals = symlog_transform(plot_y_vals, y_axis.linthresh)

        x_mask = (plot_x_vals >= x_min) & (plot_x_vals <= x_max)
        y_mask = (plot_y_vals >= y_min) & (plot_y_vals <= y_max)

        if not np.any(x_mask) or not np.any(y_mask):
            return

        sliced_x = plot_x_vals[x_mask]
        sliced_y = plot_y_vals[y_mask]
        sliced_z = sorted_z_data[np.ix_(y_mask, x_mask)]

        if len(sliced_x) < 10 or len(sliced_y) < 10:
            self.image_item.setImage(sliced_z.T, autoLevels=False)
            self.image_item.setRect(pg.QtCore.QRectF(
                sliced_x[0], sliced_y[0],
                sliced_x[-1] - sliced_x[0],
                sliced_y[-1] - sliced_y[0]
            ))
            return

        zoom_x_interp = np.linspace(sliced_x.min(), sliced_x.max(), 1000)
        zoom_y_interp = np.linspace(sliced_y.min(), sliced_y.max(), 1000)

        try:
            interp_func = RectBivariateSpline(sliced_y, sliced_x, sliced_z)
            zoomed_z_interp = interp_func(zoom_y_interp, zoom_x_interp)

            self.image_item.setImage(zoomed_z_interp.T, autoLevels=False)
            self.image_item.setRect(pg.QtCore.QRectF(
                zoom_x_interp[0], zoom_y_interp[0],
                zoom_x_interp[-1] - zoom_x_interp[0],
                zoom_y_interp[-1] - zoom_y_interp[0]
            ))
        except Exception as e:
            print(f"Dynamic zoom interpolation failed: {e}")

    def _get_ui_state(self, widget):
        """Recursively scrapes the exact state of all inputs inside a given QWidget."""
        ui_state = {}
        for child in widget.findChildren(QLineEdit):
            ui_state[child.objectName()] = child.text()
        for child in widget.findChildren(QCheckBox):
            ui_state[child.objectName()] = child.isChecked()
        for child in widget.findChildren(QComboBox):
            ui_state[child.objectName()] = child.currentText()
        for child in widget.findChildren(QSlider):
            ui_state[child.objectName()] = child.value()
        return ui_state

    def _set_ui_state(self, widget, ui_state):
        """Injects saved values back into all inputs inside a given QWidget."""
        for child in widget.findChildren(QLineEdit):
            if child.objectName() in ui_state: child.setText(ui_state[child.objectName()])
        for child in widget.findChildren(QCheckBox):
            if child.objectName() in ui_state: child.setChecked(ui_state[child.objectName()])
        for child in widget.findChildren(QComboBox):
            if child.objectName() in ui_state: child.setCurrentText(ui_state[child.objectName()])
        for child in widget.findChildren(QSlider):
            if child.objectName() in ui_state: child.setValue(ui_state[child.objectName()])

    def mouse_moved_contour(self, evt):
        if not self.data_loaded: return
        if self.signal_plot_widget.sceneBoundingRect().contains(evt):
            mouse_point = self.signal_plot_widget.getPlotItem().vb.mapSceneToView(evt)
            x_val, y_val = mouse_point.x(), mouse_point.y()
            x_axis = self.signal_plot_widget.getPlotItem().getAxis('bottom')
            y_axis = self.signal_plot_widget.getPlotItem().getAxis('left')
            if getattr(x_axis, 'symlog_mode', False): x_val = inverse_symlog(x_val, x_axis.linthresh)
            if getattr(y_axis, 'symlog_mode', False): y_val = inverse_symlog(y_val, y_axis.linthresh)
            if hasattr(self, 'cursor_position_MW'):
                self.cursor_position_MW.setText(f"X: {x_val:.2f}, Y: {y_val:.2f}")

    def mouse_moved_x_slice(self, evt):
        if not self.data_loaded: return
        if self.x_slice_plot_widget.sceneBoundingRect().contains(evt):
            mouse_point = self.x_slice_plot_widget.getPlotItem().vb.mapSceneToView(evt)
            x_val, y_val = mouse_point.x(), mouse_point.y()
            x_axis = self.x_slice_plot_widget.getPlotItem().getAxis('bottom')
            y_axis = self.x_slice_plot_widget.getPlotItem().getAxis('left')
            if getattr(x_axis, 'symlog_mode', False): x_val = inverse_symlog(x_val, x_axis.linthresh)
            if getattr(y_axis, 'symlog_mode', False): y_val = inverse_symlog(y_val, y_axis.linthresh)

            if hasattr(self, 'cursor_position_MW'):
                self.cursor_position_MW.setText(f"X: {x_val:.2f}, Y: {y_val:.4g}")

    def mouse_moved_y_slice(self, evt):
        if not self.data_loaded: return
        if self.y_slice_plot_widget.sceneBoundingRect().contains(evt):
            mouse_point = self.y_slice_plot_widget.getPlotItem().vb.mapSceneToView(evt)
            x_val, y_val = mouse_point.x(), mouse_point.y()
            x_axis = self.y_slice_plot_widget.getPlotItem().getAxis('bottom')
            y_axis = self.y_slice_plot_widget.getPlotItem().getAxis('left')
            if getattr(x_axis, 'symlog_mode', False): x_val = inverse_symlog(x_val, x_axis.linthresh)
            if getattr(y_axis, 'symlog_mode', False): y_val = inverse_symlog(y_val, y_axis.linthresh)

            if hasattr(self, 'cursor_position_MW'):
                self.cursor_position_MW.setText(f"X: {x_val:.2f}, Y: {y_val:.4g}")

    def _on_notes_changed(self):
        self._data_modified = True
        self._update_window_title()

    def _change_notes_font_size(self, size):
        font = self.notes_text_edit.font()
        font.setPointSize(size)
        self.notes_text_edit.setFont(font)
        self._data_modified = True
        self._update_window_title()

    def _update_window_title(self):
        title = self.base_title
        if self._current_project_file:
            title += f" - {os.path.basename(self._current_project_file)}"
        else:
            title += " - Unsaved"
        if self._data_modified: title += " (Unsaved Changes)"
        self.setWindowTitle(title)

    def rename_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget in (getattr(self, 'main_tab', None), getattr(self, 'notes_tab', None)):
            return
        old_name = self.tab_widget.tabText(index)
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "Enter new tab name:", QLineEdit.EchoMode.Normal, old_name)
        if ok and new_name:
            self.tab_widget.setTabText(index, new_name)
            self.tab_widget.widget(index).setObjectName(new_name)

    def close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget == getattr(self, 'main_tab', None):
            QMessageBox.information(self, "Info", "The Main Plots tab cannot be closed.")
            return
        if widget == getattr(self, 'notes_tab', None):
            QMessageBox.information(self, "Info", "The Read Me tab cannot be closed.")
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def _apply_axis_labels(self):
        self.signal_plot_widget.setLabel('bottom', f"{self.global_x_label} [{self.global_x_unit}]")
        self.signal_plot_widget.setLabel('left', f"{self.global_y_label} [{self.global_y_unit}]")

        self.x_slice_plot_widget.setLabel('bottom', f"{self.global_y_label} [{self.global_y_unit}]")
        self.x_slice_plot_widget.setLabel('left', f"{self.global_z_label} [{self.global_z_unit}]")

        self.y_slice_plot_widget.setLabel('bottom', f"{self.global_x_label} [{self.global_x_unit}]")
        self.y_slice_plot_widget.setLabel('left', f"{self.global_z_label} [{self.global_z_unit}]")

    def edit_axis_labels(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Global Axis Labels")
        layout = QGridLayout(dialog)

        x_label_input = QLineEdit(self.global_x_label)
        x_unit_input = QLineEdit(self.global_x_unit)
        y_label_input = QLineEdit(self.global_y_label)
        y_unit_input = QLineEdit(self.global_y_unit)
        z_label_input = QLineEdit(self.global_z_label)
        z_unit_input = QLineEdit(self.global_z_unit)

        layout.addWidget(QLabel("X-Axis (Probe) Label:"), 0, 0)
        layout.addWidget(x_label_input, 0, 1)
        layout.addWidget(QLabel("X-Axis Unit:"), 1, 0)
        layout.addWidget(x_unit_input, 1, 1)
        layout.addWidget(QLabel("Y-Axis (Time) Label:"), 2, 0)
        layout.addWidget(y_label_input, 2, 1)
        layout.addWidget(QLabel("Y-Axis Unit:"), 3, 0)
        layout.addWidget(y_unit_input, 3, 1)
        layout.addWidget(QLabel("Z-Axis (Signal) Label:"), 4, 0)
        layout.addWidget(z_label_input, 4, 1)
        layout.addWidget(QLabel("Z-Axis Unit:"), 5, 0)
        layout.addWidget(z_unit_input, 5, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons, 6, 0, 1, 2)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.global_x_label = x_label_input.text()
            self.global_x_unit = x_unit_input.text()
            self.global_y_label = y_label_input.text()
            self.global_y_unit = y_unit_input.text()
            self.global_z_label = z_label_input.text()
            self.global_z_unit = z_unit_input.text()

            self._data_modified = True
            self._update_window_title()
            self._apply_axis_labels()

            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if hasattr(widget, 'update_axis_labels'):
                    widget.update_axis_labels(self.global_x_label, self.global_x_unit, self.global_y_label, self.global_y_unit, self.global_z_label, self.global_z_unit)

    def update_slider_from_x_input(self):
        if not self.data_loaded: return
        try:
            val = float(self.x_input.text())
            idx = find(self.current_x_values, val)
            self.x_slider.setValue(idx)
        except ValueError:
            pass

    def update_slider_from_y_input(self):
        if not self.data_loaded: return
        try:
            val = float(self.y_input.text())
            idx = find(self.current_y_values, val)
            self.y_slider.setValue(idx)
        except ValueError:
            pass

    def update_contour_levels(self):
        if not self.data_loaded:
            return
        try:
            min_val = float(self.min_level_input.text())
            max_val = float(self.max_level_input.text())
            self.image_item.setLevels([min_val, max_val])
            self._data_modified = True
            self._update_window_title()
        except ValueError:
            pass

    def _get_interpolated_1d_data(self, original_x, original_y, method, multiplier):
        if method == "None" or len(original_x) < 2:
            return np.copy(original_x), np.copy(original_y)
        try:
            target_n_points = int(len(original_x) * multiplier)
            if target_n_points < 2:
                target_n_points = 2
            x_interp = np.linspace(original_x.min(), original_x.max(), target_n_points)
            f_interp = interp1d(original_x, original_y, kind=method.lower(), fill_value="extrapolate")
            y_interp = f_interp(x_interp)
            return x_interp, y_interp
        except Exception as e:
            print(f"Error during 1D interpolation: {e}")
            return np.copy(original_x), np.copy(original_y)

    def _apply_interpolation_to_all_plots(self):
        self._current_interp_method = self.interp_method_combo.currentText()
        try:
            self._current_interp_multiplier = int(self.interp_multiplier_combo.currentText().replace('x', ''))
        except ValueError:
            self._current_interp_multiplier = 1
        self._data_modified = True
        self._update_window_title()
        self.update_plots()

    def spline_baseline_correction(self, data, probe_wn):
        baseline = np.zeros_like(data, dtype=float)
        for i in range(data.shape[0]):
            if len(probe_wn) >= 2:
                try:
                    valid_mask = np.isfinite(data[i, :])
                    if np.sum(valid_mask) >= 2:
                        x_valid = probe_wn[valid_mask]
                        y_valid = data[i, valid_mask]
                        sort_idx = np.argsort(x_valid)
                        spline = UnivariateSpline(x_valid[sort_idx], y_valid[sort_idx])
                        baseline[i, :] = spline(probe_wn)
                    else:
                        baseline[i, :] = 0.0
                except Exception as e:
                    baseline[i, :] = 0.0
            else:
                baseline[i, :] = 0.0
        return data - baseline

    def _update_spline_button_text(self):
        if self.is_spline_corrected:
            self.spline_baseline_button.setText("Revert to Original")
        else:
            self.spline_baseline_button.setText("Use Spline Baseline")

    def _toggle_spline_correction(self):
        if not self.data_loaded:
            QMessageBox.warning(self, "No Data", "Please import data before applying spline baseline.")
            return

        if not self.is_spline_corrected:
            try:
                corrected_data = self.spline_baseline_correction(self._initial_raw_signal_data, self.current_x_values)
                self.current_signal_data = corrected_data
                self.is_spline_corrected = True
                self._update_2d_contour(reset_levels=False)
                self.update_plots()
            except Exception as e:
                print(f"Failed to apply spline baseline: {e}")
                self.current_signal_data = self._initial_raw_signal_data.copy()
                self.is_spline_corrected = False
                self._update_2d_contour(reset_levels=False)
                self.update_plots()
        else:
            self.current_signal_data = self._initial_raw_signal_data.copy()
            self.is_spline_corrected = False
            self._update_2d_contour(reset_levels=False)
            self.update_plots()

        self._update_spline_button_text()

        self._data_modified = True
        self._update_window_title()

    def hold_x_slice(self):
        if not self.data_loaded: return
        x_idx = self.x_slider.value()
        color = self.plot_colors[self.held_x_slices_count % len(self.plot_colors)]
        x_pos_val = self.current_x_values[x_idx]
        name = f'{x_pos_val:.1f} {self.global_x_unit}'
        x_data, y_data = self.x_slice_curve.getData()
        curve = self.x_slice_plot_widget.plot(x_data, y_data,
                                              pen=pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine), name=name)
        self.held_x_curves.append(curve)
        self.held_x_slices_count += 1
        self._data_modified = True
        self._update_window_title()

    def clear_x_slices(self):
        for curve in self.held_x_curves:
            self.x_slice_plot_widget.removeItem(curve)
        self.held_x_curves.clear()
        self.held_x_slices_count = 0

    def hold_y_slice(self):
        if not self.data_loaded: return
        y_idx = self.y_slider.value()
        color = self.plot_colors[self.held_y_slices_count % len(self.plot_colors)]
        y_pos_val = self.current_y_values[y_idx]
        name = f'{y_pos_val:.2f} {self.global_y_unit}'
        x_data, y_data = self.y_slice_curve.getData()
        curve = self.y_slice_plot_widget.plot(x_data, y_data,
                                              pen=pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine), name=name)
        self.held_y_curves.append(curve)
        self.held_y_slices_count += 1
        self._data_modified = True
        self._update_window_title()

    def clear_y_slices(self):
        for curve in self.held_y_curves:
            self.y_slice_plot_widget.removeItem(curve)
        self.held_y_curves.clear()
        self.held_y_slices_count = 0

    def open_dispersion_correction(self):
        if not self.data_loaded or self.current_signal_data is None:
            QMessageBox.warning(self, "No Data", "Load data first.")
            return

        self.dc_window = ChirpCorrectionApp(self)
        self.dc_window.wavelengths = self.current_x_values.copy()
        self.dc_window.times = self.current_y_values.copy()
        self.dc_window.z_values = self.current_signal_data.copy()

        try:
            self.dc_window.wl_min_input.setText(f"{self.current_x_values.min():.1f}")
            self.dc_window.wl_max_input.setText(f"{self.current_x_values.max():.1f}")
            self.dc_window.t_min_input.setText(f"{self.current_y_values.min():.1f}")
            self.dc_window.t_max_input.setText(f"{self.current_y_values.max():.1f}")

            self.dc_window.crop_wl_min.setText(f"{self.current_x_values.min():.1f}")
            self.dc_window.crop_wl_max.setText(f"{self.current_x_values.max():.1f}")
            self.dc_window.crop_t_min.setText(f"{self.current_y_values.min():.1f}")
            self.dc_window.crop_t_max.setText(f"{self.current_y_values.max():.1f}")
        except Exception:
            pass

        self.dc_window.update_heatmap(self.dc_window.image_item_raw, self.dc_window.z_values)
        self.dc_window.update_start_index()
        self.dc_window.update_plot_limits()

        self.dc_window.Update_corrected_data_in_mainwindow_DC.clicked.connect(self.receive_corrected_data)

        self.dc_window.show()

    def receive_corrected_data(self):
        if self.dc_window.current_corrected_z is None:
            QMessageBox.warning(self, "Error", "Perform correction first.")
            return

        self.current_x_values = self.dc_window.current_corrected_wl.copy()
        self.current_y_values = self.dc_window.current_corrected_times.copy()
        self.current_signal_data = self.dc_window.current_corrected_z.copy()

        self._initial_raw_x_values = self.current_x_values.copy()
        self._initial_raw_y_values = self.current_y_values.copy()
        self._initial_raw_signal_data = self.current_signal_data.copy()

        self.x_slider.setRange(0, len(self.current_x_values) - 1)
        self.y_slider.setRange(0, len(self.current_y_values) - 1)

        self.is_spline_corrected = False
        self._update_spline_button_text()

        self._update_2d_contour(reset_levels=True)
        self.update_plots()

        self._data_modified = True
        self._update_window_title()

        QMessageBox.information(self, "Success", "Global data updated with Dispersion Corrected data.")

    def _update_2d_contour(self, reset_levels=True):
        if not self.data_loaded or self.current_signal_data is None: return
        sort_x = np.argsort(self.current_x_values)
        sort_y = np.argsort(self.current_y_values)
        sorted_x_vals = self.current_x_values[sort_x]
        sorted_y_vals = self.current_y_values[sort_y]
        sorted_z_data = self.current_signal_data[sort_y, :][:, sort_x]

        x_axis = self.signal_plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.signal_plot_widget.getPlotItem().getAxis('left')

        plot_x_vals = sorted_x_vals
        plot_y_vals = sorted_y_vals

        if getattr(x_axis, 'symlog_mode', False):
            plot_x_vals = symlog_transform(plot_x_vals, x_axis.linthresh)
        if getattr(y_axis, 'symlog_mode', False):
            plot_y_vals = symlog_transform(plot_y_vals, y_axis.linthresh)

        self.x_values_interp = np.linspace(plot_x_vals.min(), plot_x_vals.max(), 1000)
        self.y_values_interp = np.linspace(plot_y_vals.min(), plot_y_vals.max(), 1000)

        try:
            interp_func = RectBivariateSpline(plot_y_vals, plot_x_vals, sorted_z_data)
            self.signal_data_interp = interp_func(self.y_values_interp, self.x_values_interp)
        except Exception:
            self.signal_data_interp = sorted_z_data
            self.x_values_interp = plot_x_vals
            self.y_values_interp = plot_y_vals

        # Get levels before rendering to prevent float levels crash
        d_min, d_max = np.min(self.current_signal_data), np.max(self.current_signal_data)

        if reset_levels:
            self.min_level_input.setText(f"{d_min:.4g}")
            self.max_level_input.setText(f"{d_max:.4g}")
            plot_levels = [d_min, d_max]
        else:
            try:
                min_val = float(self.min_level_input.text())
                max_val = float(self.max_level_input.text())
                plot_levels = [min_val, max_val]
            except ValueError:
                plot_levels = [d_min, d_max]

        if plot_levels[0] == plot_levels[1]:
            plot_levels[1] += 1e-6

        self.image_item.setImage(self.signal_data_interp.T, autoLevels=False, levels=plot_levels)
        self.image_item.setRect(pg.QtCore.QRectF(
            self.x_values_interp[0], self.y_values_interp[0],
            self.x_values_interp[-1] - self.x_values_interp[0],
            self.y_values_interp[-1] - self.y_values_interp[0]
        ))

    def on_import_data_action_triggered(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Data File", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                df = pd.read_csv(file_path, header=None)
                self.current_y_values = df.iloc[1:, 0].values.astype(float)
                self.current_x_values = df.iloc[0, 1:].values.astype(float)
                self.current_signal_data = df.iloc[1:, 1:].values.astype(float)
                self.data_loaded = True

                self._initial_raw_signal_data = self.current_signal_data.copy()
                self._initial_raw_y_values = self.current_y_values.copy()
                self._initial_raw_x_values = self.current_x_values.copy()

                self.is_spline_corrected = False
                self._update_spline_button_text()

                self._update_2d_contour(reset_levels=True)

                self.x_slider.setRange(0, len(self.current_x_values) - 1)
                self.y_slider.setRange(0, len(self.current_y_values) - 1)

                self.update_plots()

                self._data_modified = True
                self._update_window_title()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to process file: {e}")

    def update_plots(self):
        if not self.data_loaded: return
        x_idx = self.x_slider.value()
        y_idx = self.y_slider.value()

        self.x_input.setText(f"{self.current_x_values[x_idx]:.2f}")
        self.y_input.setText(f"{self.current_y_values[y_idx]:.2f}")

        cx_val = self.current_x_values[x_idx]
        cy_val = self.current_y_values[y_idx]

        x_axis = self.signal_plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.signal_plot_widget.getPlotItem().getAxis('left')

        if getattr(x_axis, 'symlog_mode', False):
            cx_val = symlog_transform(cx_val, x_axis.linthresh)
        if getattr(y_axis, 'symlog_mode', False):
            cy_val = symlog_transform(cy_val, y_axis.linthresh)

        self.cursor_x_line.setPos(cx_val)
        self.cursor_y_line.setPos(cy_val)

        original_y_slice_x_data = self.current_x_values
        original_y_slice_y_data = self.current_signal_data[y_idx, :]
        original_x_slice_x_data = self.current_y_values
        original_x_slice_y_data = self.current_signal_data[:, x_idx]

        interp_x_slice_x, interp_x_slice_y = original_x_slice_x_data, original_x_slice_y_data
        interp_y_slice_x, interp_y_slice_y = self._get_interpolated_1d_data(
            original_y_slice_x_data, original_y_slice_y_data,
            self._current_interp_method, self._current_interp_multiplier
        )

        self.y_slice_curve.setData(interp_y_slice_x, interp_y_slice_y)
        self.x_slice_curve.setData(interp_x_slice_x, interp_x_slice_y)

    def _open_x_fitter_tab(self):
        xlabel = f"{self.global_y_label} [{self.global_y_unit}]"
        ylabel = f"{self.global_z_label} [{self.global_z_unit}]"
        slice_axis_name = self.global_x_label
        slice_unit = self.global_x_unit

        self._data_modified = True

        fitter_widget = exponential_fitter_wrapper(self, self.x_slice_curve, xlabel, ylabel, slice_axis_name, self.current_x_values[self.x_slider.value()], slice_unit, False)
        if fitter_widget:
            self.tab_widget.addTab(fitter_widget, "Exp Fitter")
            self.tab_widget.setCurrentWidget(fitter_widget)

    def _open_y_fitter_tab(self):
        fit_type = self.y_fit_function_selector.currentText()
        if not fit_type: fit_type = "Gaussian"

        xlabel = f"{self.global_x_label} [{self.global_x_unit}]"
        ylabel = f"{self.global_z_label} [{self.global_z_unit}]"
        slice_axis_name = self.global_y_label
        slice_unit = self.global_y_unit

        self._data_modified = True

        fitter_widget = signal_fitter_wrapper(self, self.y_slice_curve, False, fit_type, xlabel, ylabel, slice_axis_name, self.current_y_values[self.y_slider.value()], slice_unit, self.is_spline_corrected)
        if fitter_widget:
            self.tab_widget.addTab(fitter_widget, f"{fit_type} Fitter")
            self.tab_widget.setCurrentWidget(fitter_widget)

    def _launch_global_fit_tab(self):
        if not self.data_loaded: return
        self._data_modified = True
        global_fit_tab = GlobalFitApp(
            x_axis_data=self.current_x_values, y_axis_data=self.current_y_values, two_d_spectrum_data=self.current_signal_data,
            parent=self.tab_widget,
            x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
            x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
        )
        self.tab_widget.addTab(global_fit_tab, "Global Fit")
        self.tab_widget.setCurrentWidget(global_fit_tab)

    def _launch_pfid_fit_tab(self):
        if not self.data_loaded: return
        self._data_modified = True
        pfid_fit_tab = PFIDFitterApp(
            main_window=self,
            x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
            x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
        )
        self.tab_widget.addTab(pfid_fit_tab, "PFID Fit")
        self.tab_widget.setCurrentWidget(pfid_fit_tab)

    def _launch_artifact_fit_tab(self):
        if not self.data_loaded: return
        self._data_modified = True
        artifact_fit_tab = ArtifactGlobalFitApp(
            x_axis_data=self.current_x_values, y_axis_data=self.current_y_values, two_d_spectrum_data=self.current_signal_data,
            parent=self.tab_widget,
            x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
            x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
        )
        self.tab_widget.addTab(artifact_fit_tab, "Artifact Global Fit")
        self.tab_widget.setCurrentWidget(artifact_fit_tab)

    def _save_project_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Kaalen Project (*.specdatpp *.json)")
        if file_path:
            self._current_project_file = file_path
            return self._save_project()
        return False

    def _save_project(self):
        if not self._current_project_file:
            return self._save_project_as()
        try:
            def to_list(x):
                if x is None: return None
                if isinstance(x, np.ndarray): return x.tolist()
                if isinstance(x, (np.float32, np.float64, np.int32, np.int64)): return float(x)
                if isinstance(x, list): return [float(i) if isinstance(i, (np.float32, np.float64)) else i for i in x]
                return x

            state = {
                'data_loaded': self.data_loaded,
                'current_x_values': to_list(self.current_x_values) if hasattr(self, 'current_x_values') else None,
                'current_y_values': to_list(self.current_y_values) if hasattr(self, 'current_y_values') else None,
                'current_signal_data': to_list(self.current_signal_data) if hasattr(self, 'current_signal_data') else None,
                '_initial_raw_x_values': to_list(self._initial_raw_x_values) if hasattr(self, '_initial_raw_x_values') else None,
                '_initial_raw_y_values': to_list(self._initial_raw_y_values) if hasattr(self, '_initial_raw_y_values') else None,
                '_initial_raw_signal_data': to_list(self._initial_raw_signal_data) if hasattr(self, '_initial_raw_signal_data') else None,
                'is_spline_corrected': self.is_spline_corrected,
                'global_x_label': self.global_x_label,
                'global_x_unit': self.global_x_unit,
                'global_y_label': self.global_y_label,
                'global_y_unit': self.global_y_unit,
                'global_z_label': self.global_z_label,
                'global_z_unit': self.global_z_unit,
                'main_ui_state': self._get_ui_state(self.centralwidget_MW),
                'notes_text': self.notes_text_edit.toPlainText() if hasattr(self, 'notes_text_edit') else "",
                'notes_font_size': self.notes_font_spinbox.value() if hasattr(self, 'notes_font_spinbox') else 12,

                'held_x_plots': [],
                'held_y_plots': [],
                'tabs': []
            }

            for curve in self.held_x_curves:
                x_data, y_data = curve.getData()
                state['held_x_plots'].append({
                    'name': curve.opts['name'],
                    'color': curve.opts['pen'].color().name(),
                    'x': to_list(x_data), 'y': to_list(y_data)
                })

            for curve in self.held_y_curves:
                x_data, y_data = curve.getData()
                state['held_y_plots'].append({
                    'name': curve.opts['name'],
                    'color': curve.opts['pen'].color().name(),
                    'x': to_list(x_data), 'y': to_list(y_data)
                })

            for i in range(1, self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                tab_name = self.tab_widget.tabText(i)

                if isinstance(widget, GlobalFitApp):
                    tab_data = {
                        'type': 'GlobalFitApp',
                        'name': tab_name,
                        'ui': self._get_ui_state(widget)
                    }
                    if hasattr(widget, 'last_results') and widget.last_results:
                        tab_data['last_results'] = [to_list(item) for item in widget.last_results]
                    state['tabs'].append(tab_data)

                elif isinstance(widget, PFIDFitterApp):
                    state['tabs'].append({
                        'type': 'PFIDFitterApp',
                        'name': tab_name,
                        'ui': self._get_ui_state(widget)
                    })

                elif isinstance(widget, ArtifactGlobalFitApp):
                    tab_data = {
                        'type': 'ArtifactGlobalFitApp',
                        'name': tab_name,
                        'ui': self._get_ui_state(widget)
                    }
                    if hasattr(widget, 'last_results') and widget.last_results:
                        tab_data['last_results'] = [to_list(item) for item in widget.last_results]
                    state['tabs'].append(tab_data)

                elif isinstance(widget, GaussianFitterApp):
                    state['tabs'].append({
                        'type': 'GaussianFitterApp',
                        'name': tab_name,
                        'ui': self._get_ui_state(widget),
                        'init_kwargs': {
                            'x_data': to_list(widget.x_data),
                            'y_data': to_list(widget.y_data),
                            'fitting_function_type': widget.fitting_function_type,
                            'xlabel': widget.xlabel,
                            'ylabel': widget.ylabel,
                            'slice_axis_name': widget.slice_axis_name,
                            'slice_value': widget.slice_value,
                            'slice_unit': widget.slice_unit
                        },
                        'fixed_peaks': [to_list(p) for p in widget.fixed_peaks],
                        'fitted_params': to_list(widget.fitted_params) if widget.fitted_params is not None else None,
                        'fitted_errors': to_list(widget.fitted_errors) if widget.fitted_errors is not None else None
                    })

                elif isinstance(widget, ExponentialFitterApp):
                    state['tabs'].append({
                        'type': 'ExponentialFitterApp',
                        'name': tab_name,
                        'ui': self._get_ui_state(widget),
                        'init_kwargs': {
                            'x_data': to_list(widget.x_data),
                            'y_data': to_list(widget.y_data),
                            'xlabel': widget.xlabel,
                            'ylabel': widget.ylabel,
                            'slice_axis_name': widget.slice_axis_name,
                            'slice_value': widget.slice_value,
                            'slice_unit': widget.slice_unit
                        },
                        'fixed_components': [to_list(c) for c in widget.fixed_components],
                        'fitted_params': to_list(widget.fitted_params) if widget.fitted_params is not None else None,
                        'fitted_errors': to_list(widget.fitted_errors) if widget.fitted_errors is not None else None
                    })

            with open(self._current_project_file, 'w') as f:
                json.dump(state, f)

            self._data_modified = False
            self._update_window_title()
            return True

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project: {e}")
            return False

    def _load_project(self):
        if self._data_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save before loading a new project?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                if not self._save_project():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        file_path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Kaalen Project (*.specdatpp *.json)")
        if file_path:
            self._load_project_from_path(file_path)

    def _load_project_from_path(self, file_path):
        try:
            with open(file_path, 'r') as f:
                state = json.load(f)
            for i in reversed(range(self.tab_widget.count())):
                widget = self.tab_widget.widget(i)
                if widget not in (getattr(self, 'main_tab', None), getattr(self, 'notes_tab', None)):
                    self.tab_widget.removeTab(i)
                    widget.deleteLater()

            self.clear_x_slices()
            self.clear_y_slices()

            self.data_loaded = state.get('data_loaded', False)
            if self.data_loaded:
                self.current_x_values = np.array(state['current_x_values'])
                self.current_y_values = np.array(state['current_y_values'])
                self.current_signal_data = np.array(state['current_signal_data'])

                if state.get('_initial_raw_x_values') is not None:
                    self._initial_raw_x_values = np.array(state['_initial_raw_x_values'])
                else:
                    self._initial_raw_x_values = self.current_x_values.copy()

                if state.get('_initial_raw_y_values') is not None:
                    self._initial_raw_y_values = np.array(state['_initial_raw_y_values'])
                else:
                    self._initial_raw_y_values = self.current_y_values.copy()

                if state.get('_initial_raw_signal_data') is not None:
                    self._initial_raw_signal_data = np.array(state['_initial_raw_signal_data'])
                else:
                    self._initial_raw_signal_data = self.current_signal_data.copy()

                self.is_spline_corrected = state.get('is_spline_corrected', False)
                self.global_x_label = state.get('global_x_label', 'Probe wavenumber')
                self.global_x_unit = state.get('global_x_unit', 'cm\u207B\u00B9')
                self.global_y_label = state.get('global_y_label', 'Time')
                self.global_y_unit = state.get('global_y_unit', 'ps')
                self.global_z_label = state.get('global_z_label', 'ΔOD')
                self.global_z_unit = state.get('global_z_unit', 'mOD')

                if 'main_ui_state' in state:
                    self._set_ui_state(self.centralwidget_MW, state['main_ui_state'])

                if 'notes_text' in state and hasattr(self, 'notes_text_edit'):
                    # Block signals briefly so loading notes doesn't trigger the "Unsaved changes" flag
                    self.notes_text_edit.blockSignals(True)
                    self.notes_text_edit.setPlainText(state.get('notes_text', ""))
                    self.notes_text_edit.blockSignals(False)

                if 'notes_font_size' in state and hasattr(self, 'notes_font_spinbox'):
                    self.notes_font_spinbox.blockSignals(True)
                    font_size = state.get('notes_font_size', 12)
                    self.notes_font_spinbox.setValue(font_size)
                    self._change_notes_font_size(font_size)
                    self.notes_font_spinbox.blockSignals(False)

                self._update_spline_button_text()
                self._apply_axis_labels()

                self.x_slider.setRange(0, len(self.current_x_values) - 1)
                self.y_slider.setRange(0, len(self.current_y_values) - 1)

                self._update_2d_contour(reset_levels=False)
                self.update_plots()

            for p in state.get('held_x_plots', []):
                curve = self.x_slice_plot_widget.plot(np.array(p['x']), np.array(p['y']), pen=pg.mkPen(color=p['color'], width=2, style=Qt.PenStyle.DashLine), name=p['name'])
                self.held_x_curves.append(curve)
            self.held_x_slices_count = len(self.held_x_curves)

            for p in state.get('held_y_plots', []):
                curve = self.y_slice_plot_widget.plot(np.array(p['x']), np.array(p['y']), pen=pg.mkPen(color=p['color'], width=2, style=Qt.PenStyle.DashLine), name=p['name'])
                self.held_y_curves.append(curve)
            self.held_y_slices_count = len(self.held_y_curves)

            def to_arr(x):
                return np.array(x) if x is not None else None

            for tab_data in state.get('tabs', []):
                tab_type = tab_data['type']

                if tab_type == 'GlobalFitApp':
                    app_instance = GlobalFitApp(
                        x_axis_data=self.current_x_values, y_axis_data=self.current_y_values, two_d_spectrum_data=self.current_signal_data,
                        parent=self.tab_widget, x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
                        x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
                    )
                    self._set_ui_state(app_instance, tab_data['ui'])

                    if 'last_results' in tab_data:
                        res = tab_data['last_results']
                        reconstructed_tuple = (
                            to_arr(res[0]), to_arr(res[1]), res[2], res[3], to_arr(res[4]), to_arr(res[5]), to_arr(res[6]),
                            res[7], res[8], res[9], res[10], res[11], res[12], res[13], res[14]
                        )
                        app_instance.plot_results(reconstructed_tuple)
                    self.tab_widget.addTab(app_instance, tab_data['name'])

                elif tab_type == 'PFIDFitterApp':
                    app_instance = PFIDFitterApp(
                        main_window=self, x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
                        x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
                    )
                    self._set_ui_state(app_instance, tab_data['ui'])
                    self.tab_widget.addTab(app_instance, tab_data['name'])

                elif tab_type == 'ArtifactGlobalFitApp':
                    app_instance = ArtifactGlobalFitApp(
                        x_axis_data=self.current_x_values, y_axis_data=self.current_y_values, two_d_spectrum_data=self.current_signal_data,
                        parent=self.tab_widget, x_axis_label=self.global_x_label, y_axis_label=self.global_y_label, z_axis_label=self.global_z_label,
                        x_axis_unit=self.global_x_unit, y_axis_unit=self.global_y_unit, z_axis_unit=self.global_z_unit
                    )
                    self._set_ui_state(app_instance, tab_data['ui'])
                    if 'last_results' in tab_data:
                        res = tab_data['last_results']
                        if len(res) == 11:
                            reconstructed_tuple = (
                                to_arr(res[0]), to_arr(res[1]), res[2], res[3], res[4], res[5], to_arr(res[6]), to_arr(res[7]),
                                to_arr(res[8]), res[9], res[10]
                            )
                        else:
                            # Fallback if loading a project saved prior to adding t0 parameter
                            reconstructed_tuple = (
                                to_arr(res[0]), to_arr(res[1]), 0.0, res[2], res[3], res[4], to_arr(res[5]), to_arr(res[6]),
                                to_arr(res[7]), res[8], res[9]
                            )
                        app_instance.plot_results(reconstructed_tuple)
                    self.tab_widget.addTab(app_instance, tab_data['name'])

                elif tab_type == 'GaussianFitterApp':
                    kwargs = tab_data.get('init_kwargs', {})
                    app_instance = GaussianFitterApp(self, **kwargs)
                    self._set_ui_state(app_instance, tab_data['ui'])
                    app_instance.fixed_peaks = [tuple(p) for p in tab_data.get('fixed_peaks', [])]
                    app_instance.fitted_params = to_arr(tab_data.get('fitted_params'))
                    app_instance.fitted_errors = to_arr(tab_data.get('fitted_errors'))
                    if app_instance.fitted_params is not None:
                        app_instance.display_fitted_parameters()
                        app_instance.export_button.setEnabled(True)
                    app_instance.update_plot()
                    self.tab_widget.addTab(app_instance, tab_data['name'])

                elif tab_type == 'ExponentialFitterApp':
                    kwargs = tab_data.get('init_kwargs', {})
                    app_instance = ExponentialFitterApp(self, **kwargs)
                    self._set_ui_state(app_instance, tab_data['ui'])
                    app_instance.fixed_components = [list(c) for c in tab_data.get('fixed_components', [])]
                    app_instance.fitted_params = to_arr(tab_data.get('fitted_params'))
                    app_instance.fitted_errors = to_arr(tab_data.get('fitted_errors'))
                    if app_instance.fitted_params is not None:
                        app_instance.display_fitted_parameters()
                        app_instance.export_button.setEnabled(True)
                    app_instance.update_plot()
                    self.tab_widget.addTab(app_instance, tab_data['name'])

            self._data_modified = False
            self._update_window_title()

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load project: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        if self._data_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save before exiting?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                if not self._save_project():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
        QApplication.instance().quit()


if __name__ == '__main__':
    window = SignalPlotterApp()
    time.sleep(3)
    window.show()

    if len(sys.argv) > 1:
        file_to_open = sys.argv[1]
        if os.path.exists(file_to_open) and file_to_open.lower().endswith(('.specdatpp', '.json')):
            try:
                window._load_project_from_path(file_to_open)
            except Exception as e:
                QMessageBox.critical(window, "Error Opening Project", f"Failed to load project from '{file_to_open}': {e}")

    splash.finish(window)
    sys.exit(app.exec())
