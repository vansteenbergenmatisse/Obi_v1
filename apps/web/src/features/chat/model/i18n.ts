/**
 * i18n — the widget's own six-locale UI copy (PLAN 4.7.7).
 *
 * Scope: the widget's *own* static strings only (greeting, suggestion chip, composer
 * placeholder, footer disclaimer, teaser, "···" menu labels). It does NOT translate the RAG
 * agent's actual answers — those come back from `apps/automation` in whatever language the model
 * responded in, which is a separate, unscoped backend concern (see `docs/rag/OBI-WIDGET-DESIGN.md`
 * §5). Translations here are direct, unreviewed renderings of the already-resolved English copy —
 * the same quality bar the mockup's own six-locale table set, not a professionally localized
 * product string set.
 */

export const LOCALES = ["en", "nl", "de", "fr", "es", "it"] as const;
export type Locale = (typeof LOCALES)[number];

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  nl: "Nederlands",
  de: "Deutsch",
  fr: "Français",
  es: "Español",
  it: "Italiano",
};

export interface WidgetCopy {
  greetingPre: string;
  greetingPost: string;
  /** Empty-state example-query chips (PLAN 9.5) — the first stayed the assistant's own scope
   * ("what can you help me with"); the other two are honest for any client's Confluence content
   * (self-referential, not assuming specific document topics exist) and one doubles as a nudge
   * toward the specificity this phase's clarification branch is meant to reduce the need for. */
  suggestions: [string, string, string];
  /** Status-pill label for a `clarifying` turn (PLAN 9.5) — distinct from the refusal banner:
   * an open next step, not a failure. */
  clarifyingLabel: string;
  /** Human hand-off CTA lead-in shown under a `refused` turn (PLAN 9.6, ADR-0008 decision 6) —
   * the email address itself renders separately as a `mailto:` link, not interpolated into this
   * string, so word order stays natural per locale. Stub only: `test@gmail.com` is a placeholder
   * address, not a real support channel — see `docs/future-ideas/IDEAS.md` #1. */
  handoffCta: string;
  placeholder: string;
  footer: string;
  /** Persistent composer disclosure shown while an image is staged to send — discloses the C6
   * gap (image bytes are not PII-redacted, unlike message text) rather than hiding it. */
  imageDisclosure: string;
  /** Label introducing an assistant turn's vision-analysis block (ADR-0009 decision 5). */
  imageAnalysisLabel: string;
  /** Composer error shown when a chosen image exceeds the per-image byte cap (w-composer /
   * decision w-composer-images): the image is not attached and the person is told to compress it. */
  imageTooLarge: string;
  /** Composer error shown when more images are chosen than the per-turn cap allows (w-composer):
   * the extra images are not attached. */
  imageTooMany: string;
  teaser: string;
  docs: string;
  support: string;
  restart: string;
  more: string;
  language: string;
  screenshot: string;
  close: string;
  openAssistant: string;
}

