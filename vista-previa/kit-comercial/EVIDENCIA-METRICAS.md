# Evidencia de métricas (16-oct-2026)

## Visitas al portal: aún no medidas
- build.py solo inserta el contador de GoatCounter si config.json tiene `analytics_goatcounter` (build.py, función con `CFG.get("analytics_goatcounter")`, líneas 463-466).
- config.json no tiene `analytics_goatcounter`, ni en esta rama ni en la copia local de main (`grep -c analytics_goatcounter config.json` → 0).
- Por tanto, las páginas generadas no cargan ningún contador.
- Límite de esta comprobación: la copia local de main es 1fee07b. Al último ls-remote, main estaba en 91ee710, y no pude volver a descargar main por el bloqueo de permisos. Hay que confirmar en main actual que la clave sigue sin definirse.

## Escuchas o descargas de audio: aún no medidas
- Los MP3 se sirven como archivos estáticos desde GitHub Pages (docs/audio/). GitHub Pages no ofrece estadísticas de descargas.
- El sitio no tiene ningún evento de reproducción instrumentado, porque no hay analítica activa.

## Suscriptores: registro de la tarea del 15-oct, no cifra auditada actual
- Fuente: descripción de la carpeta privada de Drive «registro» (id 1-ImGDpOlfKk0Og6f6ZQ6HJAPepcHSuXk), escrita por la tarea «Suscripciones de Boletines Médicos» (modificada 2026-10-15T18:16:10Z). Texto literal:
  «Última ejecución: 2026-10-15 14:16 (Santo Domingo). Resultado: OK. Mensajes nuevos procesados: 0. Altas: 0. Bajas: 0. Por revisar: 0. Activos: 0. Correos enviados: 0. Retenidos: 0. Distribución activa: sí. Registro guardado: no.»
- La tarea vuelve a ejecutarse a diario a las 14:13 de Santo Domingo; la cifra puede haber cambiado después. No abrí los CSV con datos personales.

## Especialidades públicas: 19
- config.json de main (copia local 1fee07b): 19 especialidades sin contar «Hitos»; la descripción dice «19 especialidades».
- Cirugía plástica (la 20.ª) existe solo en la rama preview-cirugia-plastica.
