# Contexto del proyecto: controller_fusion.py

Este archivo es para que una IA (o vos mismo en otra sesión/equipo) retome el
proyecto sin tener que releer todo el historial de chat. Está en español
porque así trabajamos la conversación; el código en sí está en inglés.

## Qué es esto

Joel y sus amigos (4 a 6 personas) quieren jugar **Ultimate Marvel vs Capcom 3**
en un solo PC, cada uno con su propio mando Xbox 360 (conectado como mando
virtual vía **Parsec**, algunos son fightsticks), pero controlando **un solo
equipo entre varios**: cada amigo maneja un personaje distinto del mismo team,
o se arma 2v2/3v2/3v3 (dos lados, cada lado con 2-3 amigos compartiendo un
control).

UMVC3 solo puede leer hasta 4 mandos vía XInput, así que la solución es
**fusionar** N mandos físicos en 1 o 2 mandos **virtuales** que el juego ve
como si fueran mandos normales.

## Stack técnico

- **Windows only.**
- Lee los mandos físicos con **pygame** (backend SDL2), no con la librería
  XInput directa (SDL puede leer más de 4 dispositivos, XInput clásico no).
- Crea el/los mando(s) virtual(es) con **vgamepad**, que usa el driver
  **ViGEmBus** (mismo driver que usa Parsec por debajo). vgamepad instala
  ViGEmBus la primera vez que se usa.
- **NO se usa vJoy.** Se probó tener vJoy instalado en paralelo durante el
  debugging pero no forma parte del diseño final (el usuario lo desinstaló).

## Archivo único: `controller_fusion.py`

Todo el proyecto es un solo script. Comandos:

```
python controller_fusion.py --list                    # lista mandos detectados con su indice
python controller_fusion.py --diagnose N [seg]         # loguea ejes/botones de un mando (calibracion)
python controller_fusion.py --identify                 # cada persona apreta un boton, se ve que indice es
python controller_fusion.py --profile-create N [nombre]  # wizard: crea un perfil de botones para el mando N
python controller_fusion.py --profile-list              # lista perfiles guardados
python controller_fusion.py --setup                     # wizard: asigna mandos a P1/P2 + perfil, GUARDA
                                                          # session.json y arranca a jugar directo
python controller_fusion.py                             # corre. Usa session.json si existe, si no CONFIG
```

Dependencias (`pygame`, `vgamepad`) se auto-instalan solas la primera vez que
falta alguna (ver `_ensure_package` al principio del archivo). Si el auto
-install falla (sin internet, sin pip, etc.) lo avisa con un mensaje claro y
corta, no queda colgado ni tira traceback crudo. Esto hace que el proyecto sea
transportable: en un equipo nuevo alcanza con tener Python 3.9+ con pip
instalado (eso sí hay que instalarlo a mano, un script de Python no puede
auto-instalar Python) y correr `python controller_fusion.py --setup`.

## Archivos de datos (se generan solos, no se editan a mano normalmente)

- `profiles.json` — perfiles de botones guardados por nombre. Cada perfil
  mapea los nombres logicos (A, X, Y, B, LB, RB, BACK, START, y
  opcionalmente LT, RT, LS, RS) a `{"type": "button"|"axis", "index": N}`
  del mando fisico. **El D-pad y los sticks NUNCA se remapean por perfil**,
  siempre usan el layout fijo de `AXES` en el CONFIG del script.
- `session.json` — la ultima asignacion hecha con `--setup`: que indice
  fisico va a P1 o P2, y con que perfil. Si existe, `run()` la usa en vez
  del `CONFIG` hardcodeado del script.
- `logs/diagnose_N.log` — logs de calibracion (no hacen falta para jugar,
  solo para debug puntual de mapeo de ejes/botones).

## Decisiones de diseño importantes (el "por qué")

