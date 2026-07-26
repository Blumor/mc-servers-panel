@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul 2>&1

:: =====================================================================
::  SERVER.BAT v2 - Gestion d'un serveur Minecraft local
::  Telecharge Java et le jar tout seul, repare les pannes courantes.
::  Aide : server.bat help
:: =====================================================================

set "SCRIPT_NAME=server.bat"
set "CONF=server.conf"
set "PID_FILE=.server.pid"
set "RUNTIME=.runtime"
set "PANEL_DIR=mcpanel"

:: ---- valeurs par defaut, ecrasees par server.conf ----
set "PORT=25565"
set "RAM=4096"
set "MCVERSION="
set "SERVER_JAR=server.jar"
set "JAVA_BIN="
set "MOTD=Speedrun Server"
set "DIFFICULTY=hard"
set "MAXPLAYERS=8"

call :load_conf

set "CMD=%~1"
if "%CMD%"=="" set "CMD=start"
if /I "%CMD%"=="--help" set "CMD=help"
if /I "%CMD%"=="-h" set "CMD=help"
if /I "%CMD%"=="/?" set "CMD=help"

for %%C in (start stop restart reboot reset create delete clean logs status ip panel install jar java config help) do (
    if /I "%CMD%"=="%%C" goto run
)
call :err "Commande inconnue : %CMD%"
goto usage

:run
call :cmd_%CMD% %2 %3 %4
exit /b !ERRORLEVEL!


:: =====================================================================
::  SORTIE
:: =====================================================================
:: Pause de N secondes. On evite timeout.exe : il refuse de tourner
:: quand l'entree standard est redirigee (script appele depuis un pipe).
:sleep
:: ping envoie le 1er paquet tout de suite : il en faut N+1 pour attendre N secondes
set /a "_S=%~1+1"
ping -n !_S! 127.0.0.1 >nul 2>&1
exit /b 0

:log
echo   %~1
exit /b 0
:ok
echo   [OK] %~1
exit /b 0
:info
echo   [i]  %~1
exit /b 0
:warn
:: pas de "!" litteral ici : l'expansion retardee le mangerait
echo   [*]  %~1
exit /b 0
:err
echo   [X]  %~1 1>&2
exit /b 0
:title
echo.
echo   ==================================================================
echo    %~1
echo   ==================================================================
exit /b 0


:: =====================================================================
::  CONFIGURATION
:: =====================================================================
:load_conf
if not exist "%CONF%" exit /b 0
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%CONF%") do (
    set "key=%%A"
    set "val=%%B"
    if not "!key!"=="" if not "!val!"=="" set "!key!=!val!"
)
exit /b 0

:save_conf
(
    echo # Configuration du serveur - modifiable a la main
    echo PORT=!PORT!
    echo RAM=!RAM!
    echo MCVERSION=!MCVERSION!
    echo SERVER_JAR=!SERVER_JAR!
    echo JAVA_BIN=!JAVA_BIN!
    echo MOTD=!MOTD!
    echo DIFFICULTY=!DIFFICULTY!
    echo MAXPLAYERS=!MAXPLAYERS!
) > "%CONF%"
exit /b 0

:cmd_config
call :title "Configuration"
call :log "PORT       = !PORT!"
call :log "RAM        = !RAM! Mo"
call :log "MCVERSION  = !MCVERSION!"
call :log "SERVER_JAR = !SERVER_JAR!"
call :log "JAVA_BIN   = !JAVA_BIN!"
call :log "DIFFICULTY = !DIFFICULTY!"
echo.
call :info "Fichier : %CD%\%CONF%"
if not exist "%CONF%" (
    call :save_conf
    call :ok "server.conf cree."
)
exit /b 0


:: =====================================================================
::  OUTILS RESEAU / PROCESSUS
:: =====================================================================
:: Renvoie dans PIDFOUND le PID qui ecoute sur !PORT! (vide si libre)
:pid_by_port
set "PIDFOUND="
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /R /C:":!PORT! .*LISTENING"') do (
    if not "%%P"=="0" set "PIDFOUND=%%P"
)
exit /b 0

:is_running
call :pid_by_port
if defined PIDFOUND exit /b 0
exit /b 1

