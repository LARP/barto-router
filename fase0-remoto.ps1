# Fase 0 remoto - Ejecutar en el PC PRINCIPAL.
# Envia .\fase0-diagnostico.ps1 al PC secundario por LAN (WinRM) y guarda la evidencia.
# Requisito previo: ejecutar UNA VEZ habilitar-remoting.ps1 en el secundario (como admin).
# Uso: .\fase0-remoto.ps1 -Target 192.168.100.X
#      (CONFIRMAR la IP real del secundario con 'ipconfig' en ese equipo.)

param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$CredentialFile
)

$ErrorActionPreference = 'Stop'
$ScriptLocal = Join-Path $PSScriptRoot 'fase0-diagnostico.ps1'
if (-not (Test-Path $ScriptLocal)) {
    Write-Host "No se encontro: $ScriptLocal" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] Ping a $Target ..." -ForegroundColor Cyan
if (-not (Test-Connection -ComputerName $Target -Count 2 -Quiet)) {
    Write-Host "Sin respuesta de $Target. Revisa IP/cable/WiFi." -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] WinRM en $Target ..." -ForegroundColor Cyan
try {
    Test-WSMan -ComputerName $Target | Out-Null
} catch {
    Write-Host "WinRM no responde. Ejecuta habilitar-remoting.ps1 en el secundario." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    exit 1
}

Write-Host "[3/4] Credenciales de ADMIN del secundario ..." -ForegroundColor Cyan
if ($CredentialFile) {
    if (-not (Test-Path $CredentialFile)) {
        Write-Host "No existe: $CredentialFile" -ForegroundColor Red
        exit 1
    }
    $cred = Import-Clixml -Path $CredentialFile
    Write-Host "Credenciales cargadas de archivo (cifrado DPAPI)." -ForegroundColor Green
} else {
    $cred = Get-Credential -Message "Usuario administrador de $Target"
}

Write-Host "[4/4] Ejecutando diagnostico remoto (read-only) ..." -ForegroundColor Cyan
$ts = Get-Date -Format 'yyyyMMdd-HHmm'
$outFile = Join-Path $PSScriptRoot "fase0-evidencia-$ts.txt"

try {
    $resultado = Invoke-Command -ComputerName $Target -Credential $cred `
        -FilePath $ScriptLocal -ErrorAction Stop
    $resultado | Out-File -FilePath $outFile -Encoding utf8
    $resultado | Out-String | Write-Host
    Write-Host ""
    Write-Host "Evidencia guardada en: $outFile" -ForegroundColor Green
    Write-Host "Credencial conservada en $CredentialFile (cifrada DPAPI, solo tu usuario la puede abrir)." -ForegroundColor DarkGray
} catch {
    Write-Host "Fallo la ejecucion remota:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host "Si dice acceso denegado: verifica usuario/clave y LocalAccountTokenFilterPolicy en el secundario." -ForegroundColor Yellow
    exit 1
}
