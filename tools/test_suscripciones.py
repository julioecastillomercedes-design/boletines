#!/usr/bin/env python3
"""Pruebas de tools/suscripciones.py con datos sintéticos (dominio example.invalid, que no existe).
Uso: python3 tools/test_suscripciones.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import suscripciones as S  # noqa: E402

NUMS = [
    {"id": "cardiologia/2026-10-20.es", "spec": "cardiologia", "lang": "es", "date": "2026-10-20",
     "title": "Boletín de cardiología — 20 de octubre de 2026", "summary": "Resumen.", "url": "u1", "audio": "a1"},
    {"id": "cardiologia/2026-10-20.en", "spec": "cardiologia", "lang": "en", "date": "2026-10-20",
     "title": "Monthly cardiology bulletin — October 20, 2026", "summary": "Summary.", "url": "u2", "audio": "a2"},
    {"id": "pediatria/2026-10-21.es", "spec": "pediatria", "lang": "es", "date": "2026-10-21",
     "title": "Boletín de pediatría — 21 de octubre de 2026", "summary": "Resumen.", "url": "u3", "audio": ""},
    {"id": "vascular/2026-10-01.es", "spec": "vascular", "lang": "es", "date": "2026-10-01",
     "title": "Boletín vascular — 1 de octubre", "summary": "Antiguo.", "url": "u4", "audio": ""},
]
CFG_ON = {"distribucion_activa": True, "max_correos_por_ejecucion": 100, "inicio_distribucion": "2026-10-15"}
fallos = []


def check(cond, txt):
    print(("OK   " if cond else "FALLA") + " " + txt)
    if not cond:
        fallos.append(txt)


def ejecutar(reg, sol, hoy, cfg, nums=NUMS):
    sal = Path(tempfile.mkdtemp())
    (reg / "config.json").write_text(json.dumps(cfg))
    r, out = S.procesar(reg, sol, hoy, sal, nums, cfg)
    return sal, r, out


def avanzar(sal, out, hoy):
    """Simula que todos los salientes se enviaron con éxito y devuelve el registro resultante."""
    S.cerrar(sal, [dict(o, mensaje_id=f"g-{i}") for i, o in enumerate(out)], hoy)
    return sal


reg = Path(tempfile.mkdtemp())
alta_es = {"id": "m1", "date": "2026-10-15T10:00", "from": "Ana Prueba <ana@example.invalid>",
           "subject": "Suscripción a Boletines Médicos",
           "body": "Hola. Quiero recibir por correo los boletines de estas especialidades:\n- Cardiología\n- Pediatría\n\nNombre: Ana\nCiudad o institución (opcional): Santiago"}
alta_en = {"id": "m2", "date": "2026-10-15T10:05", "from": "bob@example.invalid",
           "subject": "Subscription to MedBulletins",
           "body": "Hello. I would like to receive the bulletins for these specialties by email:\n- Cardiology\n\nName: Bob\nCity or institution (optional): "}
alta_todas = {"id": "m3", "date": "2026-10-15T10:06", "from": "CARLA@Example.Invalid",
              "subject": "Suscripción a Boletines Médicos",
              "body": "Quiero recibir por correo los boletines de estas especialidades (borre las que no le interesen):\n" +
                      "\n".join(f"- {S.CFG['specialties'][k]['name']}" for k in S.CLAVES) + "\n\nNombre:\n"}
sin_especs = {"id": "m4", "date": "2026-10-15T10:07", "from": "dora@example.invalid",
              "subject": "Suscripción a Boletines Médicos", "body": "Hola. Quiero suscribirme.\n\nNombre: Dora"}
ruido = {"id": "m5", "date": "2026-10-15T10:08", "from": "tienda@example.invalid",
         "subject": "Ofertas de la semana", "body": "Unsubscribe preferences at the bottom"}

# 1) Altas, idioma, especialidades, normalización de correo, solicitud ambigua y ruido
sal, r, out = ejecutar(reg, [alta_es, alta_en, alta_todas, sin_especs, ruido], "2026-10-15", CFG_ON)
subs = {s["email"]: s for s in S.leer_csv(sal / "suscriptores.csv", S.SUB_COLS)}
check(sorted(r["altas"]) == ["ana@example.invalid", "bob@example.invalid", "carla@example.invalid"], "3 altas registradas (correo en minúsculas)")
check(subs["ana@example.invalid"]["especialidades"] == "cardiologia;pediatria" and subs["ana@example.invalid"]["idioma"] == "es", "Ana: cardiología+pediatría, español")
check(subs["bob@example.invalid"]["idioma"] == "en" and subs["bob@example.invalid"]["especialidades"] == "cardiologia", "Bob: cardiología, inglés")
check(subs["carla@example.invalid"]["especialidades"] == "todas", "Carla: todas (lista completa)")
check(subs["dora@example.invalid"]["estado"] == "revisar" and r["revisar"] == ["dora@example.invalid"], "Dora: sin especialidades -> revisar, sin alta automática")
check(r["ignorados"] == 1, "correo publicitario con 'Unsubscribe' no se toma como baja ni alta")
conf = [o for o in out if o["tipo"] == "confirmacion"]
check(sorted(o["to"] for o in conf) == ["ana@example.invalid", "bob@example.invalid", "carla@example.invalid"], "una confirmación por alta; ninguna para 'revisar'")
check(all(isinstance(o["to"], str) and "," not in o["to"] for o in out), "cada correo va a un único destinatario")
check(not [o for o in out if o["tipo"] == "numeros"], "sin números aún: el número vascular del 1-oct es anterior al alta y no se envía")
avanzar(sal, out, "2026-10-15")

# 2) Repetir la misma ejecución: nada se duplica
sal2, r2, out2 = ejecutar(sal, [alta_es, alta_en, alta_todas, sin_especs, ruido], "2026-10-15", CFG_ON)
check(r2["repetidos"] == 5 and not out2, "mismos correos otra vez: 0 cambios y 0 envíos (sin duplicados)")
# Segunda solicitud del mismo correo (mensaje nuevo): actualiza, no duplica fila
alta_es2 = dict(alta_es, id="m6", date="2026-10-16T09:00", body="- Pediatría\nNombre: Ana")
sal3, r3, out3 = ejecutar(sal2, [alta_es2], "2026-10-16", CFG_ON)
subs3 = S.leer_csv(sal3 / "suscriptores.csv", S.SUB_COLS)
check(sum(1 for s in subs3 if s["email"] == "ana@example.invalid") == 1 and r3["actualizadas"] == ["ana@example.invalid"], "solicitud repetida de Ana: actualiza su fila, no crea otra")
avanzar(sal3, out3, "2026-10-16")
# Ana vuelve a cardiología + pediatría
sal3b, _, out3b = ejecutar(sal3, [dict(alta_es, id="m6b", date="2026-10-16T10:00")], "2026-10-16", CFG_ON)
avanzar(sal3b, out3b, "2026-10-16")

# 3) Reparto por especialidad e idioma
sal4, r4, out4 = ejecutar(sal3b, [], "2026-10-21", CFG_ON)
por = {o["to"]: o for o in out4 if o["tipo"] == "numeros"}
check(set(por["ana@example.invalid"]["numeros"]) == {"cardiologia/2026-10-20.es", "pediatria/2026-10-21.es"}, "Ana (ES) recibe cardiología y pediatría en español, en un solo correo")
check(por["bob@example.invalid"]["numeros"] == ["cardiologia/2026-10-20.en"], "Bob (EN) recibe solo cardiología en inglés")
check(set(por["carla@example.invalid"]["numeros"]) == {"cardiologia/2026-10-20.es", "pediatria/2026-10-21.es"}, "Carla (todas, ES) recibe lo publicado en español desde su alta")
check("dora@example.invalid" not in por, "Dora (revisar) no recibe nada")
avanzar(sal4, out4, "2026-10-21")
sal5, r5, out5 = ejecutar(sal4, [], "2026-10-22", CFG_ON)
check(not out5, "día siguiente: ningún número se reenvía (sin duplicados)")

# 4) Bajas
baja_es = {"id": "m7", "date": "2026-10-22T08:00", "from": "Ana <ana@example.invalid>",
           "subject": "Re: Boletín de pediatría — 21 de octubre de 2026", "body": "Baja\n\n> texto citado"}
baja_en = {"id": "m8", "date": "2026-10-22T08:01", "from": "bob@example.invalid", "subject": "Unsubscribe", "body": ""}
baja_ajena = {"id": "m9", "date": "2026-10-22T08:02", "from": "nadie@example.invalid", "subject": "Baja", "body": "Baja"}
sal6, r6, out6 = ejecutar(sal5, [baja_es, baja_en, baja_ajena], "2026-10-22", CFG_ON)
subs6 = {s["email"]: s for s in S.leer_csv(sal6 / "suscriptores.csv", S.SUB_COLS)}
check(sorted(r6["bajas"]) == ["ana@example.invalid", "bob@example.invalid"], "bajas por 'Baja' (respuesta) y 'Unsubscribe' (asunto)")
check(subs6["ana@example.invalid"]["estado"] == "baja" and subs6["ana@example.invalid"]["fecha_baja"] == "2026-10-22", "la baja queda registrada con fecha")
check("nadie@example.invalid" not in subs6, "una baja de alguien no suscrito no crea registro")
nuevo = NUMS + [{"id": "cardiologia/2026-10-25.es", "spec": "cardiologia", "lang": "es", "date": "2026-10-25",
                 "title": "Boletín de cardiología — 25 de octubre", "summary": ".", "url": "u5", "audio": ""}]
sal7, r7, out7 = ejecutar(sal6, [], "2026-10-25", CFG_ON, nuevo)
check([o["to"] for o in out7] == ["carla@example.invalid"], "tras la baja, Ana ya no recibe; Carla sí")

# 5) Distribución desactivada: se registra todo pero no sale ningún correo
reg_off = Path(tempfile.mkdtemp())
sal8, r8, out8 = ejecutar(reg_off, [alta_es], "2026-10-15", {"distribucion_activa": False})
check(r8["altas"] == ["ana@example.invalid"] and out8 == [] and r8["retenidos"] == 1, "distribución desactivada: alta registrada, 0 correos, 1 retenido")

# 6) Tope de cuota por ejecución
reg_q = Path(tempfile.mkdtemp())
muchas = [dict(alta_en, id=f"q{i}", **{"from": f"u{i}@example.invalid"}) for i in range(12)]
sal9, r9, out9 = ejecutar(reg_q, muchas, "2026-10-15", dict(CFG_ON, max_correos_por_ejecucion=5))
check(len(out9) == 5 and r9["retenidos"] == 7, "tope de 5 correos por ejecución: 5 salen, 7 quedan para la siguiente")
avanzar(sal9, out9, "2026-10-15")
sal10, r10, out10 = ejecutar(sal9, [], "2026-10-16", dict(CFG_ON, max_correos_por_ejecucion=5))
check(len(out10) == 5 and not ({o["to"] for o in out10} & {o["to"] for o in out9}), "la siguiente ejecución sigue con los pendientes, sin repetir")

# 7) Cuenta propia: no se suscribe sola salvo prueba marcada
sal11, r11, _ = ejecutar(Path(tempfile.mkdtemp()), [dict(alta_es, id="p1", **{"from": "propia@example.invalid"})], "2026-10-15",
                         dict(CFG_ON, cuentas_propias=["propia@example.invalid"]))
check(r11["altas"] == [] and r11["ignorados"] == 1, "la cuenta propia no se suscribe por error")

# 8) Aislamiento del modo prueba
pr = {"id": "t1", "date": "2026-10-15T11:00", "from": "propia@example.invalid",
      "subject": "[PRUEBA] Suscripción a Boletines Médicos", "body": "- Cardiología\nNombre: Prueba"}
sal12, r12, _ = ejecutar(Path(tempfile.mkdtemp()), [pr, alta_en], "2026-10-15", dict(CFG_ON, cuentas_propias=["propia@example.invalid"]))
check(r12["altas"] == ["bob@example.invalid"], "modo real: el correo [PRUEBA] se ignora")
sal13 = Path(tempfile.mkdtemp())
r13, _ = S.procesar(Path(tempfile.mkdtemp()), [pr, alta_en], "2026-10-15", sal13, NUMS,
                    dict(CFG_ON, cuentas_propias=["propia@example.invalid"]), prueba=True)
check(r13["altas"] == ["propia@example.invalid"], "modo prueba: solo el correo [PRUEBA] cuenta (aunque sea la cuenta propia)")
out13 = json.loads((sal13 / "salientes.json").read_text())
check(out13 and all(o["to"] == "propia@example.invalid" and o["subject"].startswith("[PRUEBA]") for o in out13), "modo prueba: los correos salientes van solo a la cuenta propia y con [PRUEBA] en el asunto")
check(r12["hay_cambios"] and r12["mensajes_nuevos_procesados"] == 2, "el resumen indica si hay cambios que guardar")

print(f"\n{'TODAS LAS PRUEBAS PASAN' if not fallos else str(len(fallos)) + ' FALLOS'}")
sys.exit(1 if fallos else 0)
