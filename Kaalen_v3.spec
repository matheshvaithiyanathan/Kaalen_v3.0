# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 1. Define the primary executable analysis
a = Analysis(
    ['App_PP.py'],
    pathex=['.'], 
    binaries=[],
    datas=[
        # Explicitly include the Python resource file and the external icon file
        ('resources_rc.py', '.'),
        ('icon.ico', '.'), 
    ],
    # CRITICAL: These hidden imports are necessary for PyQt5, Matplotlib, SciPy, and Pandas GUIs
    hiddenimports=[
        'matplotlib.backends.backend_qt5agg',
        'scipy.special.orthogonal', 
        'numpy.core._dtype_ctypes',
        
        # Additional essential scientific/PyQt imports
        'pandas._libs.tslibs.timedeltas',
        'PyQt5.QtNetwork',
        'PyQt5.QtPrintSupport',
        
        # Ensure Qt plugins and styling hooks are collected
        'PyQt5.Qt.plugins.platforms',
        'PyQt5.Qt.plugins.styles',
        
        # Often needed for PyQt5/PyQtGraph complex module linking
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        
        # --- NEW SCI-PY FIXES ---
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

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Kaalen_App',
          debug=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False, 
          disable_window_shadow=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          # --- FIX: Embed the icon in the executable's metadata for the OS shell ---
          icon='icon.ico')

# 4. Collection step (Crucial for multi-file build)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='Kaalen_App')
