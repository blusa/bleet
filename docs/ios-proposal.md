# Bleet: app para iPhone, widgets y backend privado

Propuesta de diseño, 14 de noviembre de 2026. Incluye mockups interactivos con datos inventados; no implementa la aplicación ni un servicio real.

## Nombre y organización del repositorio

Nombre elegido por el usuario: **Bleet**. La app se llama Bleet, el cliente/CLI puede usar `bleet` y el servicio privado se llama `bleetd`. La app y el backend se desarrollan en este mismo repositorio, junto a las versiones existentes de Blussh.

Estructura propuesta para la implementación:

```text
ios/
  Bleet/            App SwiftUI
  BleetWidgets/     Extensión WidgetKit
backend/            bleetd: API, colectores, persistencia y MCP
shared/             Contratos de API y muestras para Swift/Python
macos/              Blussh para macOS
omarchy/            Blussh para Omarchy y motor Python actual
docs/               Diseño, mockups y especificaciones
```

`ios/`, `backend/` y `shared/` son directorios propuestos, todavía no creados. Mantener app y backend juntos permite revisar en el mismo cambio las métricas, el contrato de datos, los widgets y las herramientas MCP. Los contratos compartidos definen identificadores estables, unidades, fechas, valores ausentes y permisos; los ejemplos compartidos facilitan probar los mismos casos en Swift y Python.

El backend reutiliza el comportamiento del motor Python existente. La extracción de lógica común de descubrimiento, fusión y confirmación de estados se hará al implementar su integración, con sus pruebas y distribución, para que las dos aplicaciones Python consuman una implementación común. Cada producto conserva su proceso de compilación, pruebas y publicación dentro del repositorio; la ubicación no obliga a desplegar todo a la vez.

## Qué conservar

Equipos descubiertos por SSH config, Tailscale y ZeroTier; fusión entre fuentes; estado de red y de SSH por separado; selección de equipos monitoreados; confirmación tras dos comprobaciones; copiar dirección/comando SSH; acceso a T3 y generación de vínculos; monitor btop/htop/top. Se mantiene el identificador estable de cada equipo.

## Enfoque recomendado

App nativa con SwiftUI, Network.framework para comprobaciones desde el teléfono y URLSession para consultar un servicio privado. Ese servicio corre en una máquina siempre encendida que ya tiene acceso a las redes: permite reutilizar el motor Python de Omarchy y conservar el descubrimiento mediante las herramientas locales existentes. El teléfono no puede ejecutar sus CLIs ni leer archivos o credenciales de las apps de VPN de iOS.

El servicio descubre y comprueba los equipos de forma continua. Expone inventario, estados, errores de fuentes, fecha de cada comprobación y eventos confirmados. La app consulta cada 10 segundos mientras está visible y conserva una copia local. Los estados de los mockups corresponden a la perspectiva del servicio; la accesibilidad desde el iPhone se indica por separado y se comprueba antes de una conexión SSH o T3.

El iPhone usa la app Tailscale o ZeroTier instalada y la ruta de acceso configurada. No se presupone que ambas VPN puedan estar activas al mismo tiempo ni que el servicio resulte accesible por ambas. Se configura una dirección por ruta. HTTPS necesita un certificado verificable: Tailscale Serve es una opción para Tailscale; ZeroTier requiere resolver DNS/certificado o establecer confianza explícita mediante la vinculación. No se desactiva la validación TLS.

Alternativas: conectar únicamente desde iPhone evita instalar el servicio, pero obliga a configurar inventario/credenciales allí y no ofrece monitoreo continuo ni acceso al CLI de otras apps. Una web privada reduce desarrollo, pero ofrece peor integración con terminal, widgets y Keychain. Recomiendo SwiftUI más servicio privado para esta propuesta; es una decisión de diseño pendiente de la implementación.

## Adaptación a iPhone Duo

