# Codebook

Generated from `src/oarsight/codebook.py`. Categories follow the behavior types of the MITI 4.2.1; all definitions and examples are written in our own words.

## Clinician behaviors

### `QUESTION`

Any question that asks for information, the patient's view, or their story. Open and closed questions share this code.

- Example: ¿Qué hace que se le olvide la pastilla?
- Example: ¿Desde cuándo se siente así?
- Not this: ¿No cree que ya es hora de cuidarse? → PERSUADE: a question used to push an opinion
- Not this: ¿Quiere quedarse ciego también? → CONFRONT

### `SIMPLE_REFLECTION`

A statement that gives back what the patient just said, with little or no added meaning.

- Example: [Paciente: se me olvida la pastilla] Se le olvida tomarla.
- Not this: ¿Se le olvida? → QUESTION: said as a question, not a statement

### `COMPLEX_REFLECTION`

A statement about something the patient said that adds meaning: names an unspoken feeling or value, links ideas, or reflects both sides of their ambivalence. It must build on what the patient actually said.

- Example: [Paciente: quiero estar bien para mi nieta, pero termino cansado] Su nieta le importa mucho, y a la vez el trabajo lo deja sin energía para cambiar.
- Example: [Paciente: si me regaña, me cierro] Necesita sentirse escuchado, no juzgado, para poder hablar de esto.
- Not this: Eso le pasa porque no se cuida. → CONFRONT: adds the clinician's judgment, not the patient's meaning

### `AFFIRM`

Genuine recognition of a specific strength, effort, or value of the patient.

- Example: Vino hoy aunque le cuesta trabajo salir del taller; eso muestra que le importa su salud.
- Not this: Muy bien. → NO_CODE: generic praise
- Not this: Ok, gracias. → NO_CODE

### `SEEK_COLLABORATION`

Explicitly invites the patient to decide or build something together, asks for their ideas, or asks permission before informing or advising.

- Example: ¿Qué le parece si lo revisamos juntos?
- Example: ¿Le puedo contar lo que sabemos sobre la insulina?
- Not this: Yo te voy a escuchar. → NO_CODE: a statement of the clinician's intention, not an invitation
- Not this: Mi propósito es que salgas adelante. → NO_CODE

### `EMPHASIZE_AUTONOMY`

Explicitly says that the choice, control, or decision belongs to the patient.

- Example: Usted decide si quiere intentarlo.
- Example: Usted conoce mejor que nadie lo que le funciona.
- Not this: Te puedo dar ejemplos e ideas. → NO_CODE: an offer of help, not a statement about the patient's choice

### `GIVE_INFORMATION`

Neutral information, explanation, or results, without pressure to change.

- Example: La hemoglobina glucosilada mide el promedio de azúcar de los últimos tres meses.
- Not this: Tiene que bajar esa cifra. → PERSUADE

### `PERSUADE`

Tries to change the patient's opinion or behavior with advice, arguments, warnings, or 'you must', without asking permission first.

- Example: Tiene que tomarse la metformina diario.
- Example: Es importante que me escuches.

### `PERSUADE_WITH_PERMISSION`

Advice or arguments given after the patient agreed to hear them, or framed with an explicit choice.

- Example: Ya que me lo permite: a muchas personas les ayuda tomarla con el desayuno. Usted ve si le sirve.

### `CONFRONT`

Argues, corrects with authority, judges, blames, shames, threatens, or labels the patient.

- Example: Eso no fue por la insulina, fue porque no se cuidó.
- Example: ¿Quiere quedarse ciego también?

### `NO_CODE`

Fillers, greetings, thanks, procedural instructions, fragments, and statements of the clinician's own intentions that do not invite the patient to do anything.

- Example: Ok.
- Example: Vamos a pasar a la camilla.
- Example: Bueno.

## Patient language

### `CHANGE`

Language in favor of changing a health behavior: desire, ability, reasons, need, commitment, or steps taken.

- Example: Quiero estar bien para mi nieta.
- Example: Si me lo explican paso a paso, sí me animo.

### `SUSTAIN`

Language in favor of keeping things as they are or against the change or treatment.

- Example: Insulina no, doctor.
- Example: Me cuesta un montón cambiar lo que ya hago.
- Example: Hoy me siento bien, no pasa nada si no me la tomo.

### `NEUTRAL`

Anything else: information, questions, small talk.

- Example: Trabajo en un taller.

