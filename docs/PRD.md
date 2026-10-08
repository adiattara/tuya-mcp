# PRD — Serveur Tuya pour agent IA

## Problème

Le propriétaire veut qu'un agent IA ait accès à sa domotique Tuya. Aujourd'hui, ses appareils, dont des lampes LSC Smart Connect achetées chez Action, ne se pilotent que depuis l'app Tuya Smart : ouvrir l'app, trouver l'appareil, manipuler des curseurs, appareil par appareil. Aucun agent IA ne peut voir ni commander ces appareils. Passer par Alexa ou Google ajouterait un écosystème de plus, alors qu'il utilise déjà un agent IA au quotidien. Ces agents savent désormais se brancher sur des outils externes : c'est le bon moment pour leur ouvrir la domotique.

## Solution

Un serveur que l'agent IA du propriétaire utilise pour piloter tous les appareils de son compte Tuya en langage naturel : « allume la lampe du salon », « mets-la en bleu à 50 % », « blanc chaud ». L'agent peut lister les appareils, lire leur état et leurs capacités, les allumer et les éteindre, et déclencher les scènes du compte. Les lampes ont des commandes dédiées pour la luminosité, le blanc chaud/froid et la couleur. Tous les autres appareils restent pilotables via une commande générique. Le serveur passe par le cloud Tuya et fonctionne depuis n'importe quelle machine connectée à internet. Il est publié publiquement.

## Utilisateur cible

Le propriétaire lui-même. Il a des lampes LSC Smart Connect (marque blanche Tuya, achetées chez Action) appairées dans l'app Tuya Smart, et éventuellement d'autres appareils Tuya. Il utilise un agent IA au quotidien et veut lui confier le pilotage de sa domotique sans passer par Alexa ni Google. Il est à l'aise pour lancer une commande d'installation, créer un compte développeur Tuya en suivant un guide et configurer son agent. D'autres propriétaires d'appareils Tuya peuvent utiliser le serveur publié, mais ils ne sont pas la cible.

## User Stories

1. **US-1** — En tant qu'utilisateur, je veux installer et démarrer le serveur avec une seule commande, afin de brancher ma domotique à mon agent sans procédure lourde.
2. **US-2** — En tant qu'utilisateur, je veux suivre un guide pas-à-pas pour créer mon projet développeur Tuya, lier mon compte Tuya Smart et récupérer mes identifiants, afin de faire le setup sans aide.
3. **US-3** — En tant qu'utilisateur, je veux choisir la région de mon compte Tuya (Europe, États-Unis, Chine, Inde), afin que le serveur fonctionne quelle que soit ma région.
4. **US-4** — En tant qu'utilisateur, je veux que le serveur refuse de démarrer en nommant l'identifiant manquant, afin de corriger ma configuration immédiatement.
5. **US-5** — En tant qu'agent IA, je veux lister tous les appareils du compte avec leur nom, identifiant, catégorie et état en ligne/hors ligne, afin de savoir ce que je peux piloter.
6. **US-6** — En tant qu'agent IA, je veux désigner un appareil par son nom tel qu'affiché dans l'app, sans tenir compte des majuscules, ou par son identifiant, afin de traduire directement « la lampe du salon ».
7. **US-7** — En tant qu'agent IA, je veux un message listant les noms disponibles quand le nom demandé ne correspond à aucun appareil, afin de corriger ma demande ou de questionner l'utilisateur.
8. **US-8** — En tant qu'agent IA, je veux une erreur listant les candidats quand un nom correspond à plusieurs appareils, sans aucune action exécutée, afin de ne jamais piloter le mauvais appareil.
9. **US-9** — En tant qu'agent IA, je veux lire l'état courant d'un appareil (allumé, luminosité, couleur…), afin de répondre à « la lampe est allumée ? » ou d'ajuster relativement.
10. **US-10** — En tant qu'agent IA, je veux lire le modèle, le firmware et les capacités d'un appareil, afin de savoir quelles commandes il accepte.
11. **US-11** — En tant qu'agent IA, je veux allumer, éteindre ou inverser l'état de n'importe quel appareil, afin de répondre aux demandes les plus courantes.
12. **US-12** — En tant qu'agent IA, je veux régler la luminosité d'une lampe de 0 à 100, afin de répondre à « mets à 50 % ».
13. **US-13** — En tant qu'agent IA, je veux régler le blanc d'une lampe de 0 (chaud) à 100 (froid), afin de répondre à « blanc chaud ».
14. **US-14** — En tant qu'agent IA, je veux régler la couleur d'une lampe par teinte (0–360), saturation (0–100) et luminosité (0–100), afin de répondre à « mets-la en bleu ».
15. **US-15** — En tant qu'agent IA, je veux que la lampe passe automatiquement en mode couleur ou en mode blanc selon la commande, afin de ne pas gérer ce détail moi-même.
16. **US-16** — En tant qu'agent IA, je veux un refus indiquant la plage attendue quand une valeur est hors plage, afin de corriger ma commande.
17. **US-17** — En tant qu'agent IA, je veux être averti qu'une commande d'éclairage ne s'applique pas à un appareil qui n'est pas une lampe, afin de basculer vers la commande générique.
18. **US-18** — En tant qu'agent IA, je veux être informé qu'un appareil est hors ligne quand je tente de le piloter, afin de l'expliquer à l'utilisateur.
19. **US-19** — En tant qu'agent IA, je veux envoyer une commande brute (code + valeur) à n'importe quel appareil, afin de piloter ceux qui n'ont pas de commande dédiée.
20. **US-20** — En tant qu'agent IA, je veux lister les scènes « tap-to-run » du compte, afin de les proposer à l'utilisateur.
21. **US-21** — En tant qu'agent IA, je veux déclencher une scène par son nom ou son identifiant, afin de répondre à « lance la scène soirée ».
22. **US-22** — En tant qu'agent IA, je veux un message clair quand aucune scène n'existe ou que le nom demandé ne correspond à aucune scène, afin de ne pas inventer de résultat.
23. **US-23** — En tant qu'agent IA, je veux consulter l'historique récent d'un appareil quand il est disponible, et être averti sinon, afin de répondre à « qui a allumé la lampe ? ».
24. **US-24** — En tant qu'utilisateur, je veux que chaque erreur Tuya soit traduite en message clair indiquant la cause et l'action corrective (par exemple, en cas de permission refusée, activer le service « IoT Core » dans le projet cloud), afin de me débloquer seul.
25. **US-25** — En tant qu'utilisateur, je veux qu'un appareil ajouté dans l'app Tuya Smart apparaisse côté agent sans redémarrer le serveur, afin de ne pas avoir à le relancer.
26. **US-26** — En tant qu'utilisateur, je veux que mon secret Tuya n'apparaisse jamais dans les journaux ni dans les messages, même en mode détaillé, afin de pouvoir partager des journaux sans risque.
27. **US-27** — En tant qu'utilisateur, je veux lancer une vérification contre mon vrai compte, en lecture seule par défaut et avec les écritures seulement sur demande explicite, afin de valider mon setup sans toucher à mes appareils.

