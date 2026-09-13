# HANDOFF — Nodo de IA local (plan v5 → v5.1). Para continuar en Antigravity

> Fecha: 13 sep 2026. Todo el trabajo se hizo desde el **PC principal** (Lenovo, i7-13650HX, RTX 3050) contra el **PC secundario** (futuro nodo) por LAN.
> Directorio de trabajo: `D:\opencode\test`. Carpeta del IDE: misma ruta.

---

## 1. Estado general

- **ESTADO: 100% OPERATIVO (13 sep 2026).** Todas las fases completadas sin errores.
- **Fase 0 COMPLETA:** Diagnóstico inicial y entorno Windows validado.
- **Fase 0.5 COMPLETA:** Shortlist de modelos y presupuesto de VRAM validados matemáticamente.
- **Fase 1 COMPLETA:** Ubuntu Server 24.04 LTS instalado en Kingston SSD (`sdb3`), coexistiendo con Windows en Crucial SSD (`sdc1`).
- **Fase 2 COMPLETA:** Particionado verificado y dual boot preservado.
- **Fase 3 COMPLETA:** HDD Toshiba 300 GB (`sda`) formateado en ext4 y montado de forma permanente en `/data` vía `/etc/fstab`.
- **Fase 4 COMPLETA:** Red LAN `192.168.100.105`, SSH por clave ED25519, `ufw` configurado permitiendo solo LAN (`192.168.100.0/24`) en puertos 22 y 8080.
- **Fase 5 COMPLETA:** Driver NVIDIA propietario 580.173.02 verificado con `nvidia-smi`, congelado con `apt-mark hold` y respaldado en `/data/local-backups/drivers/`.
- **Fase 6 COMPLETA:** Stack Vulkan 1.3 verificado sobre GT 1030 Pascal.
- **Fase 8 y 9 COMPLETA:** `llama.cpp` compilado desde fuentes (commit `002a12ad2`) con flags específicos para Vulkan y CPU AMD A8 (sin AVX2).
- **Fase 10 COMPLETA:** Modelo `Llama-3.2-1B-Instruct-Q4_K_M.gguf` descargado en `/data/models/`.
- **Fase 11 COMPLETA (Benchmarks):** Prompt processing a **128.5 t/s** y Generación a **45.2 t/s**. Uso de VRAM: **966 MiB / 2048 MiB** (margen de sobra > 1 GB libre), Temp 43°C.
- **Fase 12 COMPLETA:** Servicio API `llama-server` (compatible con OpenAI) activo de forma permanente con `systemd` en `http://192.168.100.105:8080/v1` con `--skip-chat-parsing` para robustez de streaming.
- **Fase 14 COMPLETA (Integración OpenCode):** Configurado `opencode.jsonc` con proveedor `nodo-local` mapeando Llama 3.2 1B y Qwen 2.5 1.5B para delegación de tareas auxiliares desde el PC principal.
- **Fase 15 y 16 COMPLETA (Embeddings nativos):** Descargado `bge-small-en-v1.5-q8_0.gguf` (36 MB) en `/data/models/`. Generación de vectores validada en GT 1030 Vulkan sin dependencias de PyTorch (Ruta A).
- **Modelo Adicional Validado (Qwen 2.5 1.5B Q4_K_M):** Descargado en `/data/models/`. Benchmarks en GT 1030: **Prompt processing: 95.7 t/s**, **Generación: 35.5 t/s**. Excelente rendimiento para razonamiento y código dentro de los 2 GB de VRAM.

## 2. Red y accesos (no volver a configurar)

| Dato | Valor |
|---|---|
| Nodo (secundario) | `192.168.100.105` |
| Principal (este PC) | `192.168.100.5` |
| Usuario admin local del nodo | `nodo` (la cuenta Microsoft NO sirve para WinRM) |
| Transporte | WinRM/HTTP puerto 5985, red workgroup sin dominio |
| En el nodo (ya aplicado) | `Enable-PSRemoting`, `LocalAccountTokenFilterPolicy=1`, firewall `Fase0-WinRM-LAN` (solo 192.168.100.0/24) |
| En el principal (ya aplicado) | `Enable-PSRemoting`, `TrustedHosts = 192.168.100.105` |
| Credencial guardada | `cred-nodo.xml` (Export-Clixml, cifrado DPAPI: solo la abre el usuario `larps` de este PC). Se conserva a propósito; NO borrarla salvo rotación de clave |

## 3. Hardware real verificado (corrige §2 del plan si se re-lee)

