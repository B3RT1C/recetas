# Despliegue en Windows (mini PC)

Destino: `C:\Users\b3-ml\recetas-web\recetas-web-v2`. La web v1 (`C:\Users\b3-ml\recetas-web`) se queda tal cual como respaldo
y su carpeta `videos\` se reutiliza (no se copian vídeos).

Todos los comandos en **PowerShell como administrador** (la tarea programada corre como SYSTEM: hace falta UAC).

## 1. Copia de seguridad y código

```powershell
$Old = "C:\Users\b3-ml\recetas-web"
$New = "$Old\recetas-web-v2"
Compress-Archive -Path "$Old\*" -DestinationPath "C:\Users\b3-ml\recetas-web-backup-$(Get-Date -f yyyyMMdd).zip" `
  -CompressionLevel Fastest   # opcional si la carpeta de vídeos es muy grande
# Copia aquí la carpeta recetas-web-v2 (USB, red o zip). No copies data\recetas.db, media\ ni videos\ desde el box.
```

## Actualizar desde la Fase 1 (`b721dc9`) a la v2.1.0

Las migraciones son automáticas y solo añaden (nunca borran): al arrancar, si la BD no está al día se guarda antes una
copia `data\recetas.db.bak-v<N>` junto a ella. El esquema pasa de v0 a **v2** (lista de la compra, despensa,
planificador, usuarios/sesiones, registro de trabajos, `price_history`).

```powershell
schtasks /End /TN RecetasWeb                         # o Stop-ScheduledTask
cd C:\Users\b3-ml\recetas-web\recetas-web-v2
Copy-Item data\recetas.db "data\recetas.db.manual-$(Get-Date -f yyyyMMdd-HHmm)"   # copia propia, por si acaso
git fetch <origen>; git checkout v2.1.0              # o copia la carpeta / aplica el bundle
.\.venv\Scripts\python -m pip install -r requirements.txt   # sin dependencias nuevas obligatorias
winget install Gyan.FFmpeg                           # portadas de vídeo (opcional pero recomendado)
.\.venv\Scripts\python -m pytest -q                  # opcional: debe salir todo en verde
.\.venv\Scripts\python -m app.cli create-admin       # crea el administrador web (o usa el código, ver abajo)
schtasks /Run /TN RecetasWeb
```

- **ffmpeg**: tras `winget install Gyan.FFmpeg` abre una consola nueva (PATH). Como la tarea corre como SYSTEM, es
  más fiable fijar la ruta completa en `config.env`:
  `RECETAS_FFMPEG=C:\Users\b3-ml\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe` (compruébala con `where.exe ffmpeg`).
  Sin ffmpeg todo funciona; las recetas sin foto muestran un marcador neutro.
- **Administrador**: desde la v2.1.0 la web exige iniciar sesión. Si no creas el usuario con `create-admin`, el
  servidor escribe un **código de configuración** en su registro y en `C:\ProgramData\recetas-web\secret\setup-code.txt`;
  la pantalla de bienvenida lo pide al crear la cuenta desde otro equipo (desde `localhost` no hace falta).
  ¿Contraseña olvidada? `python -m app.cli create-admin --replace`.
- **Volver atrás**: para la tarea, restaura `recetas.db.bak-v0` como `recetas.db` y vuelve a `b721dc9`.

## 2. Python y dependencias

```powershell
cd $New
py -3.12 -m venv .venv          # Python 3.11+ (probado con 3.13)
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 3. Variables y prueba manual

```powershell
New-Item -ItemType Directory -Force C:\ProgramData\recetas-web\secret | Out-Null
$env:RECETAS_VIDEOS_DIR = "$Old\videos"
$env:RECETAS_SECRET_DIR = "C:\ProgramData\recetas-web\secret"
.\run.bat --port 8088
```

Abre `http://localhost:8088` y comprueba que una receta con vídeo lo reproduce. Para la prueba manual para la tarea
antigua primero (paso 4, primera línea) si ocupa el puerto. `Ctrl+C` para salir.

**Por qué `RECETAS_SECRET_DIR` explícito:** por defecto la clave Fernet va a `~\.recetas-web\secret.key`; con SYSTEM
`~` es `C:\Windows\System32\config\systemprofile`, que es incómodo de respaldar y distinto del de tu usuario (las claves
de IA guardadas con una cuenta no se podrían leer con la otra). Restringe la carpeta:

```powershell
icacls C:\ProgramData\recetas-web\secret /inheritance:r /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"
```

**Haz copia de `secret.key`** (fuera del PC). Sin ella las claves de IA y de APIs guardadas no se pueden descifrar
(se vuelven a introducir; las recetas no se pierden). La sesión de Instagram (`*.session`) también vive ahí.

## 4. Sustituir la tarea programada `RecetasWeb`

