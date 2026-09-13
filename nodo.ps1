# Runner reutilizable del nodo. Ejecutar en el PC PRINCIPAL.
# Usa credenciales guardadas (cred-nodo.xml) para lanzar consultas por LAN.
# Uso:  .\nodo.ps1 -Command "Get-Disk"          # comando ad-hoc en el nodo
#       .\nodo.ps1 -Script .\fase0-diagnostico.ps1
#       .\nodo.ps1 -Command "Get-Disk" -Target 192.168.100.105

param(
    [string]$Target = '192.168.100.105',
    [string]$CredentialFile = (Join-Path $PSScriptRoot 'cred-nodo.xml'),
    [string]$Command,
    [string]$Script
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $CredentialFile)) {
    Write-Host "No existe $CredentialFile. Genera uno con:" -ForegroundColor Red
    Write-Host "  Get-Credential | Export-Clixml .\cred-nodo.xml" -ForegroundColor Yellow
    exit 1
}
$cred = Import-Clixml -Path $CredentialFile

if ($Script) {
    if (-not (Test-Path $Script)) { Write-Host "No existe: $Script" -ForegroundColor Red; exit 1 }
    Invoke-Command -ComputerName $Target -Credential $cred -FilePath $Script
}
elseif ($Command) {
    $sb = [scriptblock]::Create($Command)
    Invoke-Command -ComputerName $Target -Credential $cred -ScriptBlock $sb
}
else {
    Write-Host "Indica -Command o -Script." -ForegroundColor Yellow
}
