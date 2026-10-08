# Plan : Serveur MCP Tuya (`tuya-mcp`)

> PRD source : `docs/PRD.md`

## Décisions architecturales

Décisions durables qui s'appliquent à toutes les phases :

- **Stack** : Python ≥ 3.11, SDK MCP officiel (`mcp` 2.x, `MCPServer` — ex-`FastMCP`), client HTTP `httpx`. Transport stdio uniquement. Typage strict, `ruff` sans erreur, tests `pytest` avec HTTP mocké.
- **Paquet** : nom `tuya-mcp`, point d'entrée console `tuya-mcp`, lançable via `uvx tuya-mcp`. Licence MIT.
- **Langue** : code, commentaires, README et messages d'erreur en anglais.
- **Configuration** : variables d'environnement uniquement, aucun fichier de config.
  - `TUYA_ACCESS_ID` (obligatoire)
  - `TUYA_ACCESS_SECRET` (obligatoire, jamais loggé ni affiché)
  - `TUYA_UID` (obligatoire)
  - `TUYA_API_ENDPOINT` (défaut `https://openapi.tuyaeu.com` ; US `openapi.tuyaus.com`, CN `openapi.tuyacn.com`, IN `openapi.tuyain.com`)
  - `TUYA_CACHE_TTL` (défaut `60` secondes)
  - `TUYA_LOG_LEVEL` (défaut `WARNING`, logs sur stderr ; ajouté en phase 1 pour le mode debug)
- **Authentification Tuya** : signature HMAC-SHA256 selon https://developer.tuya.com/en/docs/iot/singnature.
  - Token : `sign = HMAC(secret, client_id + t + stringToSign)`.
  - Requêtes métier : `sign = HMAC(secret, client_id + access_token + t + stringToSign)`.
  - `stringToSign = METHOD + "\n" + SHA256(body) + "\n" + "\n" + path_with_query`.
  - Signature en hex majuscules, SHA256 du body en hex minuscules, `t` en ms (13 chiffres).
  - Écart doc officielle vs brief (vérifié phase 1) : la chaîne signée inclut un `nonce` (UUID par requête) après `t`, et la query est triée par clé. Testé contre les vecteurs officiels.
  - Token mis en cache et rafraîchi automatiquement avant `expire_time`.
