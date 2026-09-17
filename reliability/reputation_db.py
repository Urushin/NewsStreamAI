"""
NewsStreamAI — Source Reputation Database
Assigns credibility tiers and trust scores to incoming media domains.
"""
import functools
from typing import Dict, Tuple, Optional

TIER_1_REPUTATION = {
    "reuters.com": 0.98,
    "apnews.com": 0.98,
    "afp.com": 0.97,
    "ft.com": 0.95,
    "bloomberg.com": 0.95,
    "lemonde.fr": 0.93,
    "bbc.com": 0.95,
    "wsj.com": 0.95,
    "nature.com": 0.99,
    "science.org": 0.99,
    "theguardian.com": 0.90,
    "lesechos.fr": 0.92,
    "techcrunch.com": 0.88,
    "theverge.com": 0.88,
    "wired.com": 0.89,
    "arstechnica.com": 0.90,
}

TIER_3_TABLOIDS_AND_UNRELIABLE = {
    "dailymail.co.uk": 0.45,
    "thesun.co.uk": 0.40,
    "nypost.com": 0.55,
    "express.co.uk": 0.40,
    "mirror.co.uk": 0.45,
}

# ── Media Ownership Transparency & Editorial Positioning Database ──
MEDIA_PROFILES = {
    # French Press
    "lesechos.fr": {
        "owner": "Groupe LVMH (Bernard Arnault)",
        "orientation": "Économie libérale / Pro-business",
        "funding": "Abonnements payants & Publicité",
        "country": "France",
        "description": "Quotidien économique de référence en France, propriété de LVMH depuis 2007."
    },
    "lefigaro.fr": {
        "owner": "Groupe Dassault",
        "orientation": "Droite républicaine / Libéral-conservateur",
        "funding": "Abonnements payants & Publicité",
        "country": "France",
        "description": "Plus ancien quotidien national français, détenu par la famille Dassault."
    },
    "lemonde.fr": {
        "owner": "Pôle d'indépendance / Xavier Niel / Matthieu Pigasse",
        "orientation": "Centre-gauche / Référence éditoriale",
        "funding": "Abonnements payants (majoritaire)",
        "country": "France",
        "description": "Quotidien vespéral de référence avec charte d'indépendance de la rédaction."
    },
    "cnews.fr": {
        "owner": "Groupe Canal+ / Vivendi (Vincent Bolloré)",
        "orientation": "Conservateur / Débat d'opinion",
        "funding": "Publicité & Filiale de groupe audiovisuel",
        "country": "France",
        "description": "Chaîne d'information continue et site d'actualités du groupe Vivendi."
    },
    "bfmtv.com": {
        "owner": "Groupe CMA CGM (Rodolphe Saadé)",
        "orientation": "Information continue / Généraliste",
        "funding": "Publicité & Groupe audiovisuel",
        "country": "France",
        "description": "Première chaîne d'information en continu de France, reprise par CMA CGM en 2024."
    },
    "latribune.fr": {
        "owner": "Groupe CMA CGM (Rodolphe Saadé)",
        "orientation": "Économie / Transition écologique",
        "funding": "Abonnements & Événements professionnels",
        "country": "France",
        "description": "Titre économique et quotidien dominical, filiale médias de CMA CGM."
    },
    "mediapart.fr": {
        "owner": "Fonds pour une presse libre (Aucun actionnaire)",
        "orientation": "Gauche / Investigation indépendante",
        "funding": "100% Abonnements (zéro pub, zéro subvention)",
        "country": "France",
        "description": "Journal d'investigation en ligne participatif, propriété d'un fonds de dotation inaliénable."
    },
    "liberation.fr": {
        "owner": "Fonds de dotation indépendant (Financé par Daniel Křetínský)",
        "orientation": "Gauche sociale-démocrate",
        "funding": "Abonnements payants & Fonds non lucratif",
        "country": "France",
        "description": "Fondé par Jean-Paul Sartre, transféré en 2020 vers un fonds sans but lucratif."
    },
    "francetvinfo.fr": {
        "owner": "État français (France Télévisions / Service Public)",
        "orientation": "Neutre / Information de service public",
        "funding": "Financement public de l'audiovisuel",
        "country": "France",
        "description": "Portail d'information multimédia du service public audiovisuel français."
    },
    "radiofrance.fr": {
        "owner": "État français (Radio France / Service Public)",
        "orientation": "Pluraliste / Service public",
        "funding": "Financement public",
        "country": "France",
        "description": "Premier groupe radiophonique français (France Inter, France Info, France Culture)."
    },
    "lepoint.fr": {
        "owner": "Groupe Artémis (Famille François Pinault)",
        "orientation": "Centre-droit / Libéral",
        "funding": "Ventes en kiosque & Abonnements",
        "country": "France",
        "description": "Magazine d'actualité hebdomadaire propriété de la holding de François Pinault."
    },
    "lexpress.fr": {
        "owner": "Alain Weill (Groupe L'Express)",
        "orientation": "Centre / Libéralisme réformiste",
        "funding": "Abonnements payants",
        "country": "France",
        "description": "Hebdomadaire d'information générale d'inspiration libérale et pro-européenne."
    },
    "marianne.net": {
        "owner": "CMI France (Daniel Křetínský)",
        "orientation": "Républicain / Souverainiste de gauche",
        "funding": "Abonnements & Kiosque",
        "country": "France",
        "description": "Magazine hebdomadaire d'actualités et d'opinions polémiques."
    },
    "humanite.fr": {
        "owner": "Société éditrice coopérative de l'Humanité",
        "orientation": "Gauche radicale / Mouvement social",
        "funding": "Abonnements & Souscriptions de lecteurs",
        "country": "France",
        "description": "Fondé par Jean Jaurès en 1904, voix historique du mouvement ouvrier."
    },
    "20minutes.fr": {
        "owner": "Groupe Rossel / Groupe Sipa Ouest-France",
        "orientation": "Généraliste / Populaire neutre",
        "funding": "Publicité numérique",
        "country": "France",
        "description": "Média gratuit d'information générale grand public."
    },
    "usinenouvelle.com": {
        "owner": "Infopro Digital (TowerBrook Capital)",
        "orientation": "Industrie, Aéronautique & Ingénierie",
        "funding": "Abonnements B2B",
        "country": "France",
        "description": "Média de référence pour les cadres dirigeants et ingénieurs industriels."
    },

    # International & Financial Press
    "reuters.com": {
        "owner": "Thomson Reuters Trust Principles (Fondation)",
        "orientation": "Agence de presse factuelle internationale",
        "funding": "Abonnements financiers & Flux agence",
        "country": "Royaume-Uni / Canada",
        "description": "L'une des plus grandes agences de presse mondiales, régie par les Trust Principles garantissant son indépendance absolue."
    },
    "bloomberg.com": {
        "owner": "Michael Bloomberg (Bloomberg L.P.)",
        "orientation": "Finance mondiale / Données de marché",
        "funding": "Terminaux Bloomberg & Abonnements",
        "country": "États-Unis",
        "description": "Leader mondial de l'information financière et technologique."
    },
    "apnews.com": {
        "owner": "The Associated Press (Coopérative à but non lucratif)",
        "orientation": "Agence de presse factuelle non partisane",
        "funding": "Cotisations des membres médias mondiaux",
        "country": "États-Unis",
        "description": "Coopérative journalistique américaine fournissant des dépêches brutes vérifiées à l'échelle du globe."
    },
    "ft.com": {
        "owner": "Nikkei Inc. (Groupe de presse japonais)",
        "orientation": "Référence économique & financière mondiale",
        "funding": "Abonnements payants institutionnels",
        "country": "Royaume-Uni / Japon",
        "description": "Quotidien économique international au papier saumoné réputé pour sa rigueur d'analyse."
    },
    "wsj.com": {
        "owner": "News Corp / Dow Jones (Famille Rupert Murdoch)",
        "orientation": "Conservateur fiscal / Marchés financiers",
        "funding": "Abonnements payants",
        "country": "États-Unis",
        "description": "Quotidien financier de référence aux États-Unis, réputé pour son journalisme d'investigation économique."
    },
    "theguardian.com": {
        "owner": "The Scott Trust (Fiducie philanthropique)",
        "orientation": "Centre-gauche / Écologie & Investigation",
        "funding": "Dons de lecteurs & Mécénat (zéro paywall)",
        "country": "Royaume-Uni",
        "description": "Propriété du Scott Trust pour protéger son indépendance perpétuelle contre tout rachat."
    },
    "bbc.com": {
        "owner": "Couronne britannique / Charte royale d'indépendance",
        "orientation": "Service public impartial",
        "funding": "Redevance audiovisuelle publique britannique",
        "country": "Royaume-Uni",
        "description": "Plus ancien et influent diffuseur national public au monde."
    },
    "economist.com": {
        "owner": "The Economist Group (Familles Agnelli, Rothschild, Cadbury)",
        "orientation": "Libéralisme classique / Macroéconomie",
        "funding": "Abonnements payants mondiaux",
        "country": "Royaume-Uni",
        "description": "Revue hebdomadaire mondiale de référence en géopolitique et économie."
    },
    "politico.com": {
        "owner": "Axel Springer SE",
        "orientation": "Coulisses du pouvoir / Non partisan",
        "funding": "Abonnements professionnels (Pro) & Publicité",
        "country": "États-Unis / Allemagne",
        "description": "Spécialiste du journalisme politique d'initiés à Washington et Bruxelles."
    },
    "politico.eu": {
        "owner": "Axel Springer SE",
        "orientation": "Affaires européennes & Régulation",
        "funding": "Abonnements Pro & Événements",
        "country": "Union Européenne / Belgique",
        "description": "Couverture d'investigation sur les institutions et politiques de l'UE."
    },
    "dw.com": {
        "owner": "État fédéral allemand (Deutsche Welle)",
        "orientation": "Service public démocratique & Multilingue",
        "funding": "Impôt fédéral allemand",
        "country": "Allemagne",
        "description": "Audiovisuel extérieur allemand promouvant la liberté de la presse."
    },
    "euronews.com": {
        "owner": "Alpac Capital (Fonds d'investissement)",
        "orientation": "Affaires paneuropéennes",
        "funding": "Publicité & Partenariats",
        "country": "France / Portugal",
        "description": "Chaîne d'information paneuropéenne multilingue basée à Lyon et Bruxelles."
    },

    # Tech, Science & Innovation
    "nature.com": {
        "owner": "Springer Nature",
        "orientation": "Science fondamentale & Recherche par les pairs",
        "funding": "Abonnements académiques & Open Access",
        "country": "Royaume-Uni / Allemagne",
        "description": "L'une des revues scientifiques multidisciplinaires les plus prestigieuses au monde."
    },
    "science.org": {
        "owner": "AAAS (American Association for the Advancement of Science)",
        "orientation": "Science fondamentale",
        "funding": "Société savante sans but lucratif",
        "country": "États-Unis",
        "description": "Revue scientifique à fort facteur d'impact de l'association américaine pour le progrès scientifique."
    },
    "techcrunch.com": {
        "owner": "Apollo Global Management (Yahoo)",
        "orientation": "Startups, VCs & Technologies émergentes",
        "funding": "Publicité & Événements (Disrupt)",
        "country": "États-Unis",
        "description": "Média de référence sur l'écosystème startup mondial et la Silicon Valley."
    },
    "theverge.com": {
        "owner": "Vox Media",
        "orientation": "Culture technologique, Gadgets & Médias",
        "funding": "Publicité & Liens affiliés",
        "country": "États-Unis",
        "description": "Site tech d'envergure couvrant les intersections entre technologie, science et culture."
    },
    "wired.com": {
        "owner": "Condé Nast (Advance Publications)",
        "orientation": "Impact de la technologie sur le futur",
        "funding": "Abonnements & Publicité",
        "country": "États-Unis",
        "description": "Magazine culte explorant les mutations de la société engendrées par l'innovation."
    },
    "arstechnica.com": {
        "owner": "Condé Nast (Advance Publications)",
        "orientation": "Analyses techniques approfondies & IT",
        "funding": "Abonnements (Ars Pro) & Publicité",
        "country": "États-Unis",
        "description": "Publication technique rigoureuse s'adressant aux technologues et scientifiques."
    },
    "huggingface.co": {
        "owner": "Hugging Face Inc. (Indépendant / Investisseurs IA)",
        "orientation": "Open Source IA & Communauté ML",
        "funding": "Modèle freemium cloud & Compute",
        "country": "France / États-Unis",
        "description": "Plateforme centrale mondiale de l'écosystème des modèles et datasets d'intelligence artificielle."
    },
    "arxiv.org": {
        "owner": "Cornell University / Fondation Simons",
        "orientation": "Dépôt d'archives scientifiques ouvertes",
        "funding": "Dons académiques & Fondation philanthropique",
        "country": "États-Unis",
        "description": "Serveur de pré-publication d'articles scientifiques en accès libre (IA, physique, maths)."
    },
    "github.com": {
        "owner": "Microsoft Corporation",
        "orientation": "Développement logiciel & Open Source",
        "funding": "Abonnements SaaS & Entreprise",
        "country": "États-Unis",
        "description": "La plus grande forge logicielle mondiale hébergeant le code open-source de la planète."
    },
    "biorxiv.org": {
        "owner": "Cold Spring Harbor Laboratory (CSHL)",
        "orientation": "Biologie, Médecine & Sciences du Vivant",
        "funding": "Fondations philanthropiques (Chan Zuckerberg Initiative)",
        "country": "États-Unis",
        "description": "Archive ouverte et serveur de pré-publications de référence en biologie et sciences biomédicales."
    },
    "paperswithcode.com": {
        "owner": "Hugging Face / Meta AI & Communauté SOTA",
        "orientation": "Benchmarks IA, Papiers de recherche & Implémentations",
        "funding": "Open Source & Mécénat IA",
        "country": "International",
        "description": "Plateforme de suivi des records et résultats State-of-the-Art (SOTA) en intelligence artificielle avec code associé."
    },
    "openbb.co": {
        "owner": "OpenBB Inc.",
        "orientation": "Données macroéconomiques & Banques centrales",
        "funding": "Open Core & Investisseurs FinTech",
        "country": "États-Unis / Portugal",
        "description": "Alternative libre et ouverte aux terminaux financiers, agrégeant les flux officiels de la BCE, de la Fed et de la BoE."
    },
    "rfi.fr": {
        "owner": "France Médias Monde (État français)",
        "orientation": "Service public international / Francophonie",
        "funding": "Financement public français",
        "country": "France",
        "description": "Radio d'information internationale diffusant en français et 16 autres langues."
    },
    "courrierinternational.com": {
        "owner": "Groupe Le Monde",
        "orientation": "Presse mondiale traduite / Pluralisme des regards",
        "funding": "Abonnements & Kiosque",
        "country": "France",
        "description": "Sélection et traduction en français des meilleurs articles de la presse mondiale."
    }
}