1. **Equivalencia de botones Xbox <-> PlayStation** usada en los perfiles
   (los fightsticks suelen pensarse en terminos PS): A=Cross, B=Circle,
   X=Square, Y=Triangle, LB=L1, RB=R1, LT=L2, RT=R2, BACK=Select,
   START=Start, LS=L3, RS=R3.

2. **Botones obligatorios** para crear un perfil: Cross, Square, Triangle,
   Circle, **L1, R1**, Select, Start (8 en total). Opcionales (se eligen
   uno por uno, no es todo-o-nada): L2, R2, L3, R3.
   ⚠️ Ojo: en un momento hubo confusion entre el usuario y yo sobre si eran
   R1+R2 o L1+R1 — la respuesta final confirmada por el usuario es **L1 y
   R1** (R2/L2 quedaron como opcionales). Si en algun momento esto vuelve a
   generar dudas, priorizar lo que diga el usuario en el momento, esto solo
   quedo como default.

3. **Perfil "standard"**: existe implicitamente (no hace falta crearlo ni
   se guarda en `profiles.json`), es identico al mapeo por defecto
   `BUTTONS`/`AXES` del script. Sirve para gente con mando normal, sin
   layout raro, que no necesita remapear nada. En `--setup`, si elegis
   Enter (standard) igual te deja ponerle un **nombre** a ese mapeo sin
   tener que apretar ningun boton (solo clona el standard bajo ese nombre),
   para que sea mas facil despues revisar "quien esta en cada lado" en el
   resumen (`session.json`) por nombre en vez de por indice pelado.

4. **Por que "merge" en vez de "switch" para el uso tipico**: la idea de
   "cada amigo controla un personaje del mismo equipo" funciona mejor con
   `modo="merge"` (todos los botones de las fuentes de un lado se
   OR-ean/combinan en el mismo mando virtual) porque el juego solo lee al
   personaje activo en pantalla en un momento dado, y ese input viene de
   quien este efectivamente jugando en ese momento — no hace falta ciclar
   manualmente con `switch` salvo que se pida explicitamente.

5. **Indices de mandos fisicos NO son estables** entre sesiones de Parsec.
   Cada vez que los amigos se reconectan hay que correr `--list` (o
   `--setup` de nuevo, que ya lo hace) para confirmar los indices.

6. **Por que `--identify` existe**: SDL/XInput no da nombres utiles (todos
   los mandos aparecen como "Xbox 360 Controller" sin distincion). No hay
   forma de saber "el indice 3 es el mando de tal persona" mirando la
   lista. La solucion es que cada persona apriete un boton y la consola
   avise en vivo que indice fue, una linea limpia por apretada (sin
   floodear con eventos de ejes). Esta integrado como paso opcional al
   principio de `--setup`.

## Bug real encontrado y resuelto: boton "pegado" por mapear un eje a un boton normal

Un fightstick andaba perfecto conectado directo y perfecto via Parsec, pero al
pasar por `controller_fusion.py` R1 (RB) quedaba **permanentemente apretado**
y anulaba las apretadas reales del companiero que compartia el mismo virtual
(merge = OR logico: si una fuente ya tiene el boton en true todo el tiempo, el
juego nunca ve el flanco de "recien apretado" de la otra fuente, asi que su
apretada real no genera ningun cambio visible - no es que se "pisen", es que
el compañero nunca logra generar una apretada nueva mientras el fantasma sigue
prendido).

**Causa real:** durante `--profile-create`, en algun momento el wizard capturo
un movimiento de EJE (el gatillo L2, eje 4) en vez de una apretada de BOTON
para RB. Los gatillos (L2/R2) en un mando Xbox descansan en -1.0 y van a +1.0
al presionar - **nunca pasan por 0**. Como el codigo interpreta "esta
apretado" para botones no-gatillo con `abs(valor) > 0.5`, un eje de gatillo
mal asignado a un boton normal da `abs(~1.0) > 0.5` = **true todo el tiempo**,
apretado o no. Se encontraron varios perfiles en `profiles.json` con este
mismo patron (RB/LT/RT/LS cross-wireados entre si) de intentos de calibracion
anteriores - no era un caso aislado.