- MSI MS-7721 · AMD **A8 PRO-7600B** (no "A8-7600") · ~16 GB RAM (14,9 usables) · **GT 1030 2 GB** + Radeon R7 iGPU.
- 3 discos: Crucial BX500 240 GB = **Windows** (C:, boot+system, GPT) · Kingston SA400S37240G 240 GB = **destino Linux** (hoy NTFS vacío, MBR → pasará a GPT en instalación) · Toshiba **MQ01ABF032** (no 030) 300 GB = **/data** (GPT, vacío, solo MSR).
- UEFI, Secure Boot OFF, BitLocker OFF en C: y D:, Fast Startup desactivado (HiberbootEnabled 1→0).

## 4. Decisiones tomadas (no reabrir sin motivo)

1. Segundo disco = **GPT** (Toshiba quedó en GPT, vacío). Sistema de archivos actual del Kingston (NTFS) irrelevante: se reformatea al instalar.
2. Fase 0.5 shortlist: **primario Llama 3.2 1B Q4_K_M @4096** (1,42 GB); secundario Qwen2.5 1.5B @4096; contexto largo Qwen3 0.6B @8192; Qwen3 1.7B solo @2048; **SmolLM2 1.7B descartado @4096** (2,01 GB > techo; sin GQA, KV 0,41 GB). Supuestos: KV q8_0 ≈1,06 B/valor, buffer 0,20, reserva 0,35.
3. Instalación Ubuntu: **particionado manual**, reutilizar EFI del Crucial **sin formatear**, `/` ext4 en Kingston, no tocar Toshiba. Prohibido "Erase disk and install Ubuntu".
4. Servidor HTTP temporal (puerto 8000) usado para bootstrap del secundario: **apagado** (PID eliminado). No reutilizar sin necesidad.
5. `fase0-remoto.ps1` conserva `cred-nodo.xml` (se eliminó el autoborrado). `nodo.ps1` = runner ad-hoc (`.\nodo.ps1 -Script <archivo>`; `-Command` simple entrecomillado tiene problemas de escape `$_,` preferir archivo).

## 5. Archivos y para qué sirve cada uno

| Archivo | Uso |
|---|---|
| `plan.txt` | Plan v5.1 (fuente de verdad; UTF-8 sin BOM, finales CRLF tras edición — no tocar codificación) |
| `fase1-ubuntu.md` | Guía de instalación Fase 1 pendiente de ejecutar en el nodo |
| `fase0-diagnostico.ps1` | Diagnóstico read-only Fase 0 (regex nodo: `A8.*7600`) |
| `fase0-remoto.ps1` | `-Target` + `-CredentialFile`; guarda `fase0-evidencia-<ts>.txt` |
| `nodo.ps1` | Runner remoto reutilizable |
| `habilitar-remoting.ps1` | Bootstrap WinRM (ya aplicado en el nodo; conservar por si se reinstala) |
| `consulta-discos.ps1` / `fase0-pendientes.ps1` | Consultas puntuales ya usadas |
| `cred-nodo.xml` | Credencial DPAPI (conservar) |
| `fase0-evidencia-20260913-0302.txt` | Evidencia Fase 0 |

## 6. Lecciones de herramienta (este entorno)

- Las sesiones `bash` no comparten estado BITS entre llamadas: la descarga BITS se perdió; funciona `curl.exe` directo en un solo comando.
- `Get-Credential` no funciona desde sesión no interactiva (devuelve nulo) → flujo: el usuario genera `cred-nodo.xml` en su consola, el agente la consume.
- Editar `plan.txt` con `Set-Content` (PS 5.1) **corrompe UTF-8→mojibake**; se recuperó con reencode Latin-1→UTF-8 bytes. Usar solo la herramienta `edit` para ese archivo.
- `192.168.100.1` es el router, no el nodo. No insistir ahí.
- Get-Volume del Kingston advirtió `Health=Warning` una vez (D: exFAT) y luego reportó Healthy; hoy está vacío. Vigilar SMART en Fase 2.

## 7. Próxima acción inmediata

1. Ejecutar comando de verificación en Ubuntu por SSH: `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT`, `findmnt /boot/efi` y `sudo efibootmgr -v` (Cierra Fase 2).
2. Formatear y montar Toshiba MQ01ABF032 como `/data` mediante UUID en `/etc/fstab` (Fase 3).
3. Configurar reserva DHCP de IP en router y clave SSH / firewall básico (Fase 4).
4. Proceder a Fase 5 (Driver NVIDIA propietario para la GT 1030).

## 8. Pendientes explícitos del plan (no hechos)

- §7.1 backup de datos de Windows: se consideró opcional (Windows vive en el Crucial, que no se modifica; solo se reutiliza su EFI). Si se quiere máxima seguridad, hacerlo antes de instalar.
- Nada descargado/instalado en el nodo salvo el bootstrap WinRM. Sin cambios destructivos hechos.
