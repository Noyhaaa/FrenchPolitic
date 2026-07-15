import { PlaceholderScreen } from './PlaceholderScreen';

/**
 * Assistant IA — hors V1. Arrivera en V2 sous forme de questions
 * pré-cadrées (pas de champ libre au début, §2.3).
 */
export function AssistantScreen() {
  return (
    <PlaceholderScreen
      emoji="💬"
      title="Assistant"
      description="Bientôt : posez des questions sur un vote et obtenez des réponses toujours reliées aux sources officielles."
      jalon="Prévu en V2 · questions pré-cadrées"
    />
  );
}
