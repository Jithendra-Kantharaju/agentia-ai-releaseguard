@echo off
python -m releaseguard gate --scenario fail --no-llm
exit /b %ERRORLEVEL%