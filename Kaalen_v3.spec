# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
from PyInstaller.utils.hooks import collect_submodules
a = Analysis(
    ['kaalen_v3.py'], # <-- UPDATED: Points to your actual Python script
    pathex=['.'], 
    binaries=[],
    datas=[
        ('pfid_tab.ui', '.'),
        ('global_fit.ui', '.'),
        ('exponential_fit_UI.ui', '.'),
        ('peak_fit_UI.ui', '.'),
        ('dispersion_correction.ui', '.'),
        ('mainwindow.ui', '.'),
        ('icon.ico', '.'), 
        ('icon.png', '.'),
    ],
    hiddenimports=[
        # --- The new band-aids for the crash ---
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
        
        # --- Your original app imports (KEEP THESE!) ---
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
    ],
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
          [],                      # Removed a.binaries, a.zipfiles, a.datas from EXE
          exclude_binaries=True,   # Added to ensure COLLECT handles the files, creating a directory
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
