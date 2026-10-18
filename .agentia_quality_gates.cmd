@echo off
rem Agentia quality gate: explicit mode required, never default to a passing mock.
setlocal
if /I "%RELEASEGUARD_MODE%"=="mock" goto mock
if /I "%RELEASEGUARD_MODE%"=="real" goto real
echo REVIEW_REQUIRED: set RELEASEGUARD_MODE=real or RELEASEGUARD_MODE=mock 1>&2
exit /b 2
:mock
if "%RELEASEGUARD_SCENARIO%"=="" (
  echo REVIEW_REQUIRED: specify RELEASEGUARD_SCENARIO 1>&2
  exit /b 2
)
set "RG_ARGS=--mode mock --scenario %RELEASEGUARD_SCENARIO%"
goto run
:real
if "%RELEASEGUARD_WORK_ID%"=="" (
  echo REVIEW_REQUIRED: specify RELEASEGUARD_WORK_ID 1>&2
  exit /b 2
)
set "RG_ARGS=--mode real --work-id %RELEASEGUARD_WORK_ID%"
if not "%RELEASEGUARD_JOB_ID%"=="" set "RG_ARGS=%RG_ARGS% --job-id %RELEASEGUARD_JOB_ID%"
if not "%RELEASEGUARD_PREFLIGHT%"=="" set "RG_ARGS=%RG_ARGS% --preflight %RELEASEGUARD_PREFLIGHT%"
:run
set "RG_FLAGS=--no-llm"
if "%RELEASEGUARD_LLM%"=="1" set "RG_FLAGS="
python -m releaseguard gate %RG_ARGS% %RG_FLAGS%
exit /b %ERRORLEVEL%
