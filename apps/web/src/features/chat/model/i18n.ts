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
  suggestion: string;
  placeholder: string;
  footer: string;
  attachmentNotice: string;
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
    suggestion: "What can you help me with?",
    placeholder: "Ask about your Confluence workspace…",
    footer: "AI may make mistakes. Verify important information.",
    attachmentNotice: "Image attachments aren’t answered yet — sent as text only.",
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
    suggestion: "Waarmee kun je me helpen?",
    placeholder: "Stel een vraag over je Confluence-werkruimte…",
    footer: "AI kan fouten maken. Controleer belangrijke informatie.",
    attachmentNotice: "Afbeeldingen worden nog niet geanalyseerd — alleen als tekst verzonden.",
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
    suggestion: "Wobei kannst du mir helfen?",
    placeholder: "Stelle eine Frage zu deinem Confluence-Arbeitsbereich…",
    footer: "KI kann Fehler machen. Überprüfe wichtige Informationen.",
    attachmentNotice: "Bilder werden noch nicht analysiert — nur als Text gesendet.",
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
    suggestion: "En quoi puis-je vous aider ?",
    placeholder: "Posez une question sur votre espace Confluence…",
    footer: "L’IA peut faire des erreurs. Vérifiez les informations importantes.",
    attachmentNotice: "Les images ne sont pas encore analysées — envoyées comme texte uniquement.",
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
    suggestion: "¿En qué puedes ayudarme?",
    placeholder: "Haz una pregunta sobre tu espacio de Confluence…",
    footer: "La IA puede cometer errores. Verifica la información importante.",
    attachmentNotice: "Las imágenes aún no se analizan — se envían solo como texto.",
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
    suggestion: "Con cosa puoi aiutarmi?",
    placeholder: "Fai una domanda sul tuo spazio Confluence…",
    footer: "L’IA può commettere errori. Verifica le informazioni importanti.",
    attachmentNotice: "Le immagini non vengono ancora analizzate — inviate solo come testo.",
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