**Fix aplicado:**
1. En `controller_fusion.py`, `_create_profile_interactive` ahora usa
   `_capture_for()`, que **rechaza automaticamente** una captura de tipo eje
   para cualquier boton que no sea LT/RT, y le pide a la persona que vuelva a
   apretar. Esto deberia prevenir que este bug se vuelva a guardar en silencio.
2. Para el caso puntual: el `--diagnose` de ese fightstick (antes de que
   empezara a fallar) ya habia mostrado que reporta el layout Xbox estandar
   de punta a punta (botones 0-7, ejes 4/5 igual que cualquier pad). O sea
   **nunca necesito un perfil custom** - el lio vino de calibrar a mano algo
   que ya andaba bien por defecto. Se cambio `session.json` para que ese
   indice use perfil `null` (standard) en vez de uno de los perfiles rotos.

**Leccion para el futuro:** antes de crear un perfil custom para un control
nuevo, correr `--diagnose` primero. Si el layout ya sale estandar (botones
0-9 tipicos, ejes 4/5 para gatillos), **no hace falta perfil custom**, usar
standard directamente evita este tipo de error de calibracion humana.
Quedaron varios perfiles de prueba con nombres tipo `guasa`, `guasssss`,
`tubi2`, `bake1`, etc en `profiles.json` de intentos previos - son basura de
debugging, se pueden borrar cuando el usuario confirme que no los necesita.

## Pendiente / proximo paso: HidHide

**Esto es lo que sigue, no esta hecho todavia.**

Problema detectado en las pruebas: UMVC3 lee hasta 4 mandos via XInput. Si
los mandos fisicos (los que llegan por Parsec, tambien expuestos como
XInput) siguen visibles para el juego ADEMAS de los 2 mandos virtuales que
crea este script, pasan dos cosas:

- Se puede superar el limite de 4 que soporta el juego.
- Si alguien aprieta **Start** en un mando fisico "de mas" (no uno de los
  2 virtuales) mientras el juego arranca, el juego lo toma como P1 o P2 en
  vez del virtual correspondiente, y hay que cerrar el juego y volver a
  abrirlo apretando Start solo en los virtuales, en orden. Es molesto pero
  tiene workaround manual por ahora.

**Solucion planeada:** instalar **HidHide**, ocultar los mandos fisicos
(los que llegan por Parsec) de TODAS las aplicaciones excepto
`python.exe` (que necesita seguir leyendolos via SDL para hacer la
fusion). Asi el juego (y Windows en general) solo va a ver los 2 mandos
virtuales que crea `controller_fusion.py`, sin duplicados ni cruces de
Start.

Tambien se detecto (no resuelto, solo documentado) que correr dos
instancias de `controller_fusion.py` al mismo tiempo (por ejemplo `--list`
en una consola mientras `run()` esta activo en otra) genera lecturas raras
de SDL (los mandos vJoy que habia en ese momento aparecieron reemplazados
por entradas fantasma "Xbox 360 Controller"). Conclusion practica: no
correr mas de una instancia a la vez. Esto refuerza por que hace falta
HidHide — evita que el juego y el script compitan por los mismos 4 slots
de XInput.

## Como retomar esto en otra maquina / otra sesion

1. Copiar la carpeta completa (o al menos `controller_fusion.py`,
   `profiles.json` y `session.json` si querer mantener los perfiles ya
   armados).
2. Tener Python 3.9+ instalado (con pip). Si no esta, instalarlo primero
   (por ejemplo via winget: `winget install Python.Python.3.12`).
3. Correr `python controller_fusion.py --setup` — instala solo lo que
   falte (pygame, vgamepad) y arranca el flujo interactivo de asignacion.
4. Si el objetivo de la sesion es seguir con HidHide, ese es el proximo
   paso natural: instalar HidHide, agregar `python.exe` a la whitelist, y
   ocultar los mandos fisicos que llegan por Parsec.
