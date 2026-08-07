# FunnyCuteDogs — Pipeline d'automatisation YouTube + Instagram

Chaîne 100% automatisée pour `@funnycutedogs` : sourcing des clips, narration,
montage et publication sur YouTube + Instagram (Reels), sans intervention
manuelle. Entièrement gratuit (GitHub Actions + FFmpeg + Pexels API + Edge TTS
+ YouTube Data API v3 + Instagram Graph API + Cloudflare R2).

## Setup initial (une seule fois)

1. `pip install -r requirements.txt` en local
2. `python scripts/get_refresh_token.py` — ouvre ton navigateur, tu autorises
   l'accès à ta chaîne YouTube, le script affiche 3 valeurs à copier
3. Va dans **Settings > Secrets and variables > Actions** du repo GitHub et
   ajoute ces secrets :
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`
   - `IG_ACCESS_TOKEN` (token système Meta, ne expire pas)
   - `IG_BUSINESS_ACCOUNT_ID` (compte Instagram Business lié à la Page)
   - `FB_PAGE_ID`
   - `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`,
     `R2_PUBLIC_URL` (hébergement temporaire public requis par l'API
     Instagram, bucket R2 gratuit)
   - `PEXELS_API_KEY` (clé gratuite sur [pexels.com/api](https://www.pexels.com/api/),
     sourcing automatique des clips vidéo libres de droits)

## Publier une nouvelle vidéo

1. Crée un dossier `videos/<nom-du-theme>/`
2. Crée `videos/<nom-du-theme>/meta.json` — copie `videos/zoomies/meta.json`
   comme modèle. Il contient tout ce dont le pipeline a besoin :
   - `title`, `description`, `tags`, `privacyStatus` → métadonnées YouTube
   - `script` → texte narré, converti en voix off automatiquement
   - `keywords` → termes de recherche pour trouver des clips libres de droits
   - `numClips` → nombre de clips à assembler (8 par défaut)
3. Push sur GitHub, puis va dans l'onglet **Actions** → workflow
   **"Render and upload video"** → **Run workflow** → indique le nom du
   dossier (ex: `zoomies`) → Run

Le workflow produit systématiquement deux formats, tous les deux en HD minimum
(canevas 1920x1080, clips sourcés en 720p+ uniquement, encodage CRF 18) :

- **une vidéo longue** (`final.mp4`, garantie **> 60s** — le script échoue si
  ce n'est pas le cas, il faut alors allonger le `script`) → publiée en vidéo
  YouTube classique
- **un Short** (`reel.mp4`, format vertical 9:16, coupé à **≤ 60s**) → publié
  à la fois en **YouTube Shorts** et en **Instagram Reel**

Étapes :
1. télécharge des clips HD libres de droits depuis Pexels (mots-clés du `meta.json`)
2. génère la narration à partir du `script` (voix neuronale gratuite Edge TTS)
3. assemble la vidéo longue avec FFmpeg (clips normalisés en 1080p + narration + watermark)
4. la publie sur YouTube (vidéo longue)
5. découpe le Short vertical 9:16 à partir de la vidéo longue
6. publie le Short sur YouTube (Shorts) et sur Instagram (Reel, via hébergement
   temporaire Cloudflare R2, supprimé juste après publication)

Apporter tes propres clips/narration reste possible : il suffit de déposer
`clips/*.mp4` et `narration.mp3` toi-même, le pipeline ne les régénère que
s'ils sont absents.

## Publication automatique espacée (file d'attente)

`videos/queue.txt` liste les slugs à publier, un par ligne, dans l'ordre.
Le workflow **"Scheduled publish"** tourne automatiquement Mardi, Jeudi et
Dimanche à 15h UTC : il dépile la première ligne de la queue, publie cette
vidéo (vidéo longue + Short YouTube + Reel Instagram), retire la ligne et
commit la queue mise à jour. Zéro intervention manuelle — il suffit d'ajouter
des slugs à `queue.txt` (et leur `meta.json` correspondant) pour garder le
rythme de publication.

## Shorts/Reels quotidiens (reach + monétisation)

En plus des vidéos longues 3×/semaine, `videos/shorts_queue.txt` alimente un
second pipeline, **"Daily shorts publish"**, qui tourne **tous les jours** à
15h UTC. Chaque entrée est un dossier `videos/short-<sujet>/meta.json` (même
structure que les vidéos longues, sans `numClips` élevé — 4 clips suffisent
pour un format court) : le pipeline source les clips, génère la narration,
assemble directement un Short vertical HD (`scripts/assemble_short.py`, ≤58s)
et le publie sur YouTube Shorts + Instagram Reels.

Publier des Shorts tous les jours est le levier le plus rapide pour la portée
et pour la monétisation YouTube : le seuil alternatif du programme partenaire
(10M vues Shorts sur 90 jours) est bien plus accessible via du volume
quotidien que via des vidéos longues, qui restent à 3×/semaine pour préserver
leur qualité.

## Watermark de chaîne (optionnel)

Place un logo PNG transparent dans `assets/logo_watermark.png` — il sera
incrusté en bas à droite de chaque vidéo automatiquement.

## Tester le montage en local (sans publier)

```
python scripts/assemble_video.py videos/zoomies
```

Génère `videos/zoomies/final.mp4` que tu peux visionner avant de publier.