:: Verifie qu'un PID existe encore
:pid_alive
tasklist /FI "PID eq %~1" 2>nul | findstr /R /C:"^[a-zA-Z]" >nul
exit /b !ERRORLEVEL!


:: =====================================================================
::  JAVA : detection + installation portable
:: =====================================================================
:: Determine la version majeure de Java requise pour !MCVERSION!
:required_java
set "REQ=21"
if "!MCVERSION!"=="" exit /b 0
for /f "tokens=1,2 delims=." %%A in ("!MCVERSION!") do (
    set "MAJ=%%A"
    set "MIN=%%B"
)
if "!MAJ!"=="1" (
    if !MIN! LSS 17 set "REQ=8"
    if !MIN! GEQ 17 if !MIN! LSS 18 set "REQ=16"
    if !MIN! GEQ 18 if !MIN! LSS 20 set "REQ=17"
    if !MIN! GEQ 20 set "REQ=21"
)
exit /b 0

:: Version majeure de %1 -> JAVA_MAJOR (vide si inutilisable)
:: On passe par un fichier : un chemin avec espaces ("C:\Program Files\...")
:: casse la commande quand elle est lancee directement dans un for /f.
:java_major_of
set "JAVA_MAJOR="
if "%~1"=="" exit /b 1
if not exist "%~1" (
    where "%~1" >nul 2>&1 || exit /b 1
)
set "JVOUT=%TEMP%\mcjv_%RANDOM%.txt"
"%~1" -version > "%JVOUT%" 2>&1
if not exist "%JVOUT%" exit /b 1
for /f "tokens=3" %%V in ('findstr /I /C:" version " "%JVOUT%"') do (
    if not defined JAVA_MAJOR (
        set "raw=%%~V"
        for /f "tokens=1,2 delims=._" %%a in ("!raw!") do (
            if "%%a"=="1" (set "JAVA_MAJOR=%%b") else (set "JAVA_MAJOR=%%a")
        )
    )
)
del /f /q "%JVOUT%" >nul 2>&1
if not defined JAVA_MAJOR exit /b 1
exit /b 0

:: Cherche un Java >= REQ. Resultat dans JAVA_BIN.
:detect_java
call :required_java
set "FOUND="

:: 1) JRE portable installe par ce script
if exist "%RUNTIME%" (
    for /f "delims=" %%J in ('dir /b /s "%RUNTIME%\java.exe" 2^>nul') do (
        if not defined FOUND (
            call :java_major_of "%%J"
            if defined JAVA_MAJOR if !JAVA_MAJOR! GEQ !REQ! set "FOUND=%%J"
        )
    )
)
:: 2) valeur forcee dans server.conf
if not defined FOUND if not "!JAVA_BIN!"=="" (
    call :java_major_of "!JAVA_BIN!"
    if defined JAVA_MAJOR if !JAVA_MAJOR! GEQ !REQ! set "FOUND=!JAVA_BIN!"
)
:: 3) PATH
if not defined FOUND (
    call :java_major_of "java"
    if defined JAVA_MAJOR if !JAVA_MAJOR! GEQ !REQ! set "FOUND=java"
)
:: 4) JAVA_HOME
if not defined FOUND if not "%JAVA_HOME%"=="" (
    if exist "%JAVA_HOME%\bin\java.exe" (
        call :java_major_of "%JAVA_HOME%\bin\java.exe"
        if defined JAVA_MAJOR if !JAVA_MAJOR! GEQ !REQ! set "FOUND=%JAVA_HOME%\bin\java.exe"
    )
)
:: 5) installations classiques
if not defined FOUND (
    for %%R in ("%ProgramFiles%\Java" "%ProgramFiles%\Eclipse Adoptium" "%ProgramFiles%\Microsoft" "%ProgramFiles%\Zulu" "%ProgramFiles(x86)%\Java" "%LOCALAPPDATA%\Programs\Eclipse Adoptium" "%APPDATA%\.minecraft\runtime") do (
        if exist %%R (
            for /f "delims=" %%J in ('dir /b /s "%%~R\java.exe" 2^>nul') do (
                if not defined FOUND (
                    call :java_major_of "%%J"
                    if defined JAVA_MAJOR if !JAVA_MAJOR! GEQ !REQ! set "FOUND=%%J"
                )
            )
        )
    )
)
if defined FOUND (
    set "JAVA_BIN=!FOUND!"
    exit /b 0
)
exit /b 1

