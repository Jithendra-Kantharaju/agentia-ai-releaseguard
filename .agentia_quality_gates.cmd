@echo off
rem ReleaseGuard as an Agentia local quality gate. Pick a scenario with: agentia cicd work test -e RELEASEGUARD_SCENARIO=fail
if "%RELEASEGUARD_SCENARIO%"=="" set RELEASEGUARD_SCENARIO=pass
set RG_FLAGS=--no-llm
if "%RELEASEGUARD_LLM%"=="1" set RG_FLAGS=
python -m releaseguard gate --scenario %RELEASEGUARD_SCENARIO% %RG_FLAGS%
exit /b %ERRORLEVEL%