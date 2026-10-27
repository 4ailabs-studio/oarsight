"""Coding scheme for clinician behaviors and patient language.

The categories follow the behavior types described in the MITI 4.2.1 (Motivational Interviewing Treatment Integrity).
All definitions and examples here are written in our own words; no text from the manual is reproduced. Examples are
invented, in Mexican Spanish, and the "not this" examples target errors we observed in early tests, where models
were too lenient and labeled the clinician's intentions or generic praise as MI-consistent behaviors.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Code:
    name: str
    definition: str
    examples: tuple[str, ...] = ()
    not_this: tuple[tuple[str, str], ...] = field(default=())  # (example, what it is instead)


CLINICIAN_CODES: tuple[Code, ...] = (
    Code(
        "QUESTION",
        "Any question that asks for information, the patient's view, or their story. Open and closed questions "
        "share this code.",
        ("¿Qué hace que se le olvide la pastilla?", "¿Desde cuándo se siente así?"),
        (("¿No cree que ya es hora de cuidarse?", "PERSUADE: a question used to push an opinion"),
         ("¿Quiere quedarse ciego también?", "CONFRONT")),
    ),
    Code(
        "SIMPLE_REFLECTION",
        "A statement that gives back what the patient just said, with little or no added meaning.",
        ("[Paciente: se me olvida la pastilla] Se le olvida tomarla.",),
        (("¿Se le olvida?", "QUESTION: said as a question, not a statement"),),
    ),
    Code(
        "COMPLEX_REFLECTION",
        "A statement about something the patient said that adds meaning: names an unspoken feeling or value, links "
        "ideas, or reflects both sides of their ambivalence. It must build on what the patient actually said.",
        (("[Paciente: quiero estar bien para mi nieta, pero termino cansado] Su nieta le importa mucho, y a la vez el "
          "trabajo lo deja sin energía para cambiar."),
         "[Paciente: si me regaña, me cierro] Necesita sentirse escuchado, no juzgado, para poder hablar de esto."),
        (("Eso le pasa porque no se cuida.", "CONFRONT: adds the clinician's judgment, not the patient's meaning"),),
    ),
    Code(
        "AFFIRM",
        "Genuine recognition of a specific strength, effort, or value of the patient.",
        ("Vino hoy aunque le cuesta trabajo salir del taller; eso muestra que le importa su salud.",),
        (("Muy bien.", "NO_CODE: generic praise"), ("Ok, gracias.", "NO_CODE")),
    ),
    Code(
        "SEEK_COLLABORATION",
        "Explicitly invites the patient to decide or build something together, asks for their ideas, or asks "
        "permission before informing or advising.",
        ("¿Qué le parece si lo revisamos juntos?", "¿Le puedo contar lo que sabemos sobre la insulina?"),
        (("Yo te voy a escuchar.", "NO_CODE: a statement of the clinician's intention, not an invitation"),
         ("Mi propósito es que salgas adelante.", "NO_CODE")),
    ),
    Code(
        "EMPHASIZE_AUTONOMY",
        "Explicitly says that the choice, control, or decision belongs to the patient.",
        ("Usted decide si quiere intentarlo.", "Usted conoce mejor que nadie lo que le funciona."),
        (("Te puedo dar ejemplos e ideas.", "NO_CODE: an offer of help, not a statement about the patient's choice"),),
    ),
    Code(
        "GIVE_INFORMATION",
        "Neutral information, explanation, or results, without pressure to change.",
        ("La hemoglobina glucosilada mide el promedio de azúcar de los últimos tres meses.",),
        (("Tiene que bajar esa cifra.", "PERSUADE"),),
    ),
    Code(
        "PERSUADE",
        "Tries to change the patient's opinion or behavior with advice, arguments, warnings, or 'you must', "
        "without asking permission first.",
        ("Tiene que tomarse la metformina diario.", "Es importante que me escuches."),
    ),
    Code(
        "PERSUADE_WITH_PERMISSION",
        "Advice or arguments given after the patient agreed to hear them, or framed with an explicit choice.",
        ("Ya que me lo permite: a muchas personas les ayuda tomarla con el desayuno. Usted ve si le sirve.",),
    ),
    Code(
        "CONFRONT",
        "Argues, corrects with authority, judges, blames, shames, threatens, or labels the patient.",
        ("Eso no fue por la insulina, fue porque no se cuidó.", "¿Quiere quedarse ciego también?"),
    ),
    Code(
        "NO_CODE",
        "Fillers, greetings, thanks, procedural instructions, fragments, and statements of the clinician's own "
        "intentions that do not invite the patient to do anything.",
        ("Ok.", "Vamos a pasar a la camilla.", "Bueno."),
    ),
)

PATIENT_CODES: tuple[Code, ...] = (
    Code(
        "CHANGE",
        "Language in favor of changing a health behavior: desire, ability, reasons, need, commitment, or steps taken.",
        ("Quiero estar bien para mi nieta.", "Si me lo explican paso a paso, sí me animo."),
    ),
    Code(
        "SUSTAIN",
        "Language in favor of keeping things as they are or against the change or treatment.",
        ("Insulina no, doctor.", "Me cuesta un montón cambiar lo que ya hago.", "Hoy me siento bien, no pasa nada si no me la tomo."),
    ),
    Code(
        "NEUTRAL",
        "Anything else: information, questions, small talk.",
        ("Trabajo en un taller.",),
    ),
)

CLINICIAN_CODE_NAMES = tuple(c.name for c in CLINICIAN_CODES)
PATIENT_CODE_NAMES = tuple(c.name for c in PATIENT_CODES)
REFLECTIONS = frozenset({"SIMPLE_REFLECTION", "COMPLEX_REFLECTION"})
MI_ADHERENT = frozenset({"AFFIRM", "SEEK_COLLABORATION", "EMPHASIZE_AUTONOMY"})
MI_NON_ADHERENT = frozenset({"PERSUADE", "CONFRONT"})


def render(codes: tuple[Code, ...]) -> str:
    """Render codes as plain text for prompts (stable order, so prompt prefixes can be cached)."""
    blocks = []
    for code in codes:
        lines = [f"{code.name}: {code.definition}"]
        lines += [f"  Example: {e}" for e in code.examples]
        lines += [f"  Not this: {e} -> {instead}" for e, instead in code.not_this]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_markdown() -> str:
    """Human-readable codebook for docs/CODEBOOK.md."""
    intro = ("Generated from `src/oarsight/codebook.py`. Categories follow the behavior types of the MITI 4.2.1; "
             "all definitions and examples are written in our own words.")
    out = ["# Codebook", "", intro, ""]
    for title, codes in (("Clinician behaviors", CLINICIAN_CODES), ("Patient language", PATIENT_CODES)):
        out += [f"## {title}", ""]
        for code in codes:
            out += [f"### `{code.name}`", "", code.definition, ""]
            out += [f"- Example: {e}" for e in code.examples]
            out += [f"- Not this: {e} → {instead}" for e, instead in code.not_this]
            out.append("")
    return "\n".join(out)