:ensure_java
call :detect_java
if !ERRORLEVEL!==0 (
    call :java_major_of "!JAVA_BIN!"
    call :ok "Java !JAVA_MAJOR! detecte."
    exit /b 0
)
call :warn "Aucun Java >= !REQ! trouve. Installation d'un JRE portable..."
call :install_java !REQ!
if !ERRORLEVEL! NEQ 0 exit /b 1
call :detect_java
if !ERRORLEVEL! NEQ 0 (
    call :err "Java installe mais introuvable. Installez-le manuellement : https://adoptium.net/"
    exit /b 1
)
call :save_conf
exit /b 0

:install_java
set "FEAT=%~1"
set "JURL=https://api.adoptium.net/v3/binary/latest/%FEAT%/ga/windows/x64/jre/hotspot/normal/eclipse"
set "JZIP=%TEMP%\temurin-jre-%FEAT%.zip"
call :log "Telechargement du JRE %FEAT% (~45 Mo)..."
call :download "%JURL%" "%JZIP%"
if !ERRORLEVEL! NEQ 0 (
    call :err "Telechargement de Java impossible. Verifiez votre connexion."
    call :info "Installation manuelle : https://adoptium.net/temurin/releases/?version=%FEAT%"
    exit /b 1
)
call :log "Extraction..."
if not exist "%RUNTIME%" mkdir "%RUNTIME%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try{ Expand-Archive -LiteralPath '%JZIP%' -DestinationPath '%RUNTIME%' -Force; exit 0 }catch{ exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    tar -xf "%JZIP%" -C "%RUNTIME%" 2>nul
    if !ERRORLEVEL! NEQ 0 (
        call :err "Extraction impossible. Archive corrompue ?"
        del /f /q "%JZIP%" >nul 2>&1
        exit /b 1
    )
)
del /f /q "%JZIP%" >nul 2>&1
call :ok "JRE %FEAT% installe dans %RUNTIME%\"
exit /b 0

:cmd_java
call :title "Java"
call :ensure_java
if !ERRORLEVEL! NEQ 0 exit /b 1
call :log "Binaire : !JAVA_BIN!"
"!JAVA_BIN!" -version 2>&1
exit /b 0

:cmd_install
call :title "Installation des prerequis"
call :ensure_java || exit /b 1
call :ensure_jar || exit /b 1
call :cmd_create
call :ok "Tout est pret. Lancez : %SCRIPT_NAME% start"
exit /b 0


