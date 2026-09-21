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
   audio_minutes: 6
   greeting: "A quién saluda el noticiero"
   ---
   (cuerpo: secciones con ##, ítems con ###, URL sueltas en su propia línea)

   ## Texto para WhatsApp
   (bloque literal listo para pegar)
   ```
   No incluir la línea "Versión en audio…" ni saludos al Dr. Castillo: la página es pública.
3. Copiar el MP3 del noticiero a `audio/<especialidad>-<AAAA-MM-DD>.mp3` (mismo nombre de fecha).
4. `pip install markdown && python3 build.py` → regenera `docs/`.
5. `git add -A && git commit -m "Boletín <especialidad> <fecha>" && git push`.
   GitHub Pages publica `docs/` en 1–2 minutos.

El enlace del número queda en `https://julioecastillomercedes-design.github.io/boletines/<especialidad>/<AAAA-MM-DD>.html`
y el del audio en `https://julioecastillomercedes-design.github.io/boletines/audio/<especialidad>-<AAAA-MM-DD>.mp3`.
Incluir ambos enlaces en el correo y en el bloque de WhatsApp.

Para añadir una especialidad nueva: agregar su entrada en `config.json` (clave, nombre, cadencia, público, blurb, hue) y crear la carpeta `issues/<clave>/`.