## Critères de succès

1. Le serveur s'installe et démarre avec une seule commande une fois les identifiants Tuya fournis.
2. La liste renvoyée à l'agent contient 100 % des appareils visibles dans l'app Tuya Smart.
3. Allumer, éteindre, régler la luminosité, le blanc chaud/froid et la couleur d'une vraie lampe fonctionne de bout en bout.
4. Tous les tests automatisés passent et le contrôle qualité du code ne signale aucune erreur.
5. Un tiers refait le setup Tuya de zéro en suivant uniquement le guide, sans aide.
6. Le secret Tuya n'apparaît dans aucun journal, même en mode détaillé.
7. Une commande sur une lampe se voit physiquement en moins de 3 secondes après l'appel de l'agent.
8. Une scène déclenchée par son nom depuis l'agent s'exécute, de façon vérifiable dans l'app ou physiquement.

## Hors périmètre

- Contrôle local sur le réseau de la maison : tout passe par le cloud Tuya.
- Interface graphique ou accès web : le serveur ne sert qu'à l'agent IA.
- Intégration Alexa, Google ou SmartThings.
- Commandes dédiées pour les minuteurs, ventilateurs, stores, thermostats, la gestion des pièces ou l'analyse de consommation d'énergie. Ces appareils restent pilotables via le socle générique.
- Modification du compte Tuya : appairage, renommage d'appareil, création ou édition de scène.
- Plusieurs comptes Tuya pour un même serveur.
- Demande de confirmation avant une action.

## Décisions d'implémentation

- **Langue :** guide, messages et erreurs en anglais.
- **Désignation d'un appareil :** nom exact tel qu'affiché dans l'app, sans tenir compte des majuscules, ou identifiant. Pas de correspondance approximative.
- **Nom introuvable :** erreur listant les noms disponibles. **Nom ambigu :** erreur listant les candidats, aucune action exécutée.
- **Échelles exposées à l'agent :**
  - luminosité 0–100 ;
  - blanc 0 (chaud) à 100 (froid) ;
  - couleur : teinte 0–360, saturation 0–100, luminosité 0–100.
- **Luminosité à 0 :** la lampe passe à son minimum, elle ne s'éteint pas. Pour éteindre, il faut la commande dédiée.
- **Luminosité en mode couleur :** la couleur actuelle est conservée, seule son intensité change (« mets le bleu à 50 % » reste bleu). En mode blanc, la lampe reste en blanc.
- **État affiché après une commande :** l'état lu reflète immédiatement ce qui vient d'être commandé, même si l'appareil tarde à le remonter ; un changement fait depuis l'app reprend le dessus dès qu'il est remonté.
- **Lampe éteinte :** un réglage de luminosité, de blanc ou de couleur ne l'allume pas. La réponse au réglage indique que la lampe est éteinte, pour que l'agent décide de l'allumer.
- **Bascule automatique :** une commande de couleur passe la lampe en mode couleur, une commande de blanc la passe en mode blanc.
- **Valeur hors plage :** refus avec la plage attendue, rien n'est envoyé à l'appareil.
- **Appareil hors ligne :** message explicite « hors ligne ».
- **Fraîcheur de la liste :** la liste des appareils se met à jour au plus tard 60 secondes après un changement dans l'app. Ce délai est réglable.
- **Région :** Europe par défaut, les 4 régions documentées dans le guide.
- **Démarrage :** si un identifiant manque, le serveur refuse de démarrer et nomme le paramètre, sans jamais afficher la valeur du secret.
- **Vérification contre le vrai compte :** lecture seule par défaut, écritures seulement sur option explicite.
- **Distribution :** publique, sous licence MIT, avec un guide de setup pas-à-pas, l'exemple de configuration de l'agent et une section de dépannage des erreurs courantes.

## Notes complémentaires

- **Dépendance :** tout repose sur le cloud Tuya et sur un compte développeur Tuya gratuit. L'accès gratuit aux services est limité dans le temps et doit être renouvelé périodiquement.
- **Risque :** les points d'accès Tuya cités dans le brief, notamment ceux des scènes, sont à valider contre la doc officielle. Aucune adresse ne doit être inventée.
- **Hypothèse :** les lampes LSC exposent les capacités d'éclairage standard Tuya. Le serveur les découvre appareil par appareil au lieu de les supposer.
- **Hypothèse :** l'historique récent n'est pas disponible pour tous les appareils.