const COPY: Record<Locale, WidgetCopy> = {
  en: {
    greetingPre: "Hi there, how can I help you with ",
    greetingPost: "? The more details you provide, the better.",
    suggestions: [
      "What can you help me with?",
      "What topics do you know about?",
      "How specific should my question be?",
    ],
    clarifyingLabel: "Need one more detail before I search",
    handoffCta: "Prefer a real person? Email us and we'll help.",
    placeholder: "Ask about your Confluence workspace…",
    footer: "AI may make mistakes. Verify important information.",
    imageDisclosure: "We don't check images for personal info. Skip sensitive screenshots.",
    imageAnalysisLabel: "Obi looked at your image",
    imageTooLarge: "Too large — compress your image and try again.",
    imageTooMany: "You've reached the image limit for this message.",
    teaser: "Hey, I'm Obi. Need help with onboarding or support?",
    docs: "Developer docs",
    support: "Support articles",
    restart: "Restart conversation",
    more: "More",
    language: "Language",
    screenshot: "Screenshot this page and ask Obi about it",
    close: "Close",
    openAssistant: "Open assistant",
  },
  nl: {
    greetingPre: "Hoi, waarmee kan ik je helpen met ",
    greetingPost: "? Hoe meer details je geeft, hoe beter.",
    suggestions: [
      "Waarmee kun je me helpen?",
      "Over welke onderwerpen weet je iets?",
      "Hoe specifiek moet mijn vraag zijn?",
    ],
    clarifyingLabel: "Ik heb nog één detail nodig voordat ik zoek",
    handoffCta: "Liever een echt persoon? Mail ons, dan helpen we je verder.",
    placeholder: "Stel een vraag over je Confluence-werkruimte…",
    footer: "AI kan fouten maken. Controleer belangrijke informatie.",
    imageDisclosure: "We checken afbeeldingen niet op persoonlijke info. Vermijd gevoelige screenshots.",
    imageAnalysisLabel: "Obi bekeek je afbeelding",
    imageTooLarge: "Te groot — verklein je afbeelding en probeer opnieuw.",
    imageTooMany: "Je hebt de limiet voor afbeeldingen in dit bericht bereikt.",
    teaser: "Hé, ik ben Obi. Hulp nodig bij onboarding of support?",
    docs: "Developer docs",
    support: "Supportartikelen",
    restart: "Gesprek opnieuw starten",
    more: "Meer",
    language: "Taal",
    screenshot: "Maak een screenshot van deze pagina en vraag het Obi",
    close: "Sluiten",
    openAssistant: "Assistent openen",
  },
  de: {
    greetingPre: "Hallo, wie kann ich dir mit ",
    greetingPost: " helfen? Je mehr Details du angibst, desto besser.",
    suggestions: [
      "Wobei kannst du mir helfen?",
      "Über welche Themen weißt du Bescheid?",
      "Wie genau sollte meine Frage sein?",
    ],
    clarifyingLabel: "Ich brauche noch ein Detail, bevor ich suche",
    handoffCta: "Lieber ein echter Mensch? Schreib uns, wir helfen dir weiter.",
    placeholder: "Stelle eine Frage zu deinem Confluence-Arbeitsbereich…",
    footer: "KI kann Fehler machen. Überprüfe wichtige Informationen.",
    imageDisclosure: "Wir prüfen Bilder nicht auf persönliche Daten. Vermeide sensible Screenshots.",
    imageAnalysisLabel: "Obi hat sich dein Bild angesehen",
    imageTooLarge: "Zu groß — komprimiere dein Bild und versuche es erneut.",
    imageTooMany: "Du hast das Bildlimit für diese Nachricht erreicht.",
    teaser: "Hey, ich bin Obi. Hilfe bei Onboarding oder Support?",
    docs: "Entwickler-Docs",
    support: "Support-Artikel",
    restart: "Unterhaltung neu starten",
    more: "Mehr",
    language: "Sprache",
    screenshot: "Screenshot dieser Seite aufnehmen und Obi fragen",
    close: "Schließen",
    openAssistant: "Assistenten öffnen",
  },
  fr: {
    greetingPre: "Bonjour, comment puis-je vous aider avec ",
    greetingPost: " ? Plus vous donnez de détails, mieux c’est.",
    suggestions: [
      "En quoi puis-je vous aider ?",
      "Sur quels sujets avez-vous des informations ?",
      "À quel point dois-je être précis dans ma question ?",
    ],
    clarifyingLabel: "J’ai besoin d’un détail avant de chercher",
    handoffCta: "Vous préférez une vraie personne ? Écrivez-nous, nous vous aiderons.",
    placeholder: "Posez une question sur votre espace Confluence…",
    footer: "L’IA peut faire des erreurs. Vérifiez les informations importantes.",
    imageDisclosure: "Nous ne vérifions pas les infos personnelles dans les images. Évitez les captures sensibles.",
    imageAnalysisLabel: "Obi a regardé votre image",
    imageTooLarge: "Trop volumineuse — compressez votre image et réessayez.",
    imageTooMany: "Vous avez atteint la limite d’images pour ce message.",
    teaser: "Bonjour, je suis Obi. Besoin d’aide pour l’onboarding ou le support ?",
    docs: "Docs développeur",
    support: "Articles d’aide",
    restart: "Redémarrer la conversation",
    more: "Plus",
    language: "Langue",
    screenshot: "Capturer cette page et demander à Obi",
    close: "Fermer",
    openAssistant: "Ouvrir l’assistant",
  },
  es: {
    greetingPre: "Hola, ¿en qué puedo ayudarte con ",
    greetingPost: "? Cuantos más detalles, mejor.",
    suggestions: [
      "¿En qué puedes ayudarme?",
      "¿Sobre qué temas tienes información?",
      "¿Qué tan específica debe ser mi pregunta?",
    ],
    clarifyingLabel: "Necesito un detalle más antes de buscar",
    handoffCta: "¿Prefieres una persona real? Escríbenos y te ayudamos.",
    placeholder: "Haz una pregunta sobre tu espacio de Confluence…",
    footer: "La IA puede cometer errores. Verifica la información importante.",
    imageDisclosure: "No revisamos las imágenes en busca de información personal. Evita capturas sensibles.",
    imageAnalysisLabel: "Obi miró tu imagen",
    imageTooLarge: "Demasiado grande — comprime tu imagen e inténtalo de nuevo.",
    imageTooMany: "Has alcanzado el límite de imágenes de este mensaje.",
    teaser: "Hola, soy Obi. ¿Ayuda con onboarding o soporte?",
    docs: "Docs para desarrolladores",
    support: "Artículos de soporte",
    restart: "Reiniciar conversación",
    more: "Más",
    language: "Idioma",
    screenshot: "Capturar esta página y preguntarle a Obi",
    close: "Cerrar",
    openAssistant: "Abrir asistente",
  },
  it: {
    greetingPre: "Ciao, come posso aiutarti con ",
    greetingPost: "? Più dettagli fornisci, meglio è.",
    suggestions: [
      "Con cosa puoi aiutarmi?",
      "Su quali argomenti hai informazioni?",
      "Quanto specifica deve essere la mia domanda?",
    ],
    clarifyingLabel: "Mi serve un altro dettaglio prima di cercare",
    handoffCta: "Preferisci una persona reale? Scrivici e ti aiutiamo.",
    placeholder: "Fai una domanda sul tuo spazio Confluence…",
    footer: "L’IA può commettere errori. Verifica le informazioni importanti.",
    imageDisclosure: "Non controlliamo le immagini per dati personali. Evita screenshot sensibili.",
    imageAnalysisLabel: "Obi ha guardato la tua immagine",
    imageTooLarge: "Troppo grande — comprimi la tua immagine e riprova.",
    imageTooMany: "Hai raggiunto il limite di immagini per questo messaggio.",
    teaser: "Ciao, sono Obi. Serve aiuto con onboarding o supporto?",
    docs: "Docs per sviluppatori",
    support: "Articoli di supporto",
    restart: "Riavvia la conversazione",
    more: "Altro",
    language: "Lingua",
    screenshot: "Catturare questa pagina e chiedere a Obi",
    close: "Chiudi",
    openAssistant: "Apri assistente",
  },
};

export function getCopy(locale: Locale): WidgetCopy {
  return COPY[locale];
}