class SourceReputationDB:
    @staticmethod
    def evaluate_domain(domain: str) -> Tuple[float, int]:
        """Returns (trust_score: float, tier: int)."""
        clean_domain = domain.lower().replace("www.", "").strip()
        
        # Exact match
        if clean_domain in TIER_1_REPUTATION:
            return TIER_1_REPUTATION[clean_domain], 1
        if clean_domain in TIER_3_TABLOIDS_AND_UNRELIABLE:
            return TIER_3_TABLOIDS_AND_UNRELIABLE[clean_domain], 3
            
        # Suffix matching (e.g. news.bbc.com)
        for d, score in TIER_1_REPUTATION.items():
            if clean_domain.endswith("." + d) or clean_domain == d:
                return score, 1
                
        for d, score in TIER_3_TABLOIDS_AND_UNRELIABLE.items():
            if clean_domain.endswith("." + d) or clean_domain == d:
                return score, 3
                
        # Default Tier 2 (Standard verified source)
        return 0.75, 2

    @staticmethod
    @functools.lru_cache(maxsize=4096)
    def _lookup_media_profile_cached(clean: str) -> Dict[str, Optional[str]]:
        # 1. Direct domain match
        if clean in MEDIA_PROFILES:
            return MEDIA_PROFILES[clean]
            
        # 2. Domain suffix match
        for d, prof in MEDIA_PROFILES.items():
            if clean.endswith("." + d) or d in clean:
                return prof
                
        # 3. Heuristic matching based on name / domain keywords
        if "lemonde" in clean or "le monde" in clean:
            return MEDIA_PROFILES["lemonde.fr"]
        if "figaro" in clean:
            return MEDIA_PROFILES["lefigaro.fr"]
        if "echos" in clean:
            return MEDIA_PROFILES["lesechos.fr"]
        if "reuters" in clean:
            return MEDIA_PROFILES["reuters.com"]
        if "bloomberg" in clean:
            return MEDIA_PROFILES["bloomberg.com"]
        if "bbc" in clean:
            return MEDIA_PROFILES["bbc.com"]
        if "guardian" in clean:
            return MEDIA_PROFILES["theguardian.com"]
        if "cnews" in clean:
            return MEDIA_PROFILES["cnews.fr"]
        if "bfm" in clean:
            return MEDIA_PROFILES["bfmtv.com"]
        if "hugging" in clean:
            return MEDIA_PROFILES["huggingface.co"]
        if "arxiv" in clean:
            return MEDIA_PROFILES["arxiv.org"]
        if "biorxiv" in clean or "medrxiv" in clean:
            return MEDIA_PROFILES["biorxiv.org"]
        if "paperswithcode" in clean or "papers with code" in clean or "sota" in clean:
            return MEDIA_PROFILES["paperswithcode.com"]
        if "openbb" in clean:
            return MEDIA_PROFILES["openbb.co"]
        if "github" in clean:
            return MEDIA_PROFILES["github.com"]
        if "rfi" in clean:
            return MEDIA_PROFILES["rfi.fr"]
        if "france info" in clean or "franceinfo" in clean or "radiofrance" in clean:
            return MEDIA_PROFILES["francetvinfo.fr"]
        if "courrier" in clean:
            return MEDIA_PROFILES["courrierinternational.com"]

        # 4. Default fallback profile: None values (no placeholder filler text)
        return {
            "owner": None,
            "orientation": None,
            "funding": None,
            "country": None,
            "description": None
        }

    @staticmethod
    def get_media_profile(domain_or_name: str) -> Dict[str, Optional[str]]:
        """Returns comprehensive media ownership and orientation profile, or None if unknown."""
        clean = (domain_or_name or "").lower().replace("www.", "").strip()
        prof = SourceReputationDB._lookup_media_profile_cached(clean)
        return dict(prof) if prof else {}

