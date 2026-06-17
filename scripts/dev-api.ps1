Set-Location "$PSScriptRoot\..\apps\api"
py -m app.seed
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
