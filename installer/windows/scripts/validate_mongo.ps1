# Validate MongoDB connection before install continues
param(
    [Parameter(Mandatory = $true)][string]$MongoUri,
    [Parameter(Mandatory = $true)][string]$DbName,
    [Parameter(Mandatory = $true)][string]$PythonExe
)

$ErrorActionPreference = "Stop"
$script = @"
from vaybooks.bms.infrastructure.config.settings import validate_mongo_connection
ok, msg = validate_mongo_connection('$MongoUri', '$DbName')
print(msg)
raise SystemExit(0 if ok else 1)
"@
& $PythonExe -c $script
exit $LASTEXITCODE