:: =====================================================================
::  TELECHARGEMENTS
:: =====================================================================
:download
:: %1 = url, %2 = destination
where curl.exe >nul 2>&1
if !ERRORLEVEL!==0 (
    curl.exe -L --fail --silent --show-error --retry 3 --retry-delay 2 -o "%~2" "%~1"
    if !ERRORLEVEL!==0 if exist "%~2" exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try{ Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing; exit 0 }catch{ exit 1 }"
if !ERRORLEVEL!==0 if exist "%~2" exit /b 0
exit /b 1

:: Resout l'URL du jar serveur pour !MCVERSION! (vide = derniere release)
:resolve_jar_url
set "JARURL="
set "RESOLVED="
set "PS1=%TEMP%\mcresolve_%RANDOM%.ps1"
> "%PS1%" (
    echo $ErrorActionPreference = 'Stop'
    echo try {
    echo   $man = Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json' -UseBasicParsing
    echo   $want = '!MCVERSION!'
    echo   if ^([string]::IsNullOrWhiteSpace^($want^)^) { $want = $man.latest.release }
    echo   $entry = $man.versions ^| Where-Object { $_.id -eq $want } ^| Select-Object -First 1
    echo   if ^(-not $entry^) { throw "version inconnue : $want" }
    echo   $dl = ^(Invoke-RestMethod $entry.url -UseBasicParsing^).downloads.server
    echo   if ^(-not $dl^) { throw 'cette version ne fournit pas de serveur telechargeable' }
    echo   Write-Output ^($want + '^|' + $dl.url^)
    echo } catch {
    echo   Write-Output ^('ERR^|' + $_.Exception.Message^)
    echo }
)
for /f "usebackq delims=" %%L in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"`) do set "LINE=%%L"
del /f /q "%PS1%" >nul 2>&1
for /f "tokens=1,* delims=|" %%A in ("!LINE!") do (
    set "RESOLVED=%%A"
    set "JARURL=%%B"
)
if "!RESOLVED!"=="ERR" (
    call :err "Mojang : !JARURL!"
    set "JARURL="
    exit /b 1
)
if "!JARURL!"=="" (
    call :err "Impossible de contacter les serveurs Mojang."
    exit /b 1
)
exit /b 0

:ensure_jar
if exist "!SERVER_JAR!" (
    for %%F in ("!SERVER_JAR!") do if %%~zF GTR 100000 exit /b 0
    call :warn "!SERVER_JAR! est corrompu (trop petit), re-telechargement."
    del /f /q "!SERVER_JAR!" >nul 2>&1
)
call :log "Recherche du serveur Minecraft..."
call :resolve_jar_url
if !ERRORLEVEL! NEQ 0 exit /b 1
call :log "Telechargement de Minecraft !RESOLVED! (~50 Mo)..."
call :download "!JARURL!" "!SERVER_JAR!"
if !ERRORLEVEL! NEQ 0 (
    call :err "Telechargement du jar impossible."
    exit /b 1
)
set "MCVERSION=!RESOLVED!"
call :save_conf
call :ok "Minecraft !RESOLVED! pret (!SERVER_JAR!)."
exit /b 0

:cmd_jar
if not "%~1"=="" set "MCVERSION=%~1"
call :title "Serveur Minecraft"
if not "%~1"=="" if exist "!SERVER_JAR!" (
    call :info "Remplacement du jar par la version %~1"
    del /f /q "!SERVER_JAR!" >nul 2>&1
)
call :ensure_jar
exit /b !ERRORLEVEL!


:: =====================================================================
::  FICHIERS DE CONFIGURATION DU SERVEUR
:: =====================================================================
:cmd_create
set "N=0"
if exist eula.txt (
    findstr /I /C:"eula=true" eula.txt >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo eula=true> eula.txt
        call :ok "eula.txt corrige (eula=true)."
        set /a N+=1
    )
) else (
    echo eula=true> eula.txt
    call :ok "eula.txt cree."
    set /a N+=1
)

if exist server.properties (
    call :sync_props
) else (
    (
        echo #Minecraft server properties
        echo allow-flight=false
        echo difficulty=!DIFFICULTY!
        echo enable-command-block=false
        echo enforce-secure-profile=false
        echo gamemode=survival
        echo hardcore=false
        echo level-name=world
        echo level-seed=
        echo level-type=minecraft\:normal
        echo max-players=!MAXPLAYERS!
        echo motd=!MOTD!
        echo online-mode=true
        echo prevent-proxy-connections=false
        echo pvp=true
        echo server-port=!PORT!
        echo simulation-distance=8
        echo spawn-protection=0
        echo sync-chunk-writes=false
        echo view-distance=10
        echo white-list=false
    ) > server.properties
    call :ok "server.properties cree."
    set /a N+=1
)

if not exist whitelist.json (
    echo [] > whitelist.json
    call :ok "whitelist.json cree (vide - ajoutez vos potes avec /whitelist add)."
    set /a N+=1
)
if not exist ops.json echo [] > ops.json

if !N!==0 call :info "Configuration deja complete."
exit /b 0

:: Aligne server.properties sur server.conf sans ecraser le reste
:sync_props
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='server.properties'; $l=Get-Content $p; $set=@{'server-port'='!PORT!'};" ^
  "foreach($k in $set.Keys){ if($l -match ('^'+[regex]::Escape($k)+'=')){ $l = $l -replace ('^'+[regex]::Escape($k)+'=.*'), ($k+'='+$set[$k]) } else { $l += ($k+'='+$set[$k]) } };" ^
  "Set-Content $p $l" 2>nul
exit /b 0


:: =====================================================================
::  CYCLE DE VIE
:: =====================================================================
:cmd_start
call :title "Demarrage du serveur"
call :is_running
if !ERRORLEVEL!==0 (
    call :err "Un serveur ecoute deja sur le port !PORT! (PID !PIDFOUND!)."
    call :info "Utilisez : %SCRIPT_NAME% stop   ou   %SCRIPT_NAME% restart"
    exit /b 1
)