Información contrastada con Apple el 14 de noviembre de 2026: iPhone Duo tiene pantalla interior plegable de 7,6 pulgadas y exterior de 5,4 pulgadas, y permite Split View. La página del producto también muestra uso apoyado y StandBy sin necesidad de carga. Fuentes: [producto](https://www.apple.com/iphone-duo/), [ficha técnica](https://www.apple.com/iphone-duo/specs/) y [guía de layout de Apple](https://developer.apple.com/design/human-interface-guidelines/layout).

La optimización sigue el espacio real de la ventana y sus size classes. No decide el diseño comparando el nombre del dispositivo ni deduciendo puntos de UI a partir de la resolución en píxeles. El prototipo de Duo usa proporciones ilustrativas para distinguir formatos; no representa una captura de la app nativa ni valida tamaños de Simulator.

- **Cerrado / espacio compacto:** equipo seleccionado, matriz de CPU y gauge de la GPU elegida; RAM y VRAM en barras. Selector de equipo y de GPU accesibles, con acciones principales a mano. La pantalla exterior es más corta en proporción que la de un iPhone tradicional: se reorganiza el contenido y se conserva texto legible.
- **Abierto / espacio ancho:** navegación en dos paneles, con equipos a la izquierda y detalle a la derecha. El espacio extra permite mostrar el heatmap de CPU y las dos GPU del ejemplo a la vez. Las barras de RAM y VRAM seleccionada comparten fila. El inventario y la información secundaria permanecen accesibles sin ocupar permanentemente un tercer panel.
- **Split View con otra app:** Bleet se adapta al ancho que le asigna iOS, aunque el teléfono siga abierto. Un flujo útil es Bleet junto a T3/Safari: monitoreo en un lado y sesión de trabajo en el otro. El usuario organiza Split View mediante iOS; no se promete colocar automáticamente otra app en una mitad específica.
- **Apoyado / modo de mesa:** propuesta opcional con métricas arriba y terminal/controles abajo, preservando legibilidad y espacio para teclado. El mockup ofrece un selector manual de disposición. La detección automática de postura depende de APIs públicas verificadas en el SDK; no se presupone acceso al ángulo de la bisagra ni control simultáneo de ambas pantallas.
- **StandBy y widgets:** núcleos, gauge y memoria del equipo favorito con fecha visible. La vista se adapta a modos tintados, contraste y accesibilidad; color no es la única forma de identificar carga y valores ausentes. Se conserva el presupuesto de actualización que asigna iOS y no se presenta la última muestra como una transmisión continua.

Implementación prevista: `NavigationSplitView` para lista/detalle cuando el ancho lo permita; `ViewThatFits`, grids y layouts adaptativos para reorganizar instrumentos. Con Dynamic Type grande o una ventana estrecha se reduce la cantidad de paneles y se permite desplazamiento. Safe areas, barras del sistema y teclado se toman de la ventana actual. La pantalla interior se trata como una superficie continua, no como dos pantallas separadas por un hueco inventado.

Un modelo de sesión estable, fuera de las vistas que se reorganizan, conserva `HostID`, UUID de GPU, identificador de núcleo, navegación y lecturas. Plegar o rotar cambia la presentación; no dispara descubrimientos completos, nuevos pairings T3 ni nuevas conexiones por cada panel. La sesión SSH vive en un servicio independiente de la vista, dentro de los límites del ciclo de vida de iOS. Si cambia el tamaño del terminal, se actualizan las dimensiones del PTY para que btop/htop/top se redibuje.

Rendimiento y batería: una fuente de muestras compartida por toda la UI, solicitudes agrupadas al backend y actualizaciones por cambio de datos. ProMotion a 120 Hz no implica consultar métricas 120 veces por segundo ni animar celdas continuamente. Al perder visibilidad se detienen consultas de primer plano; al volver se comprueba frescura y conectividad. Se respetan Reduce Motion y modo de bajo consumo.

Validación nativa pendiente: pantalla exterior, interior en ambas orientaciones, transición mientras hay un equipo/GPU/core seleccionado, Split View en distintos anchos, teclado con terminal activo, Dynamic Type grande, VoiceOver, modo de bajo consumo y datos sin VPN. El prototipo permite comprobar continuidad de selección y cambios de disposición con datos de ejemplo.

## Pantallas

1. **Equipos:** resumen, búsqueda, filtro de problemas y grupos por origen. Disponible significa que los controles aplicables responden; un equipo con red disponible y SSH caído requiere atención.
2. **Detalle:** red y SSH separados, dirección/usuario/puerto, monitoreo y acciones. Se suma una vista de recursos e inventario con modelos, capacidades y métricas por GPU. En implementación se copiará una dirección resoluble por el iPhone; un alias del SSH config del servidor no necesariamente existe en el teléfono.
3. **Terminal / monitor:** terminal SSH con PTY y soporte de secuencias ANSI, usando SwiftTerm más un transporte SSH compatible con iOS. Se comprueba la clave del servidor mediante known_hosts y se conservan claves del teléfono en Keychain. btop/htop/top corre en el equipo remoto, igual que hoy. La biblioteca de transporte y su licencia se validarán al implementar.
4. **T3:** abrir sesión existente, escanear QR y generar un enlace temporal mediante una acción autorizada. El deep link sólo se usará si hay un cliente compatible instalado; la alternativa es el flujo HTTPS de T3.
5. **Actividad:** registro local de transiciones confirmadas, sin incluir tokens ni enlaces de pairing. Es una ampliación del producto actual, que notifica transiciones pero no ofrece historial persistente.
6. **Red:** acceso al servicio, ruta elegida, última lectura y frecuencia de actualización en primer plano. No intenta administrar otra app VPN ni atribuir con certeza un fallo a la VPN.
7. **Vinculación inicial:** QR de bleetd para registrar el teléfono en Bleet. Es distinto del QR de T3.
8. **Sin acceso:** copia guardada, fecha visible y estado sin verificar. La pérdida de acceso al servicio no convierte todos los equipos en caídos.
9. **Widgets de inicio:** pequeño con resumen y mediano con equipos que requieren atención y favoritos.
10. **Widget bloqueado:** resumen discreto; se puede ocultar el nombre de los equipos en la pantalla bloqueada.

## Widgets

WidgetKit y App Intents para abrir la app o el detalle mediante un identificador de equipo. Un App Group comparte una copia mínima del inventario, estado y fecha entre app y extensión. Las credenciales no se guardan en el contenedor compartido. Si se habilitan consultas desde la extensión, tendrá sólo una credencial de lectura en un Keychain Access Group explícito; nunca permisos para terminal o generar pairing.

Se usa una Timeline para representar el tiempo transcurrido y degradar datos antiguos a “sin verificar”. La app solicita una recarga tras obtener datos nuevos; iOS decide cuándo ejecutar la extensión y aplicar actualizaciones. El widget no mantiene conexiones permanentes, no activa la VPN y no promete segundos de refresco. Con la VPN inaccesible muestra la última lectura. Un toque abre la app para actualizar y realizar acciones autenticadas.

Los widgets usan el mismo lenguaje visual que la app: un widget pequeño de CPU con matriz de carga por núcleo, otro de GPU con gauge y modelo, y uno mediano de memoria con barras de RAM y VRAM por placa. La pantalla bloqueada adapta la matriz y el gauge a accesorios compactos. Cada vista lleva la fecha de la muestra; las cifras guardadas no se presentan como una medición actual. El toque abre el detalle del equipo o de sus núcleos en la app.

## CPU, RAM, GPU y VRAM

Revisión visual solicitada: los primeros mockups tenían teléfonos demasiado largos, texto pequeño, exceso de espacio al final del inventario y controles con densidad irregular. Se rehacen las pantallas con un marco fijo de 790 px, desplazamiento nativo del contenido, datos principales visibles antes del pliegue, módulos de RAM y núcleos identificables, y widgets de bloqueo en tamaños de accesorio. La nueva dirección conserva la identidad instrumental y separa la lectura rápida del inventario detallado.

Nueva preferencia del usuario: priorizar barras y gauges sobre grandes números y porcentajes, y usar la matriz de núcleos como un heatmap. La vista de uso presenta una celda por núcleo, un gauge de GPU, y barras de RAM/VRAM con las capacidades en texto secundario. El total de CPU, temperatura y potencia quedan detrás de “Ver valores detallados”. El modelo y las cantidades de hardware siguen disponibles. Al tocar la matriz se abre una hoja con núcleos identificados y el valor exacto de la celda seleccionada.

El heatmap indica utilización, no temperatura. Usa una escala fija 0–100% con intervalos 0–9, 10–29, 30–59, 60–84 y 85–100, de neutro/verde a ámbar y naranja. Las etiquetas accesibles y el detalle por núcleo permiten leer los valores sin depender sólo del color. Cero de carga es un valor válido; una muestra ausente o desactualizada se marca como tal, con patrón neutro, y no se pinta como 0%. En widgets se conserva la escala de la app y se representa la última muestra, sin animación que sugiera datos en vivo.

Se solicita mostrar las métricas directamente en la app, junto con nombres de hardware y cantidades. La dirección visual propuesta es instrumental: superficies de grafito, tipografía del sistema, cifras con alineación tabular y una única traza verde menta para el uso de GPU. La información de la placa elegida es el elemento principal; CPU y memoria quedan en una fila compacta. Un inventario separado muestra modelos, núcleos/hilos, módulos de RAM y cantidad de GPU sin sobrecargar la vista de uso. Dirección y procesos de diseño informados por unslop, Damir Sokolovsky, CC BY 4.0.

Los datos del prototipo son ficticios, no una detección del hardware de la flota. Los ejemplos incluyen AMD Ryzen 9 9950X (16 núcleos/32 hilos), 128 GiB de RAM (4 × 32 GiB DDR5-5600) y 2 × NVIDIA GeForce RTX 5090 de 32 GiB GDDR7 cada una; otro equipo tiene Core i9-13900K y RTX 4090 de 24 GiB; un Mac tiene M4 Pro de 12 núcleos CPU/16 GPU y 64 GiB de memoria unificada.

El backend requiere recolectar métricas en cada equipo. El estado VPN o una comprobación TCP por sí solos no informan uso de hardware. Para una primera versión propongo colectores de lectura por SSH, con conexiones reutilizadas, comandos fijos y tiempo máximo por consulta. Un agente persistente por equipo es una alternativa posterior si la cantidad de máquinas o la frecuencia justifican instalarlo; no es un requisito de estos mockups.

- **Linux CPU:** diferencias de contadores de `/proc/stat` entre muestras, normalizadas al rango 0–100% para el equipo completo y para cada procesador lógico. Inventario/topología mediante `lscpu`/sysfs, con campos faltantes explícitos. Se identifica socket, núcleo físico y sus procesadores lógicos para construir el heatmap.
- **Linux RAM:** total y disponible de `/proc/meminfo`; uso definido como total menos disponible. Velocidad y cantidad física de módulos sólo se muestran cuando una fuente del sistema las informa con los permisos disponibles. No se deducen a partir de la capacidad total.
- **NVIDIA:** `nvidia-smi` para nombre, UUID/identificador, uso, memoria total/usada, temperatura y potencia, cuando el driver lo admite. Se conserva cada GPU por UUID y no por un índice que pueda cambiar tras reiniciar.
- **AMD/Intel:** adaptadores específicos usando herramientas del driver o sysfs según disponibilidad. Cada métrica comunica si está soportada; una falta de soporte no se convierte en 0%.
- **macOS:** CPU y memoria mediante APIs del sistema o un helper remoto. En Apple Silicon se muestra memoria unificada, sin sumar una supuesta VRAM dedicada. La utilización GPU requiere una fuente compatible con esa versión/hardware; `powermetrics`, por ejemplo, puede necesitar privilegios. La primera versión permite mostrar “uso no informado” y no solicita elevación automáticamente.

Cada muestra incluye `host_id`, `collected_at`, estado de recolección y campos opcionales; inventario y métricas tienen fechas independientes. CPU se expresa en porcentaje; memoria se transmite en bytes y se presenta en GiB, y potencia/temperatura en W/°C. Se identifica la definición de memoria usada de cada plataforma para no comparar fórmulas incompatibles. No se mezclan porcentajes de recursos distintos ni se acumula VRAM de varias placas como si fuera un único bloque asignable.

La muestra de CPU agrega `sample_window_ms`, total y una lista de núcleos con identificador estable de socket/núcleo, `logical_cpu_ids`, utilización y estado de disponibilidad. Si hay SMT, la celda física representa la media de sus procesadores lógicos para la misma ventana; el total del equipo pondera todos los procesadores lógicos, teniendo en cuenta que los núcleos pueden tener distinta cantidad de hilos. Si la topología no se conoce, se muestran procesadores lógicos con esa etiqueta explícita. Un core offline o sin muestra conserva su posición y se marca sin datos. El MCP expone estos mismos valores por núcleo mediante las herramientas de métricas. El ejemplo de 16 núcleos del prototipo tiene una media de 34%, e incluye un core en 0% y otro en 92%.

Propuesta de frecuencia: cada 5 segundos para el detalle visible, cada 15 segundos para el resto; la viabilidad y carga se miden antes de fijar los valores. La gráfica muestra muestras reales con sus tiempos y huecos cuando falta información. El prototipo usa una serie de ejemplo de 15 minutos. Si una muestra envejece, se marca como guardada/sin verificar y se impide que parezca una lectura actual. Una GPU no soportada y una GPU con 0% de uso son estados distintos.

## MCP: lectura de datos y código, más vinculación T3

El usuario solicita un servidor MCP en el backend para leer todos los datos y código configurados y, posteriormente, generar enlaces o QR de vinculación T3. Se agrega una interfaz MCP con el SDK de Python, publicada mediante Streamable HTTP en `/mcp`, con HTTPS y acceso por las mismas rutas VPN del servicio. La API de la app y MCP comparten la capa de inventario, métricas e historial: no se mantienen dos fuentes de verdad.

Herramientas propuestas de lectura: `list_hosts`, `get_host`, `get_hardware`, `get_metrics`, `get_metrics_history`, `get_events`, `get_source_status` y `get_configuration` sin credenciales. Cada resultado incluye fecha, origen y estado de frescura; la historia tiene límites, paginación y rango temporal. Leer no dispara conexiones privilegiadas ni acciones de T3.

Para código: `list_repositories`, `list_directory`, `read_file`, `search_code`, `get_repository_status` y `get_diff`. Incluye el propio repositorio del backend y repositorios configurados en los equipos. Los resultados indican equipo, repositorio, ruta relativa, revisión/worktree observado y números de línea. Se pueden exponer recursos MCP con contenido textual y metadatos, manteniendo límites por archivo y paginación. El servicio debe acceder por la VPN a cada equipo y tener permiso de lectura de sus repositorios; SSH config/VPN no otorgan ese permiso automáticamente.

Los clientes MCP tienen credenciales propias revocables, autorización por equipo/repositorio y permisos de lectura. Los clientes habilitados para generar vínculos T3 reciben además el permiso específico `t3:pair`. Las raíces autorizadas se resuelven antes de leer; se controla traversal y escape mediante symlinks. Las claves privadas, tokens de VPN/T3, archivos de secretos y credenciales del backend quedan fuera del catálogo y de las búsquedas. El código es contenido no confiable para el cliente: un comentario o README no concede permisos de ejecución.

Las herramientas de datos y código conservan su carácter de lectura. Las consultas de código remoto usan operaciones predefinidas con argumentos validados y límites de tiempo/salida. Con un equipo inaccesible se indica el error o la antigüedad de una copia indexada; no se presenta el índice como el worktree actual. Índices de búsqueda y copias de código permanecen dentro de la infraestructura privada del usuario. La generación T3 es la única operación adicional autorizada en este diseño; no habilita escritura de código, terminal ni ejecución de comandos arbitrarios por MCP.

### Enlace y QR T3 por MCP

Herramienta propuesta: `create_t3_pairing(host_id, output)`; `output` admite `link`, `qr` o `both`. Genera un vínculo nuevo en el equipo seleccionado usando el comando fijo y validado de T3 por SSH. El cliente requiere `t3:pair` y acceso a ese equipo. Los parámetros no aceptan un shell, una URL de destino arbitraria ni comandos del solicitante.

Devuelve el identificador/nombre del equipo, fecha de emisión, expiración y, según el formato pedido, el enlace HTTPS y/o el QR como contenido de imagen MCP `image/png`. El QR codifica exactamente el mismo enlace: no crea otro tipo de acceso. La imagen y el resultado se construyen en memoria; no se guardan en archivos, historial del servidor, logs ni herramientas de lectura. Se emplean respuestas sin caché. Los mockups usan un QR de ejemplo que apunta a `example.com`, sin ninguna credencial real.

La herramienta se declara con `readOnlyHint: false` e `idempotentHint: false`: emitir una credencial tiene efectos y cada llamada crea una nueva. Esas anotaciones describen el comportamiento; la autorización se comprueba en el servidor. Consultar inventario o leer código nunca genera un pairing como efecto secundario. La vigencia inicial conserva la hora que solicita el comando actual; un plazo menor queda sujeto al soporte verificado de T3.

Al devolver el enlace o QR por MCP, el resultado llega al cliente/agent y puede quedar en su historial, trazas o conversación. Blussh controla la retención de su propio servidor, pero no garantiza que el cliente mantenga la credencial sólo en memoria. El usuario debe conocer ese límite al habilitar `t3:pair` para un cliente. El vínculo permite vincularse mientras sea válido; no se presume uso único ni revocación individual.

## Seguridad de T3

El código/enlace de pairing es una credencial sensible. En el código actual, `T3.pairScript` ejecuta `t3 pair --tailscale --ttl 1h`; no hay evidencia suficiente para afirmar que el código sea de un solo uso o que pueda revocarse individualmente. No se promete ninguna de esas propiedades.

Para vincular este iPhone, se puede escanear el QR ya generado por blussh de escritorio. Para emitir un vínculo desde iPhone o un cliente MCP autorizado, el servicio necesita una operación autenticada específica: verifica permiso sobre el equipo, ejecuta el comando fijo mediante SSH y devuelve el enlace o su QR por HTTPS. No acepta comandos arbitrarios ni destinos SSH proporcionados sin validar. Se conserva el comportamiento existente de reescritura del host al nombre MagicDNS cuando corresponda.

En la app de Bleet, el enlace vive sólo en memoria y se descarta al cerrar su vista o salir de primer plano. En el servidor no entra en logs, trazas HTTP, analítica, caché, eventos, UserDefaults ni notificaciones; la respuesta usa Cache-Control: no-store. No se copia automáticamente. Si el usuario decide copiarlo, se usa un elemento local de UIPasteboard con fecha de expiración, explicando que otras apps con acceso al portapapeles podrían capturarlo. Abrirlo en un navegador o devolverlo por MCP transfiere la credencial a ese cliente, cuya retención es independiente; se evitan redirecciones a terceros y carga de recursos externos en el flujo controlado por Bleet. También deben excluirse cuerpos y URLs sensibles de los logs del proxy.

La VPN limita exposición, pero no sustituye autenticación ni autorización. El alta en Bleet usa un token de inscripción de corta duración y un solo uso, canjeado por una credencial de dispositivo revocable, almacenada en Keychain. Esto es una capacidad a implementar en bleetd, distinta de las garantías del pairing de T3. Separar permisos de lectura, configuración y emisión T3; sólo el último autoriza esa operación. Las claves del servicio y el token de ZeroTier Central quedan en la máquina que ya los usa. El servicio es un punto sensible: comprometerlo o robar una credencial de emisión podría permitir generar nuevos vínculos T3.

## Segundo plano y alertas

El servicio sigue comprobando cuando el teléfono duerme. iOS no permite ejecutar un timer de monitoreo de 10 segundos continuamente en segundo plano. Sin infraestructura adicional, el historial se consulta al volver a la app y los widgets se actualizan de manera oportunista. Avisos remotos inmediatos requieren APNs, sus credenciales y conectividad con Apple; no se presentan como una función garantizada de una solución exclusivamente local.

## Implementación por etapas

Primero: servicio privado autenticado, inventario, estados, detalle, copia SSH, vinculación del teléfono y estados sin acceso. Después: colectores de CPU/RAM/GPU, inventario de hardware y MCP para lectura de datos/código y generación de vínculos T3 con permiso específico. Luego: widgets de recursos, terminal SSH y operación T3 con permisos independientes. Finalmente: historial persistente y, si se desea, push. El MCP sólo ofrece rangos históricos cuando esa persistencia ya esté implementada; hasta entonces se informa que no hay historia disponible. Los mockups muestran la dirección completa propuesta, no una afirmación de funcionalidad disponible.
