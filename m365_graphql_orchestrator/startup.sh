#!/bin/bash
# Azure App Service startup script
#
# Dependencies are installed by Oryx during deployment (SCM_DO_BUILD_DURING_DEPLOYMENT=true).
# If deps are missing at runtime, uncomment the next line:
# pip install --no-cache-dir -r requirements.txt

python -m src.main
