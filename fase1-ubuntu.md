# FASE 1 — Instalación de Ubuntu Server 24.04 LTS en el nodo

> Requiere presencia física en el PC secundario y un USB (≥ 4 GB).
> Objetivo: instalar Ubuntu en el **Kingston SA400S37240G (240 GB)** reutilizando la EFI del **Crucial BX500** (Windows), sin tocar Windows ni el Toshiba.

---

## Paso 1 — Descargar la ISO (en el PC principal)

Imagen vigente: **Ubuntu Server 24.04.5 LTS**

```powershell
cd $env:USERPROFILE\Downloads
$url = 'https://releases.ubuntu.com/24.04/ubuntu-24.04.5-live-server-amd64.iso'
Invoke-WebRequest -Uri $url -OutFile 'ubuntu-24.04.5-live-server-amd64.iso'
```

Verificar integridad (debe coincidir exactamente):

```powershell
Get-FileHash .\ubuntu-24.04.5-live-server-amd64.iso -Algorithm SHA256
# Esperado: 97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8
```

Si el hash no coincide, **no usar la ISO**: volver a descargar.

---

## Paso 2 — Crear el USB de arranque

Recomendado: **Rufus** (https://rufus.ie).

- Dispositivo: el USB.
- Selección de arranque: la ISO descargada.
- Esquema de partición: **GPT**.
- Sistema destino: **UEFI (no CSM)**.
- Al preguntar el modo: **Escribir en modo imagen DD** (modo ISO puede fallar en Server).

Alternativa: balenaEtcher o Ventoy.

---

## Paso 3 — Arrancar el nodo desde el USB

1. Con el USB puesto, encender el nodo.
2. Tecla de menú de arranque de MSI: **F11** (o `Del` → BIOS → Boot).
3. Elegir la entrada **UEFI: <marca del USB>** (no la variante "legacy").

---

## Paso 4 — Instalador (guía de pantallas)

1. Idioma / teclado.
2. Red: dejar **DHCP** por ahora (la IP estable se reserva en el router en Fase 4).
3. Proxy / mirror: por defecto.
4. Tipo de instalación: **Ubuntu Server** (no minimizada, no "Ubuntu Server (minimized)").
5. Red de almacenamiento: dejar por defecto (LVM opcional; para el plan se prefiere particionado **manual**).

---

## Paso 5 — Particionado (CRÍTICO)

Entrar en **Storage → Custom storage layout**.

### Regla de identificación

Distinguir los discos **por modelo/tamaño**, nunca por orden:

| Disco | Modelo | Tamaño | Acción |
| --- | --- | --- | --- |
| Crucial BX500 | `CT240BX500SSD1` | 240 GB | **Windows — NO TOCAR** (salvo usar su EFI) |
| Kingston | `SA400S37240G` | 240 GB | **Destino de Ubuntu** |
| Toshiba | `MQ01ABF032` | 300 GB | **NO TOCAR** (se monta en Fase 3) |

### 5.1 Reutilizar la EFI de Windows (sin formatear)

- En el **Crucial**, localizar la partición EFI (~100 MB, FAT32, tipo EFI System).
- Seleccionarla → **Use as Boot Device** / montar en `/boot/efi`.
- **NO marcar "format"** ni borrarla. Aquí coexistirán los arranques de Windows y Ubuntu.

### 5.2 Crear la raíz de Ubuntu en el Kingston

- En el **Kingston**: si pide, crear **nueva tabla GPT** (hoy es MBR).
- Crear una partición **ext4** que ocupe todo el disco → montar en `/`.
- Swap: se crea el **swapfile** por defecto (no hace falta partición swap).

### 5.3 No tocar

- No añadir ni modificar nada en Crucial (más allá de la EFI) ni en Toshiba.

Resumen del layout resultante:

```text
Crucial BX500 (Windows)          Kingston SA400S37240G
├── EFI System  <-- compartida   ├── /  (ext4, todo el disco)
├── MSR                          └── (swapfile dentro de /)
├── C: Windows
└── Recovery
```

---

## Paso 6 — Usuario, hostname y SSH

- Hostname: `nodo`.
- Usuario administrador: el que quieras (evita cuentas Microsoft; es Linux, es local).
- **Install OpenSSH server: SÍ** (necesario para Fase 4).

---

## Paso 7 — Bootloader y fin de instalación

- Subiquity instalará GRUB y detectará Windows vía os-prober.
- Revisar que aparezcan **ambos** antes de reiniciar: "Ubuntu" y "Windows Boot Manager".
- Reiniciar y **retirar el USB**.

---

## Verificación Fase 1 (criterios de éxito)

En el nodo, tras el primer arranque:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
sudo blkid
findmnt /boot/efi
```

Debe verse:

- `/` montado desde el **Kingston**;
- `/boot/efi` montado (la EFI del Crucial);
- Windows intacto en el **Crucial**;
- **Toshiba sin montar** (se hará en Fase 3).

Y en el menú de arranque debe seguir apareciendo Windows.

> Si el menú no muestra Windows: no continuar. Revisar os-prober / orden de arranque UEFI antes de seguir.
