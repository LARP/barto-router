# Fase 0 - Diagnóstico READ-ONLY. No modifica nada.
# Ejecutar en el PC secundario (futuro nodo): AMD A8 PRO-7600B / GT 1030.
# Uso: powershell -ExecutionPolicy Bypass -File .\fase0-diagnostico.ps1

$ErrorActionPreference = 'Continue'

function Section($t) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host $t -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

Section "0. Identificacion del equipo (confirmar que es el nodo)"
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "AVISO: ejecutar como Administrador para BitLocker y Secure Boot." -ForegroundColor Yellow
}
try {
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor
    $gpu = Get-CimInstance Win32_VideoController
    Write-Host "Equipo : $($cs.Manufacturer) $($cs.Model)"
    Write-Host "CPU    : $($cpu.Name)"
    Write-Host "Nucleos: $($cpu.NumberOfCores)"
    Write-Host ("RAM    : {0:N1} GB" -f ($cs.TotalPhysicalMemory / 1GB))
    foreach ($g in $gpu) {
        Write-Host ("GPU    : {0} | VRAM reportada {1:N2} GB" -f $g.Name, ($g.AdapterRAM / 1GB))
    }
    if ($cpu.Name -match 'A8.*7600') {
        Write-Host "Coincide con nodo (A8 PRO-7600B): True" -ForegroundColor Green
    } else {
        Write-Host "Coincide con nodo (A8 PRO-7600B): False - ATENCION, no es el PC secundario" -ForegroundColor Yellow
    }
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "1. Modo BIOS / UEFI (plan 7.3)"
try {
    Write-Host "FirmwareType (env): $env:firmware_type"
    try {
        $sb = Confirm-SecureBootUEFI
        Write-Host "Secure Boot      : $sb"
    } catch {
        Write-Host "Secure Boot      : no disponible (probable BIOS legacy o sin privilegios)" -ForegroundColor Yellow
    }
    Write-Host "  -> Alternativa: ejecutar 'msinfo32' y leer 'BIOS Mode'"
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "2. Fast Startup / Hiberboot (plan 7.4)"
try {
    $hb = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -ErrorAction Stop
    Write-Host "HiberbootEnabled = $($hb.HiberbootEnabled)  (1 = Fast Startup ACTIVADO, debe ser 0)"
} catch { Write-Host "No se pudo leer HiberbootEnabled: $_" -ForegroundColor Yellow }

Section "3. BitLocker / Device Encryption (plan 7.2)"
try {
    $bl = Get-BitLockerVolume -ErrorAction Stop
    foreach ($v in $bl) {
        Write-Host "$($v.MountPoint)  Protection=$($v.ProtectionStatus)  Encryption=$($v.VolumeStatus)"
    }
} catch {
    Write-Host "Get-BitLockerVolume no disponible o requiere admin; intentando manage-bde:"
    manage-bde -status
}

Section "4. Discos fisicos (plan 7.5)"
try {
    Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType,
        @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, SerialNumber |
        Format-Table -AutoSize
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "5. Discos y particiones (plan 7.5)"
try {
    Get-Disk | Select-Object Number, FriendlyName, PartitionStyle, BusType,
        @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, IsBoot, IsSystem |
        Format-Table -AutoSize
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

try {
    Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Type,
        @{n='SizeGB';e={[math]::Round($_.Size/1GB,2)}} |
        Format-Table -AutoSize
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "6. Volumenes (EFI / Recovery / OEM)"
try {
    Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem,
        @{n='SizeGB';e={[math]::Round($_.Size/1GB,2)}}, HealthStatus |
        Format-Table -AutoSize
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "7. IDs por volumen (para /etc/fstab por UUID mas adelante)"
try {
    Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID, VolumeName, VolumeSerialNumber, FileSystem |
        Format-Table -AutoSize
} catch { Write-Host "ERROR: $_" -ForegroundColor Red }

Section "FIN - Todo read-only. Revisar y archivar como evidencia de Fase 0."
