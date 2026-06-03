# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# IMPORT collect_all to handle the aggressive gathering of Qt and pyqtgraph plugins
from PyInstaller.utils.hooks import collect_all

# Trigger the "Nuclear Option" collection for both libraries
pg_datas, pg_binaries, pg_hiddenimports = collect_all('pyqtgraph')
qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')

a = Analysis(
    ['kaalen_v3.py'], 
    pathex=['.'], 
    # Inject the collected C++ DLLs and binaries here
    binaries=[] + pg_binaries + qt_binaries,
    
    # Append the collected data files to your UI files and icons
    datas=[
        ('pfid_tab.ui', '.'),
        ('global_fit.ui', '.'),
        ('exponential_fit_UI.ui', '.'),
        ('peak_fit_UI.ui', '.'),
        ('dispersion_correction.ui', '.'),
        ('mainwindow.ui', '.'),
        ('coherent_artifact_included_GF.ui', '.'),
        ('icon.ico', '.'), 
        ('icon.png', '.'),
    ] + pg_datas + qt_datas,
    
    # Append the collected submodules to your specific hidden imports
    hiddenimports=[
        # --- Fix for SVG exports ---
        'PyQt6.QtSvg',
        'pyqtgraph.exporters',
        
        # --- Background dependencies (Keep these to prevent crashes) ---
        'pkg_resources',
        'jaraco',
        'jaraco.text',
        'jaraco.context',
        'jaraco.functools',
        'jaraco.classes',
        'platformdirs',                      
        'packaging',
        'appdirs',
        'importlib_metadata',
        'more_itertools',
        
        # --- Your original specific app imports ---
        'matplotlib.backends.backend_qtagg',
        'scipy.special.orthogonal', 
        'numpy.core._dtype_ctypes',
        'pandas._libs.tslibs.timedeltas',
        'PyQt6.QtNetwork',                   
        'PyQt6.QtPrintSupport',              
        'PyQt6.QtCore',                      
        'PyQt6.QtGui',                       
        'scipy._lib.array_api_compat.numpy',
        'scipy._lib.array_api_compat.numpy.fft',
        'scipy.linalg.cython_blas', 
        'scipy.linalg.cython_lapack',
        'scipy.optimize.minpack',
    ] + pg_hiddenimports + qt_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          [],                      
          exclude_binaries=True,   
          name='Kaalen_v3',
          debug=False,
          strip=False,
          upx=True,
          console=False, 
          disable_window_shadow=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='icon.ico')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='Kaalen_v3')

# macOS specific bundle - this is ignored by Windows and Linux builds
app = BUNDLE(coll,
             name='Kaalen_v3.app',
             icon='icon.ico',
             bundle_identifier=None)