call :ensure_java
if !ERRORLEVEL! NEQ 0 exit /b 1
call :ensure_jar
if !ERRORLEVEL! NEQ 0 exit /b 1
call :cmd_create

:: RAM : on refuse une valeur absurde
if !RAM! LSS 1024 (
    call :warn "RAM trop basse (!RAM! Mo), remontee a 1024 Mo."
    set "RAM=1024"
)

set "JVM=-Xms!RAM!M -Xmx!RAM!M -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200"
set "JVM=!JVM! -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch"
set "JVM=!JVM! -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M"
set "JVM=!JVM! -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4"
set "JVM=!JVM! -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90"
set "JVM=!JVM! -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem"
set "JVM=!JVM! -XX:MaxTenuringThreshold=1 -Dfile.encoding=UTF-8"

call :log "RAM !RAM! Mo - port !PORT!"
:: On passe par un lanceur genere : evite tout probleme de guillemets imbriques.
> ".launch.cmd" (
    echo @echo off
    echo title Minecraft !MCVERSION! - port !PORT!
    echo cd /d "%CD%"
    echo "!JAVA_BIN!" !JVM! -jar "!SERVER_JAR!" nogui
    echo echo.
    echo echo [Serveur arrete] Vous pouvez fermer cette fenetre.
    echo pause ^>nul
)
start "Minecraft !MCVERSION! - port !PORT!" cmd /c ".launch.cmd"

call :log "Attente de l'ouverture du port !PORT!..."
set "WAIT=0"
:wait_start
call :sleep 1
call :is_running
if !ERRORLEVEL!==0 goto started
set /a WAIT+=1
if !WAIT! GEQ 180 (
    call :err "Le serveur n'a pas demarre en 3 minutes."
    call :info "Regardez la fenetre du serveur ou lancez : %SCRIPT_NAME% logs"
    exit /b 1
)
if !WAIT!==20 call :log "toujours en cours (generation du monde)..."
if !WAIT!==60 call :log "patience, premiere generation de monde..."
goto wait_start

:started
call :pid_by_port
echo !PIDFOUND!> "%PID_FILE%"
call :ok "Serveur en ligne (PID !PIDFOUND!) apres !WAIT!s."
call :show_addresses
exit /b 0

:cmd_stop
call :is_running
if !ERRORLEVEL! NEQ 0 (
    call :info "Aucun serveur n'ecoute sur le port !PORT!."
    del /f /q "%PID_FILE%" >nul 2>&1
    exit /b 0
)
call :log "Arret du serveur (PID !PIDFOUND!), sauvegarde du monde..."
call :ctrl_c !PIDFOUND!
set "WAIT=0"
:wait_stop
call :sleep 1
call :is_running
if !ERRORLEVEL! NEQ 0 goto stopped
set /a WAIT+=1
if !WAIT! GEQ 12 (
    call :warn "Pas de reponse au Ctrl+C, arret en force."
    call :info "Minecraft sauvegarde tout seul toutes les 5 min : au pire vous perdez"
    call :info "les dernieres minutes. Le panel web ('%SCRIPT_NAME% panel') pilote la"
    call :info "console du serveur et garantit un arret propre."
    taskkill /F /PID !PIDFOUND! /T >nul 2>&1
    call :sleep 2
    goto stopped
)
goto wait_stop

:stopped
del /f /q "%PID_FILE%" >nul 2>&1
call :ok "Serveur arrete."
exit /b 0

