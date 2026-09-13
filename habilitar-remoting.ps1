# Habilitar remoting - Ejecutar UNA VEZ, LOCAL, en el PC SECUNDARIO como Administrador.
# Permite que el PC principal ejecute el diagnostico de Fase 0 por LAN.

#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

# Chequeo explicito (funciona tambien via iex/descarga)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "REABRE PowerShell COMO ADMINISTRADOR y repite el comando." -ForegroundColor Red
    return
}

Write-Host "[1/3] Habilitando PowerShell Remoting (WinRM)..." -ForegroundColor Cyan
Enable-PSRemoting -Force -SkipNetworkProfileCheck

Write-Host "[2/3] Token admin completo para cuentas locales (red workgroup)..." -ForegroundColor Cyan
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' `
    -Name LocalAccountTokenFilterPolicy -Value 1 -Type DWord -Force

Write-Host "[3/3] Regla de firewall WinRM (solo LAN 192.168.100.0/24)..." -ForegroundColor Cyan
$rule = Get-NetFirewallRule -DisplayName 'Fase0-WinRM-LAN' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -DisplayName 'Fase0-WinRM-LAN' -Direction Inbound `
        -Protocol TCP -LocalPort 5985 -RemoteAddress 192.168.100.0/24 -Action Allow | Out-Null
    Write-Host "Regla creada." -ForegroundColor Green
} else {
    Write-Host "Regla ya existia." -ForegroundColor Green
}

Write-Host ""
Write-Host "Listo. Desde el PC principal:" -ForegroundColor Green
Write-Host '  .\fase0-remoto.ps1 -Target 192.168.100.X   # IP REAL del secundario (ver con ipconfig)'
Test-WSMan -ComputerName localhost | Select-Object -ExpandProperty ProductVersion