- **Endpoints Tuya** (à valider contre la doc officielle, ne jamais inventer d'URL) :
  - Token : `GET /v1.0/token?grant_type=1`
  - Liste : `GET /v1.0/iot-01/associated-users/devices?last_row_key=…&size=20` (doc officielle : pas de `uid`, pagination `has_more` / `last_row_key`)
  - Statut : `GET /v1.0/iot-03/devices/{device_id}/status`
  - Infos : `GET /v1.0/iot-03/devices/{device_id}`
  - Firmware : `GET /v2.0/cloud/thing/{device_id}/firmware` (vérifié phase 2 ; les variantes v1.0 renvoient 1108)
  - Spécifications : `GET /v1.0/iot-03/devices/{device_id}/specification` (singulier : `functions` + `status` avec `values` ; le pluriel existe mais renvoie `scopes`)
  - Commandes : `POST /v1.0/iot-03/devices/{device_id}/commands` avec `{"commands": [{"code", "value"}]}`
  - Maisons : `GET /v1.0/users/{uid}/homes` (→ `home_id`)
  - Scènes : `GET /v2.0/cloud/scene/rule?space_id={home_id}` (filtre `type == "scene"` = tap-to-run ; `automation` exclu) et `POST /v2.0/cloud/scene/rule/{id}/actions/trigger` (vérifiés phase 6 ; l'ancienne API `/v1.0/homes/{home_id}/scenes` répond aussi mais le service est marqué *[Deprecate]*)
- **Modèles clés** :
  - `Device` : id, name, category, online.
  - `DeviceStatus` : liste de `{code, value}`.
  - `Specification` : codes DP et plages.
  - `Scene` : id, name.
  - `TuyaError` : code, msg, message clair.
- **Architecture** :
  - Une couche client Tuya unique, qui gère la signature, le token, l'appel et la remontée des erreurs `code`/`msg`.
  - Un résolveur d'appareil unique (nom exact insensible à la casse ou ID, erreur si introuvable ou ambigu), réutilisé par tous les outils.
  - Un cache mémoire de la liste d'appareils, avec TTL.
  - Des outils MCP fins, préfixés `tuya_`, construits au-dessus. Ajouter un outil doit rester trivial.
- **Codes DP lampe** (`category: "dj"`) :
  - `switch_led` (bool) ;
  - `work_mode` (`white`/`colour`/`scene`/`music`) ;
  - `bright_value` (10–1000) ;
  - `temp_value` (0–1000) ;
  - `colour_data` (JSON `{"h":0-360,"s":0-1000?,"v":0-1000?}`, plages lues dans les spécifications de l'appareil plutôt que codées en dur).
- **Codes réels (vérifiés sur LSC Smart Table Lamp, phase 2)** : la lampe expose `bright_value_v2`, `temp_value_v2`, `colour_data_v2` avec s/v sur 0–1000. Les codes sont découverts par spécification (variantes `_v2` puis legacy), jamais supposés.
- **État envoyé prioritaire** : les lampes LSC exécutent les commandes mais remontent leur nouvel état au cloud en retard ou jamais (mesuré : > 10 s, souvent jamais). Le client retient chaque valeur envoyée et la superpose à l'état cloud pendant 5 min, sauf si le cloud remonte entre-temps une valeur différente de celle d'avant l'envoi (changement fait ailleurs, ex. app) ou rattrape la valeur envoyée. Toggle, note « lampe éteinte », luminosité en mode couleur et lecture d'état s'appuient dessus.
- **Luminosité en mode couleur** : `tuya_set_brightness` sur une lampe en mode couleur change l'intensité `v` de la couleur courante (la couleur est conservée) ; sinon elle passe en blanc et règle `bright_value*`.
- **Erreurs** : jusqu'à la phase 8, les erreurs Tuya remontent brutes (`code` + `msg`). La phase 8 ajoute la traduction en messages clairs.

---

## Phase 1 : Démarrer et lister les appareils

**User stories** : US-1, US-3, US-4, US-5, US-26

### Ce qu'on livre

`uvx tuya-mcp` démarre un serveur MCP stdio qui lit sa configuration depuis l'environnement, obtient et met en cache un token signé, et expose `tuya_list_devices`. L'outil renvoie id, nom, catégorie et état en ligne/hors ligne de chaque appareil du compte lié. Si une variable obligatoire manque, le serveur refuse de démarrer en nommant la variable. Le secret n'apparaît nulle part.

### Critères d'acceptation

- [x] `uvx tuya-mcp` (ou installation locale équivalente) démarre sans erreur avec les variables posées.
- [x] Une variable obligatoire manquante empêche le démarrage avec un message qui nomme la variable, sans afficher le secret.
- [x] Tests unitaires de la signature HMAC (token et requête métier) avec vecteurs connus.
- [x] Le token est réutilisé entre appels et rafraîchi avant expiration (test avec horloge simulée).
- [x] `tuya_list_devices` renvoie la liste parsée (test avec HTTP mocké) et les vrais appareils contre le cloud.
- [x] `TUYA_API_ENDPOINT` change l'endpoint appelé. EU par défaut.
- [x] Aucun log, même en debug, ne contient `TUYA_ACCESS_SECRET` (test dédié).
- [x] `pytest` passe et `ruff check` est sans erreur.

## Bloquée par

Aucune — démarrable immédiatement.

---

## Phase 2 : Désigner un appareil et lire son état

**User stories** : US-6, US-7, US-8, US-9, US-10, US-25

### Ce qu'on livre

Le résolveur d'appareil (nom exact insensible à la casse ou ID) et trois outils de lecture : `tuya_get_device_status`, `tuya_get_device_info` et `tuya_get_device_specifications`. La liste des appareils est mise en cache selon `TUYA_CACHE_TTL` : un appareil ajouté dans l'app apparaît après expiration du cache, sans redémarrage.

### Critères d'acceptation

- [x] « salon lamp », « Salon Lamp » et l'ID désignent le même appareil.
- [x] Un nom introuvable renvoie une erreur listant les noms disponibles.
- [x] Un nom ambigu renvoie une erreur listant les candidats, sans aucun appel de commande.
- [x] Le statut, les infos (modèle, firmware, nœud) et les spécifications sont renvoyés pour un vrai appareil.
- [x] Le cache évite un second appel de liste dans le TTL et se rafraîchit après (test avec horloge simulée).

## Bloquée par

- Phase 1

---

## Phase 3 : Allumer, éteindre, commande générique

**User stories** : US-11, US-18, US-19

### Ce qu'on livre

`tuya_turn_on`, `tuya_turn_off` et `tuya_toggle`, qui fonctionnent pour tout appareil : le code d'interrupteur est déduit des spécifications (`switch_led`, `switch_1`, `switch`…). `tuya_send_command(device, code, value)` envoie une commande DP brute. Piloter un appareil hors ligne renvoie un message explicite « offline ».

### Critères d'acceptation

- [x] Une vraie lampe s'allume, s'éteint et bascule, de façon visible en moins de 3 s.
- [x] `tuya_toggle` inverse l'état lu.
- [x] `tuya_send_command` envoie le body `{"commands": [{"code", "value"}]}` attendu (test mocké).
- [x] Un appareil hors ligne produit un message « offline » clair.
- [x] Un appareil sans code d'interrupteur reconnu produit un message invitant à utiliser `tuya_send_command`.

## Bloquée par

- Phase 2

---

## Phase 4 : Luminosité et blanc

**User stories** : US-12, US-13, US-15, US-16, US-17

### Ce qu'on livre

`tuya_set_brightness(device, 0–100)` et `tuya_set_color_temperature(device, 0–100)`, avec 0 = blanc chaud et 100 = blanc froid. Les valeurs sont converties vers les plages de l'appareil (par défaut 10–1000 et 0–1000) et la lampe passe automatiquement en `work_mode: "white"`. Une luminosité de 0 met la lampe au minimum sans l'éteindre. Une lampe éteinte n'est pas allumée, mais la réponse signale qu'elle est éteinte. Une valeur hors plage est refusée avec la plage attendue, sans appel. Un appareil qui n'est pas une lampe est refusé avec un renvoi vers `tuya_send_command`.

### Critères d'acceptation

- [x] Tests de conversion des échelles, bornes comprises (0 → 10, 100 → 1000).
- [x] La commande envoyée inclut `work_mode: "white"` (test mocké).
- [x] Une valeur hors plage est refusée sans appel HTTP.
- [x] Sur une lampe éteinte, la réponse mentionne qu'elle est éteinte et aucun `switch_led: true` n'est envoyé.
- [x] Un appareil non-lampe est refusé avec un renvoi vers la commande générique.
- [x] Sur une vraie lampe, 50 % et blanc chaud sont visibles en moins de 3 s.

## Bloquée par

- Phase 3

---

## Phase 5 : Couleur

**User stories** : US-14, US-15, US-16

### Ce qu'on livre

`tuya_set_color(device, hue 0–360, saturation 0–100, brightness 0–100)`. Les valeurs sont converties en `colour_data` (chaîne JSON) selon les plages lues dans les spécifications de l'appareil, et la lampe passe automatiquement en `work_mode: "colour"`. Les comportements de la phase 4 s'appliquent aussi : plages vérifiées, lampe éteinte signalée, refus d'un appareil non-lampe.

### Critères d'acceptation

- [x] Tests de conversion HSV, bornes comprises, pour les variantes de plages (0–255 et 0–1000).
- [x] La commande envoyée inclut `work_mode: "colour"` et `colour_data` sous forme de chaîne JSON (test mocké).
- [x] Une valeur hors plage est refusée sans appel HTTP.
- [x] Sur une vraie lampe, « bleu à 50 % » est visible en moins de 3 s.

## Bloquée par

- Phase 4

---

## Phase 6 : Scènes

**User stories** : US-20, US-21, US-22

### Ce qu'on livre

`tuya_list_scenes` liste les scènes « tap-to-run » du compte. `tuya_trigger_scene` déclenche une scène par son nom (exact, insensible à la casse) ou par son ID. Un message clair est renvoyé quand aucune scène n'existe ou que le nom est introuvable (avec la liste des noms) ou ambigu. Les endpoints exacts sont validés contre la doc officielle avant implémentation.

### Critères d'acceptation

- [x] Les endpoints scènes sont confirmés dans la doc Tuya, avec la référence notée dans le code.
- [x] La liste parsée est correcte (test mocké) et les vraies scènes sont renvoyées contre le cloud.
- [x] Une scène déclenchée par son nom s'exécute, de façon vérifiable physiquement ou dans l'app.
- [x] Les cas aucune scène, nom introuvable et nom ambigu produisent des messages clairs.

## Bloquée par

- Phase 1

---

## Phase 7 : Historique d'un appareil

**User stories** : US-23

### Ce qu'on livre

`tuya_get_device_events(device)` renvoie l'historique récent quand l'appareil et le compte le permettent. Sinon, l'outil renvoie un message explicite indiquant que l'historique n'est pas disponible pour cet appareil.

### Critères d'acceptation

- [ ] L'endpoint d'historique est confirmé dans la doc Tuya.
- [ ] Les événements parsés sont corrects (test mocké).
- [ ] Une réponse vide ou non supportée produit le message « not available ».

## Bloquée par

- Phase 2

---

## Phase 8 : Erreurs Tuya traduites

**User stories** : US-24

### Ce qu'on livre

La couche client traduit les codes d'erreur Tuya courants en messages clairs, avec la cause et l'action corrective. Par exemple, « permission deny » invite à activer les Service API IoT Core dans le projet cloud. Les cas couverts au minimum sont les suivants : token invalide ou expiré, signature invalide, mauvaise région, appareil non lié au compte, quota ou essai expiré. Un code inconnu remonte avec son `code` et son `msg` d'origine.

### Critères d'acceptation

- [x] Chaque code du catalogue produit le message attendu (tests paramétrés).
- [x] Un code inconnu remonte `code` et `msg` bruts.
- [x] Tous les outils existants bénéficient de la traduction sans modification individuelle.

## Bloquée par

- Phase 1

---

## Phase 9 : Vérification contre le vrai compte

**User stories** : US-27

### Ce qu'on livre

`smoke_test.py` vérifie le setup contre le vrai cloud. Par défaut, il ne fait que des lectures : token, liste, statut, spécifications, scènes. Avec `--include-write`, il fait aussi un cycle d'écriture réversible sur un appareil choisi (allumer, régler, puis restaurer l'état initial).

### Critères d'acceptation

- [ ] Sans option, aucune commande d'écriture n'est envoyée (vérifiable dans la sortie).
- [ ] Avec `--include-write`, l'état initial de l'appareil est restauré à la fin.
- [ ] Le script affiche un résumé succès/échec par étape et ne montre jamais le secret.

## Bloquée par

- Phase 3
- Phase 6

---

## Phase 10 : Guide et publication

**User stories** : US-2

### Ce qu'on livre

La phase livre :
- un README pas-à-pas, qui couvre :
  - le compte iot.tuya.com ;
  - le Cloud Project « Smart Home » dans la bonne région ;
  - la liaison du compte Tuya Smart / Smart Life par QR ;
  - l'activation des Service API IoT Core ;
  - la récupération de l'Access ID, du Secret et de l'UID ;
  - le tableau des régions ;
  - les exemples de configuration Claude Desktop et Claude Code ;
  - le dépannage des erreurs du catalogue de la phase 8 ;
- `LICENSE` (MIT), `.gitignore`, `.env.example` et `CHANGELOG.md` ;
- un `pyproject.toml` prêt pour PyPI.

### Critères d'acceptation

- [ ] Un tiers refait le setup de zéro en suivant uniquement le README.
- [ ] `.env.example` liste toutes les variables, sans valeur secrète.
- [ ] Le paquet se construit et s'installe via `uvx` depuis l'artefact construit.
- [ ] Les 8 critères de succès du PRD sont vérifiés et cochés dans le CHANGELOG de la version 0.1.0.

## Bloquée par

- Phases 1 à 9