:: Envoie un vrai Ctrl+C a la console du serveur : Java execute son shutdown
:: hook et Minecraft sauvegarde le monde. taskkill sans /F ne marche pas ici,
:: une application console n'a pas de fenetre a qui envoyer WM_CLOSE.
:ctrl_c
set "PSC=%TEMP%\mcstop_%RANDOM%.ps1"
> "%PSC%" (
    echo $target = %~1
    echo Add-Type -TypeDefinition @"
    echo using System;
    echo using System.Runtime.InteropServices;
    echo public static class ConsoleCtrl {
    echo   [DllImport^("kernel32.dll", SetLastError=true^)] public static extern bool AttachConsole^(uint pid^);
    echo   [DllImport^("kernel32.dll", SetLastError=true^)] public static extern bool FreeConsole^(^);
    echo   [DllImport^("kernel32.dll"^)] public static extern bool SetConsoleCtrlHandler^(IntPtr handler, bool add^);
    echo   [DllImport^("kernel32.dll"^)] public static extern bool GenerateConsoleCtrlEvent^(uint evt, uint group^);
    echo }
    echo "@
    echo [ConsoleCtrl]::FreeConsole^(^) ^| Out-Null
    echo if ^([ConsoleCtrl]::AttachConsole^($target^)^) {
    echo   [ConsoleCtrl]::SetConsoleCtrlHandler^([IntPtr]::Zero, $true^) ^| Out-Null
    echo   [ConsoleCtrl]::GenerateConsoleCtrlEvent^(0, 0^) ^| Out-Null
    echo   Start-Sleep -Milliseconds 400
    echo   [ConsoleCtrl]::FreeConsole^(^) ^| Out-Null
    echo }
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PSC%" >nul 2>&1
del /f /q "%PSC%" >nul 2>&1
exit /b 0

:: Arret immediat, sans sauvegarde : pour les resets, ou le monde part a la poubelle
:force_stop
call :is_running
if !ERRORLEVEL! NEQ 0 exit /b 0
taskkill /F /PID !PIDFOUND! /T >nul 2>&1
call :sleep 1
del /f /q "%PID_FILE%" >nul 2>&1
exit /b 0

:cmd_restart
call :title "Redemarrage"
call :cmd_stop
call :sleep 1
call :cmd_start
exit /b !ERRORLEVEL!

:: reset = monde neuf, config conservee (le vrai bouton speedrun)
:: Pas d'arret propre : le monde est supprime juste apres, autant gagner les secondes.
:cmd_reset
call :title "Reset du monde"
call :force_stop
call :wipe_worlds
call :cmd_start
exit /b !ERRORLEVEL!

:cmd_reboot
call :cmd_reset
exit /b !ERRORLEVEL!

:wipe_worlds
set "LEVEL=world"
if exist server.properties (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("server.properties") do (
        if /I "%%A"=="level-name" set "LEVEL=%%B"
    )
)
for %%W in ("!LEVEL!" "!LEVEL!_nether" "!LEVEL!_the_end" "world" "world_nether" "world_the_end") do (
    if exist %%W (
        rd /s /q %%W >nul 2>&1
        if exist %%W (
            call :warn "%%W verrouille, nouvelle tentative..."
            call :sleep 2
            rd /s /q %%W >nul 2>&1
        )
    )
)
if exist crash-reports rd /s /q crash-reports >nul 2>&1
call :ok "Monde supprime."
exit /b 0

:: delete = nettoyage sur (ne touche qu'aux fichiers generes par Minecraft)
:cmd_delete
call :cmd_clean
exit /b !ERRORLEVEL!

:cmd_clean
call :title "Nettoyage"
call :cmd_stop
call :wipe_worlds
for %%D in (logs crash-reports libraries versions cache .fabric .mixin.out) do (
    if exist %%D rd /s /q %%D >nul 2>&1
)
for %%F in (usercache.json usernamecache.json banned-ips.json banned-players.json session.lock) do (
    if exist %%F del /f /q %%F >nul 2>&1
)
call :ok "Mondes, logs et caches supprimes."
call :info "Conserves : !SERVER_JAR!, %SCRIPT_NAME%, %CONF%, server.properties, whitelist.json, ops.json, %RUNTIME%\"
exit /b 0


:: =====================================================================
::  INFOS
:: =====================================================================
:cmd_status
call :title "Etat du serveur"
call :is_running
if !ERRORLEVEL!==0 (
    call :ok "EN LIGNE - port !PORT! - PID !PIDFOUND!"
) else (
    call :info "Hors ligne (port !PORT! libre)."
)
if exist "!SERVER_JAR!" (
    for %%F in ("!SERVER_JAR!") do call :log "Jar        : !SERVER_JAR! (%%~zF octets)"
) else (
    call :warn "Jar        : absent - sera telecharge au demarrage"
)
call :detect_java
if !ERRORLEVEL!==0 (
    call :java_major_of "!JAVA_BIN!"
    call :log "Java       : !JAVA_MAJOR! (!JAVA_BIN!)"
) else (
    call :warn "Java       : absent - sera installe au demarrage"
)
call :log "Version MC : !MCVERSION!"
call :log "RAM        : !RAM! Mo"
if exist world (
    call :log "Monde      : present"
) else (
    call :log "Monde      : aucun (sera genere)"
)
call :show_addresses
exit /b 0

:show_addresses
echo.
call :log "Pour toi        : localhost:!PORT!"
for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /R /C:"IPv4.*: 192\.168\." /C:"IPv4.*: 10\." /C:"IPv4.*: 172\."') do (
    set "LAN=%%I"
    set "LAN=!LAN: =!"
    if not "!LAN!"=="" call :log "Sur ton reseau  : !LAN!:!PORT!"
)
exit /b 0

:cmd_ip
call :title "Adresses"
call :show_addresses
echo.
call :log "IP publique (a donner a tes potes) :"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try{(Invoke-RestMethod 'https://api.ipify.org?format=json' -UseBasicParsing).ip}catch{'indisponible'}"`) do (
    call :log "  %%P:!PORT!"
)
echo.
call :info "Pense a ouvrir le port !PORT! (TCP) sur ta box et dans le pare-feu Windows."
call :info "Pare-feu : %SCRIPT_NAME% panel puis clique, ou commande admin :"
call :log "  netsh advfirewall firewall add rule name=\"Minecraft !PORT!\" dir=in action=allow protocol=TCP localport=!PORT!"
exit /b 0

