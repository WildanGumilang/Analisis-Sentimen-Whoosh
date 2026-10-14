@echo off
REM Jalankan Label Studio dari virtualenv terpisah (.venv-ls).
REM Database anotasi disimpan di whoosh-absa\.labelstudio\ (drive D:), bukan di %APPDATA% (drive C:).
REM JANGAN hapus folder .labelstudio -- di situlah semua label Anda tersimpan sebelum di-export.
set LABEL_STUDIO_BASE_DATA_DIR=%~dp0..\.labelstudio
"%~dp0..\.venv-ls\Scripts\label-studio.exe" start --port 8080
