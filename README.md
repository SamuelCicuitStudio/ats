# ATS Platform – Frontend React (Guide complet en français)

Ce dossier `ats/` contient l’interface web (React) de la plateforme ATS.  
Elle permet :
- d’uploader et parser des CV et des fiches de poste (JD),
- de faire du matching (un JD vs plusieurs CV),
- de générer des tests à partir d’un JD,
- de consulter l’historique des actions,
- de gérer les utilisateurs,
- d’utiliser un chat KPI sur un PDF.

> Important : le frontend a besoin du backend FastAPI lancé en parallèle (dans `ats/backend`).  
> La page d’accueil (onglet **Accueil**) est l’écran qui s’ouvre par défaut.

---

## 1. Prérequis (même pour non-développeurs)

### 1.1. Logiciels à installer

Sur Windows (similaire sur macOS / Linux) :

1. **Python 3.10+**
   - Télécharger depuis : https://www.python.org/downloads/
   - Pendant l’installation, cochez « Add Python to PATH ».
2. **Node.js 18+ (avec npm)**
   - Télécharger depuis : https://nodejs.org/en/download
   - Après installation, ouvrez un terminal et vérifiez :
     ```bash
     node -v
     npm -v
     ```
3. Optionnel mais conseillé : **Git** (https://git-scm.com/downloads) pour cloner le repo.

### 1.2. Vérifier que tout fonctionne

Dans un terminal (PowerShell ou CMD) :
```bash
python --version
node -v
npm -v
```
Si chaque commande renvoie une version (par ex. `Python 3.11.x`, `v18.x`, etc.), c’est bon.

---

## 2. Lancer le backend (FastAPI)

Ces étapes se font **une seule fois** pour installer, puis à chaque fois que vous voulez lancer le backend.

1. Ouvrir un terminal dans le dossier du projet :
   ```bash
   cd D:\Freelancer\SOIBE\CvJobwebsite\ats\backend
   ```
2. Créer un environnement virtuel Python :
   ```bash
   python -m venv .venv
   ```
3. Activer l’environnement :
   - Sous PowerShell :
     ```bash
     .\.venv\Scripts\Activate.ps1
     ```
   - Sous CMD :
     ```bash
     .venv\Scripts\activate.bat
     ```
4. Installer les dépendances Python :
   ```bash
   pip install -r requirements.txt
   ```
5. Créer un fichier `.env` dans `ats/backend` (s’il n’existe pas) avec au minimum :
   ```env
   FRONTEND_ORIGIN=http://localhost:3000
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=admin123

   # Modèles / clés, à adapter à votre environnement
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL_CV=phi3:latest
   OLLAMA_MODEL_TEST=mistral
   SENTENCE_TRANSFORMERS_MODEL=sentence-transformers/all-MiniLM-L6-v2
   OPENROUTER_API_KEY=VOTRE_CLE
   OPENROUTER_MODEL_KPI=deepseek/deepseek-chat:free
   ```
6. Lancer le serveur FastAPI (backend) :
   ```bash
   uvicorn app.main:app --reload
   ```
7. Vérifier qu’il répond :
   - Ouvrir un navigateur sur : http://127.0.0.1:8000/health  
   - Vous devez voir un JSON avec `{"status":"ok", ...}`.

Tant que ce terminal reste ouvert, le backend tourne.

---

## 3. Lancer le frontend (React)

Dans un **second terminal** (laissez le backend tourner dans le premier) :

1. Aller dans le dossier `ats` :
   ```bash
   cd D:\Freelancer\SOIBE\CvJobwebsite\ats
   ```
2. Installer les dépendances JavaScript (une seule fois) :
   ```bash
   npm install
   ```
   > Cette étape peut prendre quelques minutes la première fois.

3. Lancer le serveur de développement React :
   ```bash
   npm start
   ```
4. Le navigateur devrait s’ouvrir automatiquement sur  
   `http://localhost:3000`. Sinon, ouvrez-le manuellement.

Par défaut, le frontend appelle l’API en `http://127.0.0.1:8000`.  
Vous pouvez changer cela via la variable `REACT_APP_API_BASE` si besoin.

---

## 4. Connexion à l’application

1. Sur la page de login, entrez les identifiants admin :
   - **Username** : `admin` (ou la valeur de `ADMIN_USERNAME`)
   - **Password** : `admin123` (ou la valeur de `ADMIN_PASSWORD`)
2. Cliquez sur **Log In**.
3. Vous arrivez sur l’onglet **Accueil** (tableau de bord).

---

## 5. Navigation dans l’interface

### 5.1. Onglet Accueil
- S’ouvre par défaut.
- Affiche :
  - Nombre de CV parsés,
  - Nombre de JD parsés,
  - Nombre de matchs effectués,
  - Nombre de tests générés.
- Affiche aussi les derniers matchs et tests (tirés de `/dashboard/summary`).

### 5.2. Pipeline de Recrutement
- Permet de :
  - Uploader **plusieurs CV** (jusqu’à 100) et **un JD**.
  - Parser le JD une fois.
  - Parser tous les CV un par un.
  - Faire du **matching bulk** (un JD vs tous les CV).
  - Voir un tableau des résultats triés par score global.
- Les actions déclenchent des entrées dans l’historique.

### 5.3. Génération de Tests
- Upload d’une fiche de poste (JD).
- Le backend génère une liste de questions.
- Vous pouvez voir le nombre de questions générées et l’historique associé.

### 5.4. Streaming CV
- Onglet placeholder pour des fonctionnalités futures :
  - Textes « Fonctionnalite en developpement / Le streaming de CV sera bientot disponible ».

### 5.5. Historique
- Affiche la liste des actions récentes renvoyées par `/history` :
  - `cv_parse` : parsing de CV.
  - `jd_parse` : parsing de JD.
  - `match` / `match_bulk` : matchs effectués.
  - `test_generate` : tests générés.
- Pour chaque entrée, vous pouvez avoir :
  - La date/heure,
  - Un lien **Original** (fichier source),
  - Un lien **Download** / **JSON** pour récupérer les artefacts si disponibles.

### 5.6. Gestion utilisateur
- Onglet réservé à l’admin (“Gestion utilisateur”) :
  - Créer un nouvel utilisateur (username / mot de passe / rôles),
  - Modifier un utilisateur existant,
  - Supprimer un utilisateur (avec garde pour ne pas supprimer le dernier admin).
- La gestion se fait via les endpoints `/users` du backend.

### 5.7. Bulle de chat KPI
- En bas à droite, une bulle permet d’ouvrir le chat KPI.
- Fonctionnement :
  1. Uploader un **PDF** contenant des KPI.
  2. Le backend crée une session.
  3. Vous posez des questions sur le contenu du PDF.

---

## 6. Configuration côté frontend

Si votre backend n’est pas sur `http://127.0.0.1:8000` :

1. Créez (ou éditez) un fichier `.env` dans `ats/` avec :
   ```env
   REACT_APP_API_BASE=http://ADRESSE_DE_VOTRE_API:8000
   ```
2. Relancez `npm start` pour que la variable soit prise en compte.

---

## 7. Build de production

Lorsque vous êtes satisfait et que vous voulez déployer :

1. Dans `ats/` :
   ```bash
   npm run build
   ```
2. Un dossier `ats/build/` est créé :
   - Contient les fichiers HTML/CSS/JS optimisés.
3. Servez ce dossier avec un serveur web (Nginx, Apache, etc.).
4. Configurez votre reverse-proxy pour que :
   - Le frontend soit servi depuis `build/`,
   - Les requêtes API soient redirigées vers le backend FastAPI.

---

## 8. Récapitulatif rapide pour quelqu’un “qui ne fait pas de web”

1. Installer **Python** et **Node.js**.
2. Dans `ats/backend` :
   - Créer et activer `.venv`,
   - `pip install -r requirements.txt`,
   - Créer `.env`,
   - Lancer : `uvicorn app.main:app --reload`.
3. Dans `ats/` :
   - `npm install`,
   - `npm start`.
4. Ouvrir `http://localhost:3000` dans le navigateur.
5. Se connecter avec `admin` / `admin123` (ou vos identifiants).
6. Utiliser les onglets :
   - Accueil → vue globale,
   - Pipeline → matcher CV/JD,
   - Generation de Tests → générer des questions,
   - Historique → voir et télécharger les résultats,
   - Gestion utilisateur → gérer les comptes,
   - Bulle de chat → poser des questions sur un PDF KPI.

