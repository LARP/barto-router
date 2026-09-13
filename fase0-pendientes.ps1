'=== 1. Desactivar Fast Startup (HiberbootEnabled = 0) ==='
$key = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power'
$antes = (Get-ItemProperty $key -Name HiberbootEnabled -ErrorAction SilentlyContinue).HiberbootEnabled
Set-ItemProperty $key -Name HiberbootEnabled -Value 0 -Type DWord -Force
$despues = (Get-ItemProperty $key -Name HiberbootEnabled).HiberbootEnabled
"Antes : $antes"
"Despues: $despues   (0 = Fast Startup desactivado)"

'=== 2. Contenido actual de D: (Kingston, a vaciar) ==='
$vol = Get-Volume -DriveLetter D
"Etiqueta: $($vol.FileSystemLabel)  FS: $($vol.FileSystem)"
"Tamano: {0:N1} GB   Libre: {1:N1} GB   Usado: {2:N1} GB" -f `
    ($vol.Size/1GB), ($vol.SizeRemaining/1GB), (($vol.Size - $vol.SizeRemaining)/1GB)

Get-ChildItem -LiteralPath 'D:\' -Force -ErrorAction SilentlyContinue |
    Select-Object Mode, LastWriteTime, @{n='SizeMB';e={ if ($_.PSIsContainer) { '<dir>' } else { [math]::Round($_.Length/1MB,2) } }}, Name |
    Format-Table -AutoSize