:cmd_logs
if not exist "logs\latest.log" (
    call :err "Aucun log. Le serveur n'a jamais demarre dans ce dossier."
    exit /b 1
)
call :title "Logs en direct (Ctrl+C pour quitter)"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content 'logs\latest.log' -Wait -Tail 40"
exit /b 0


:: =====================================================================
::  PANEL WEB
:: =====================================================================
:cmd_panel
call :title "Panel web"
if not exist "%PANEL_DIR%\__main__.py" (
    call :err "Dossier %PANEL_DIR% introuvable a cote de ce script."
    exit /b 1
)
set "PY="
for %%P in (py.exe python.exe python3.exe) do (
    if not defined PY (
        where %%P >nul 2>&1 && set "PY=%%P"
    )
)
if not defined PY (
    call :err "Python 3 n'est pas installe."
    call :info "Installation rapide : winget install -e --id Python.Python.3.12"
    call :info "Ou telecharger : https://www.python.org/downloads/  (cochez 'Add to PATH')"
    choice /C ON /N /M "  Lancer l'installation via winget maintenant ? [O/N] "
    if !ERRORLEVEL!==1 (
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        call :info "Relancez : %SCRIPT_NAME% panel"
    )
    exit /b 1
)
call :ok "Python trouve (%PY%)."
call :log "Ouverture du panel sur http://localhost:8765/ ..."
if /I "%PY%"=="py.exe" (
    py -3 -m mcpanel
) else (
    %PY% -m mcpanel
)
exit /b !ERRORLEVEL!


:: =====================================================================
::  AIDE
:: =====================================================================
:cmd_help
:usage
echo.
echo   SERVER.BAT - serveur Minecraft local
echo.
echo   Utilisation : %SCRIPT_NAME% [commande]
echo.
echo     panel        Ouvre le panel web (recommande - tout en boutons)
echo     start        Demarre le serveur (par defaut)
echo     stop         Arrete proprement le serveur de ce port
echo     restart      Arret puis redemarrage
echo     reset        Monde neuf, config conservee  ^<-- speedrun
echo     clean        Supprime mondes, logs et caches
echo     create       Genere eula / server.properties / whitelist manquants
echo     status       Etat, version, Java, adresses
echo     logs         Console en direct
echo     ip           IP locale et publique + rappel pare-feu
echo     install      Telecharge Java + le jar et prepare tout
echo     jar [ver]    Telecharge une version precise (ex: jar 1.21.4)
echo     java         Verifie / installe Java
echo     config       Affiche la configuration
echo.
echo   Configuration : server.conf  (PORT, RAM, MCVERSION, DIFFICULTY...)
echo.
exit /b 0