```powershell
Stop-ScheduledTask -TaskName RecetasWeb -ErrorAction SilentlyContinue
Export-ScheduledTask -TaskName RecetasWeb | Out-File "$Old\RecetasWeb-v1-task.xml"   # respaldo de la tarea v1
Unregister-ScheduledTask -TaskName RecetasWeb -Confirm:$false

$cmd = "set RECETAS_VIDEOS_DIR=$Old\videos&& set RECETAS_SECRET_DIR=C:\ProgramData\recetas-web\secret&& `"$New\run.bat`" --port 8088"
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmd" -WorkingDirectory $New
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName RecetasWeb -Action $action -Trigger $trigger -Settings $settings -User SYSTEM -RunLevel Highest
Start-ScheduledTask -TaskName RecetasWeb
Start-Sleep 5; Invoke-RestMethod http://localhost:8088/api/health
```

> Desde la v2.1.0 la tarea la definen tus scripts de operaciones (`start-recetas.ps1`, ver «Configuración y cambio de
> dirección/puerto»); el bloque anterior queda como referencia de la instalación de la Fase 1.

Firewall (mismos nombres que gestiona la aplicación):

```powershell
New-NetFirewallRule -DisplayName "Recetario 8088 (LAN)" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Recetario 8088 (Tailscale)" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow -RemoteAddress 100.64.0.0/10
```

## Configuración y cambio de dirección/puerto (contrato de producción)

La tarea **RecetasWeb** (SYSTEM) ejecuta `C:\ProgramData\recetas-web\bin\start-recetas.ps1`, que:

1. lee `C:\ProgramData\recetas-web\config.env` (`CLAVE=valor`: `RECETAS_HOST`, `RECETAS_PORT`, y cualquier otra
   `RECETAS_*`) y exporta `RECETAS_CONFIG_FILE` apuntando a él;
2. arranca `run.py --host … --port …` y comprueba `/api/health` durante 45 s;
3. si falla, copia el archivo malo a `config.env.failed`, restaura `config.env.last-good` y reinicia; si va bien,
   copia `config.env` a `config.env.last-good`.

Una nueva ejecución (`schtasks /Run /TN RecetasWeb`, instancias en paralelo) mata el servidor anterior por su archivo pid.
La aplicación **no cambia** este contrato; solo:

- **Ajustes → Acceso** (solo con sesión de administrador y token CSRF) muestra las URLs (LAN, Tailscale `100.x`,
  `localhost`), un botón copiar y un QR generado en el propio servidor; y permite cambiar dirección y puerto.
- Validación: puerto entero 1024–65535 libre (se prueba a abrirlo; el actual cuenta como libre); dirección `0.0.0.0`,
  `127.0.0.1` o una IP de una interfaz de este equipo.
- Escribe `RECETAS_CONFIG_FILE` de forma **atómica** (temporal + renombrado) conservando las demás claves y comentarios.
- Si cambia el puerto, crea **solo** sus propias reglas de cortafuegos: `Recetario <puerto> (LAN)` (perfil Privado) y
  `Recetario <puerto> (Tailscale)` (remoto `100.64.0.0/10`). Las del puerto anterior se borran cuando el servidor nuevo
  responde a `/api/health`; si hubo marcha atrás, se borran las del puerto nuevo. Nunca toca otras reglas (tampoco la
  antigua `Recetario 8088` creada a mano: bórrala tú si ya no la quieres).
- Lanza `schtasks /Run /TN RecetasWeb`. La página espera hasta ~60 s a que la nueva URL responda y redirige; si no,
  avisa de que se restauró la configuración anterior y se queda en la URL actual.
- Fuera de Windows o sin `RECETAS_CONFIG_FILE` guarda el archivo (o `.env`) y avisa de que hay que reiniciar a mano.

Prioridad de configuración: argumentos de `run.py` > variables de entorno > `config.env`/`.env` > valores por defecto.
Como el script pasa `--host/--port` leídos del propio `config.env`, el archivo manda en la práctica.

## Volver a la v1

```powershell
Unregister-ScheduledTask -TaskName RecetasWeb -Confirm:$false
Register-ScheduledTask -TaskName RecetasWeb -Xml (Get-Content "$Old\RecetasWeb-v1-task.xml" -Raw)
Start-ScheduledTask -TaskName RecetasWeb
```

## Notas

- Los datos nuevos viven en `recetas-web-v2\data\recetas.db` (+ `media\`). La primera ejecución siembra la BD con las
  recetas v1 incluidas en `data\seed\`. Respalda `data\`, `media\` y la carpeta secreta.
- La UI exige sesión de administrador (v2.1.0). Las API externas (`/api/v1`, `/mcp`) exigen token.
- Backlog y Fase 3: [docs/ROADMAP.md](docs/ROADMAP.md). Historial: [CHANGELOG.md](CHANGELOG.md).
