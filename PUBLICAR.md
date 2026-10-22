# Cómo publicar un número nuevo en el portal

Este repositorio genera el portal de boletines (GitHub Pages). Para añadir un número:

1. Clonar el repositorio (con token de escritura):
   `git clone https://TOKEN@github.com/julioecastillomercedes-design/boletines.git && cd boletines`
2. Crear `issues/<especialidad>/<AAAA-MM-DD>.md` con este encabezado y el cuerpo del boletín en markdown:
   ```
   ---
   specialty: vascular | cirugia-general | ginecologia | pediatria | cardiologia
   date: AAAA-MM-DD
   title: "Boletín ... — D de mes de AAAA"
   audio_minutes: 6   # opcional: la duración que se muestra se mide del MP3
   greeting: "A quién saluda el noticiero"
   ---
   (cuerpo: secciones con ##, ítems con ###, URL sueltas en su propia línea)

   ## Texto para WhatsApp
   (bloque literal listo para pegar)
   ```
   No incluir la línea "Versión en audio…" ni saludos al Dr. Castillo: la página es pública.
3. Copiar el MP3 del noticiero a `audio/<especialidad>-<AAAA-MM-DD>.mp3` (mismo nombre de fecha).
   Versión en inglés (opcional): `issues/<especialidad>/<AAAA-MM-DD>.en.md` con el mismo formato (títulos en inglés,
   secciones finales `## Text for LinkedIn` y `## Text for X`) y audio `audio/<especialidad>-<AAAA-MM-DD>-en.mp3`.
   Los bloques `## Texto para LinkedIn` y `## Texto para X` al final del .md en español se convierten en botones de copiar.
4. `pip install markdown && python3 build.py` → regenera `docs/`.
5. `git add -A && git commit -m "Boletín <especialidad> <fecha>" && git push`.
   GitHub Pages publica `docs/` en 1–2 minutos.

La edición en inglés queda en `https://boletinesmedicos.com/en/<especialidad>/<AAAA-MM-DD>.html`.
El enlace del número queda en `https://boletinesmedicos.com/<especialidad>/<AAAA-MM-DD>.html`
y el del audio en `https://boletinesmedicos.com/audio/<especialidad>-<AAAA-MM-DD>.mp3`.
Incluir ambos enlaces en el correo y en el bloque de WhatsApp.

Para añadir una especialidad nueva: agregar su entrada en `config.json` (clave, nombre, cadencia, público, blurb, hue) y crear la carpeta `issues/<clave>/`.

Direcciones de la edición inglesa: cada especialidad tiene su `slug_en` en `config.json` (p. ej. `pediatria` → `/en/pediatrics/`).
Los archivos se siguen nombrando con la clave en español (`issues/pediatria/...en.md`); `build.py` genera la dirección inglesa
y deja redirecciones desde las antiguas (`/en/pediatria/...`). En los textos .en.md, enlazar con la dirección inglesa.

## Correcciones verificadas desde Drive

Cada nueva revisión verificada debe entregar en `Portal boletines/pendientes` los cuatro
archivos con el mismo sello UTC, tomado al terminar la revisión. Por ejemplo:

```
endocrinologia-2026-10-10.r20261022T030000Z.v.md
endocrinologia-2026-10-10.en.r20261022T030000Z.v.md
endocrinologia-2026-10-10.r20261022T030000Z.v.guion.txt
endocrinologia-2026-10-10.en.r20261022T030000Z.v.guion.txt
```

Para «Lo que viene», añadir `-viene` después de la fecha del número. No cambiar el
contenido de un sello ya publicado: una corrección posterior necesita un sello nuevo.
Los cuatro archivos deben terminar de subirse antes de la siguiente ejecución del
publicador. Una revisión incompleta detiene la ejecución, conserva lo publicado y se
reintentará en la siguiente ejecución cuando esté completa.

El publicador enumera Drive y descarga cada ID por separado; dos nombres iguales no
se sobrescriben durante la descarga. Elige el sello más reciente y rechaza archivos
contradictorios del mismo sello. Guarda la revisión y las huellas de su contenido en
`issues/.revisiones.json`, ignora revisiones anteriores y no vuelve a grabar audios si
el guion no cambió. Si cambia un guion, genera el MP3 en un temporal antes de sustituir
texto, guion y audio. Si falla una descarga, una validación o la síntesis, la ejecución
falla antes de publicar cambios.

Los archivos antiguos sin sello `.r...` se admiten para números nuevos o cuando
coinciden con lo ya publicado. Si difieren de un archivo existente, la ejecución falla
con el mensaje «Corrección sin sello de revisión»; el editor debe entregar una revisión
completa con sello nuevo. No se toma la fecha de descarga como prueba de que un contenido
sea más reciente.

Prueba local sin red ni síntesis real:
`python -m unittest discover -s tests -p test_importar_drive.py`.

Para descargar y después importar:
`python tools/importar_drive.py entrada --descargar` y
`python tools/importar_drive.py entrada`.

La tarea del verificador debe usar este convenio para sus futuras correcciones. Cambiar
su instrucción persistente se gestiona por separado de este repositorio.
