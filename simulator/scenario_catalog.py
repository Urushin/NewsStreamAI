"""
NewsStreamAI — Dynamic Simulation Scenario Catalog & Generator
Provides rotating multi-source breaking news events and single-source discovery signals
across AI, Manga, Gaming, Space, Cybersecurity, Finance, Climate, and Health.
Guarantees fresh, diverse stories on every simulation run.
"""
import os
import random
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class SimulationScenarioManager:
    def __init__(self):
        self._recently_used_ids: List[str] = []
        self._max_recent_history = 12

    def get_scenarios(self) -> List[Dict[str, Any]]:
        """Returns the full catalog of multi-source breaking event scenarios."""
        return [
            # ── 1. IA & Modèles Révolutionnaires ──
            {
                "id": "ai_llama4_frontier",
                "category": "Tech & Science",
                "topic": "IA & Modèles Révolutionnaires",
                "articles": [
                    {
                        "source": "TechCrunch",
                        "domain": "techcrunch.com",
                        "title": "Meta dévoile Llama 4 : un modèle de 400 milliards de paramètres rivalisant avec les meilleurs systèmes fermés",
                        "content": "Meta vient de publier la suite Llama 4 en open-weights complet, intégrant un raisonnement multi-modal natif et une fenêtre de contexte de 1 million de tokens.",
                        "comments": [{"text": "Le saut qualitatif sur le raisonnement mathématique en local est bluffant."}]
                    },
                    {
                        "source": "Reuters",
                        "domain": "reuters.com",
                        "title": "Llama 4 : Meta accélère la course à l'IA ouverte et bouscule le modèle économique propriétaire",
                        "content": "L'annonce de Mark Zuckerberg met sous pression les acteurs de l'IA commerciale en rendant accessible une puissance de calcul de pointe sans frais de licence.",
                        "comments": [{"text": "C'est un coup dur pour les modèles payants d'entrée de gamme."}]
                    },
                    {
                        "source": "Le Monde",
                        "domain": "lemonde.fr",
                        "title": "Avec Llama 4, l'intelligence artificielle open source franchit un cap historique face aux géants américains",
                        "content": "Les benchmarks indépendants confirment que le nouveau modèle de Meta égale GPT-4o sur la programmation et la synthèse de documents complexes.",
                        "comments": []
                    }
                ]
            },

            # ── 2. Manga & Anime : Void Century ──
            {
                "id": "manga_onepiece_void_century",
                "category": "Manga & Anime",
                "topic": "Manga & Anime",
                "articles": [
                    {
                        "source": "Anime News Network",
                        "domain": "animenewsnetwork.com",
                        "title": "One Piece : Eiichiro Oda et le Shonen Jump confirment les révélations ultimes sur le Siècle Oublié",
                        "content": "Dans une interview accordée au Weekly Shonen Jump, l'auteur précise que les chapitres à venir lèveront enfin le voile sur Joy Boy, les Armes Antiques et la géographie originelle du monde.",
                        "comments": [{"text": "Vingt-sept ans d'attente pour enfin comprendre la véritable nature du One Piece !"}]
                    },
                    {
                        "source": "Manga-News",
                        "domain": "manga-news.com",
                        "title": "One Piece entre dans sa phase culminante : planning spécial et chapitres étendus annoncés",
                        "content": "La Shueisha annonce un rythme de parution renforcé accompagné de pages en couleur pour marquer le dénouement de la saga la plus lue de l'histoire du manga.",
                        "comments": [{"text": "Le calendrier dévoilé montre qu'Oda maîtrise son sprint final sans précipitation."}]
                    },
                    {
                        "source": "Crunchyroll News",
                        "domain": "crunchyroll.com",
                        "title": "L'arc final de One Piece dévoile ses secrets : les lecteurs du monde entier en ébullition",
                        "content": "Les librairies japonaises et les plateformes internationales de lecture numérique enregistrent un pic d'affluence historique à l'approche de la parution du chapitre clé.",
                        "comments": []
                    }
                ]
            },

            # ── 3. Gaming : Nintendo Switch 2 ──
            {
                "id": "gaming_switch2_official",
                "category": "Jeux Vidéo & Esport",
                "topic": "Gaming & Consoles",
                "articles": [
                    {
                        "source": "IGN",
                        "domain": "ign.com",
                        "title": "Nintendo officialise la Switch 2 : écran OLED 120Hz, compatibilité totale et nouveau Mario 3D",
                        "content": "Nintendo a diffusé une présentation surprise confirmant le successeur de sa console hybride, équipée d'un processeur Nvidia custom avec DLSS 3.5 et d'une rétrocompatibilité physique complète.",
                        "comments": [{"text": "La rétrocompatibilité avec la ludothèque existante à 60 FPS est le point clé !"}]
                    },
                    {
                        "source": "Jeuxvideo.com",
                        "domain": "jeuxvideo.com",
                        "title": "Nintendo Switch 2 : prix, date de sortie et catalogue de lancement officialisés",
                        "content": "La console sortira fin 2026 au tarif de 449€ avec une dizaine de titres exclusifs majeurs et une interface utilisateur repensée pour le jeu compétitif et le streaming local.",
                        "comments": [{"text": "Le positionnement prix reste raisonnable compte tenu des capacités graphiques annoncées."}]
                    },
                    {
                        "source": "Eurogamer",
                        "domain": "eurogamer.net",
                        "title": "Switch 2 analysis: how custom Nvidia silicon enables 4K ray-traced hybrid gaming",
                        "content": "Digital Foundry dissects the technical specifications of Nintendo's upcoming flagship hardware and its architectural leap over previous generation handhelds.",
                        "comments": []
                    }
                ]
            },

            # ── 4. Espace & Découverte Exoplanète ──
            {
                "id": "space_jwst_biosignature",
                "category": "Tech & Science",
                "topic": "Espace & Astronomie",
                "articles": [
                    {
                        "source": "Nature",
                        "domain": "nature.com",
                        "title": "Le télescope spatial James Webb identifie des signatures atmosphériques compatibles avec la vie sur LHS 1140 b",
                        "content": "Une équipe internationale d'astrophysiciens a détecté des concentrations anormales de sulfure de diméthyle et de vapeur d'eau dans l'atmosphère de cette super-Terre située à 48 années-lumière.",
                        "comments": [{"text": "C'est l'indice le plus solide jamais collecté hors du système solaire, même s'il faut rester prudent sur l'origine biotique."}]
                    },
                    {
                        "source": "BBC News",
                        "domain": "bbc.com",
                        "title": "James Webb telescope finds tantalising signs of habitable atmosphere on ocean exoplanet",
                        "content": "Spectroscopic measurements indicate LHS 1140 b could host a global temperate ocean and a nitrogen-rich atmosphere shielded by a strong magnetic dipole.",
                        "comments": [{"text": "Next scheduled observation campaign in autumn will confirm isotope ratios."}]
                    },
                    {
                        "source": "Futura Sciences",
                        "domain": "futura-sciences.com",
                        "title": "Exoplanètes : James Webb confirme l'existence d'un monde océan tempéré",
                        "content": "Les données du spectrographe NIRSpec valident la présence d'une atmosphère dense et stable, écartant l'hypothèse d'une planète naine gazeuse stérile.",
                        "comments": []
                    }
                ]
            },

            # ── 5. Cybersécurité : Faille Critique Post-Quantique ──
            {
                "id": "cyber_post_quantum_alert",
                "category": "Tech & Science",
                "topic": "Cybersécurité & Réseaux",
                "articles": [
                    {
                        "source": "The Hacker News",
                        "domain": "thehackernews.com",
                        "title": "Alerte mondiale : Faille critique zero-day découverte dans les algorithmes cryptographiques post-quantiques",
                        "content": "Des chercheurs du MIT ont mis en évidence une vulnérabilité mathématique dans l'implémentation de référence de Kyber permettant la récupération de clés en temps polynomial.",
                        "comments": [{"text": "Le NIST convoque une réunion d'urgence pour réviser les paramètres des standards."}]
                    },
                    {
                        "source": "BleepingComputer",
                        "domain": "bleepingcomputer.com",
                        "title": "Emergency patch rollout across major cloud providers following post-quantum crypto flaw",
                        "content": "Amazon AWS, Microsoft Azure and Google Cloud are deploying architectural mitigations to prevent side-channel key extraction on cryptographic accelerators.",
                        "comments": []
                    },
                    {
                        "source": "Zataz",
                        "domain": "zataz.com",
                        "title": "Cybersécurité : les protocoles de chiffrement de nouvelle génération soumis à un audit sans précédent",
                        "content": "L'ANSSI et les agences européennes recommandent l'activation temporaire de schémas hybrides associant cryptographie classique et réseaux euclidiens renforcés.",
                        "comments": []
                    }
                ]
            },

            # ── 6. Finance : Monnaie Numérique Interbancaire ──
            {
                "id": "finance_instant_settlement",
                "category": "Économie & Finance",
                "topic": "Banques & Finance Mondiale",
                "articles": [
                    {
                        "source": "Financial Times",
                        "domain": "ft.com",
                        "title": "Central banks launch unified instant cross-border settlement system to replace SWIFT friction",
                        "content": "The Bank for International Settlements together with the ECB, the Fed and the Bank of Japan have unveiled Project Agora, enabling 24/7 sub-second wholesale settlement.",
                        "comments": [{"text": "Transaction costs for multinational trade will drop from days to milliseconds."}]
                    },
                    {
                        "source": "Les Échos",
                        "domain": "lesechos.fr",
                        "title": "Révolution des paiements : les banques centrales officialisent le règlement international instantané",
                        "content": "Ce système tokenisé sécurisé par des nœuds souverains permet d'éliminer les décalages de change et le risque de contrepartie dans les transactions interbancaires.",
                        "comments": [{"text": "C'est une transformation profonde de la tuyauterie financière globale."}]
                    },
                    {
                        "source": "Bloomberg",
                        "domain": "bloomberg.com",
                        "title": "Project Agora goes live: 40 global commercial banks join synchronized tokenized currency network",
                        "content": "Major tier-one financial institutions complete first live cross-currency settlement between Tokyo, Frankfurt and New York.",
                        "comments": []
                    }
                ]
            },

            # ── 7. Climat : Batterie Tout-Solide 1200 km ──
            {
                "id": "climate_solid_state_battery",
                "category": "Climat & Environnement",
                "topic": "Transition Énergétique",
                "articles": [
                    {
                        "source": "Les Échos",
                        "domain": "lesechos.fr",
                        "title": "Batteries tout-solide : un consortium européen annonce une autonomie record de 1 200 km et 8 minutes de recharge",
                        "content": "La nouvelle technologie à électrolyte céramique sans risque d'emballement thermique franchit avec succès la phase pilote d'industrialisation en Allemagne et en France.",
                        "comments": [{"text": "Si le coût au kWh passe sous la barre des 70 dollars, le moteur thermique est définitivement obsolète."}]
                    },
                    {
                        "source": "Wired",
                        "domain": "wired.com",
                        "title": "Solid-state battery breakthrough delivers 1,200 km range with non-flammable electrolyte",
                        "content": "Automotive engineers validate 2,000 deep charge cycles with zero volumetric degradation, paving the way for commercial mass adoption in 2027.",
                        "comments": []
                    },
                    {
                        "source": "Futura Sciences",
                        "domain": "futura-sciences.com",
                        "title": "Véhicules électriques : la fin définitive de l'angoisse de la panne avec la batterie solide",
                        "content": "Les tests indépendants en conditions hivernales à -20°C confirment une rétention de capacité supérieure à 92%, résolvant le principal talon d'Achille des accumulateurs actuels.",
                        "comments": []
                    }
                ]
            },

            # ── 8. Manga : Retour de Hunter x Hunter ──
            {
                "id": "manga_hunter_return",
                "category": "Manga & Anime",
                "topic": "Manga & Anime",
                "articles": [
                    {
                        "source": "Anime News Network",
                        "domain": "animenewsnetwork.com",
                        "title": "Hunter x Hunter : Yoshihiro Togashi confirme l'achèvement de 20 chapitres et un nouveau rythme de parution",
                        "content": "L'auteur mythique de Hunter x Hunter partage les manuscrits finalisés de l'arc du Continent Caché et annonce un partenariat de production avec son équipe d'assistants.",
                        "comments": [{"text": "Kurapika et la guerre de succession vont enfin avoir le dénouement qu'ils méritent !"}]
                    },
                    {
                        "source": "Manga-News",
                        "domain": "manga-news.com",
                        "title": "Le manga Hunter x Hunter reprend sa publication officielle dans le Shonen Jump",
                        "content": "Après plusieurs mois de travail minutieux sur les storyboards, la rédaction du Jump programme la publication continue des nouveaux chapitres à partir du mois prochain.",
                        "comments": [{"text": "C'est la nouvelle que tous les passionnés de manga espéraient."}]
                    }
                ]
            },

            # ── 9. Santé & IA : Molécule Anticancéreuse ──
            {
                "id": "health_ai_cancer_molecule",
                "category": "Tech & Science",
                "topic": "Biotechnologies & Santé",
                "articles": [
                    {
                        "source": "Nature",
                        "domain": "nature.com",
                        "title": "Une molécule conçue par intelligence artificielle montre une rémission complète sur des tumeurs résistantes",
                        "content": "Les résultats des essais cliniques préliminaires publiés ce matin démontrent une sélectivité cellulaire totale sans destruction des globules blancs sains.",
                        "comments": [{"text": "La médecine computationnelle prouve qu'elle peut accélérer de dix ans la conception de thérapies ciblées."}]
                    },
                    {
                        "source": "Le Figaro",
                        "domain": "lefigaro.fr",
                        "title": "Percée thérapeutique : l'IA générative donne naissance à un anticancéreux ultra-ciblé",
                        "content": "L'Institut Gustave Roussy et ses partenaires confirment l'efficacité du composé qui bloque spécifiquement le métabolisme glycolytique des cellules métastatiques.",
                        "comments": []
                    },
                    {
                        "source": "BBC News",
                        "domain": "bbc.com",
                        "title": "AI-designed cancer therapy eliminates drug-resistant tumours in groundbreaking clinical trial",
                        "content": "Oncologists celebrate early data showing zero observed organ toxicity across Phase 1 human cohort.",
                        "comments": []
                    }
                ]
            },

            # ── 10. Espace : Transfert d'Ergols en Orbite SpaceX ──
            {
                "id": "space_starship_refueling",
                "category": "Tech & Science",
                "topic": "Conquête Spatiale",
                "articles": [
                    {
                        "source": "Ars Technica",
                        "domain": "arstechnica.com",
                        "title": "SpaceX réussit le premier transfert de méthane cryogénique entre deux Starship en orbite terrestre",
                        "content": "La démonstration cruciale pour le programme lunaire Artemis III s'est déroulée sans anomalie à 400 km d'altitude, validant le ravitaillement spatial automatisé.",
                        "comments": [{"text": "C'était le verrou technique numéro 1 pour envoyer des charges lourdes vers la Lune et Mars."}]
                    },
                    {
                        "source": "Le Monde",
                        "domain": "lemonde.fr",
                        "title": "Conquête spatiale : SpaceX franchit une étape décisive pour le retour des astronautes sur la Lune",
                        "content": "La NASA salue le succès de l'amarrage dynamique et du transfert de fluide sous microgravité, ouvrant la voie au premier vol d'essai sans équipage autour de la Lune.",
                        "comments": []
                    },
                    {
                        "source": "Reuters",
                        "domain": "reuters.com",
                        "title": "SpaceX completes orbital propellant transfer milestone under NASA Artemis contract",
                        "content": "NASA leadership confirms key mission architecture requirement met ahead of next year's planned lunar lander test flight.",
                        "comments": []
                    }
                ]
            },

            # ── 11. Hardware : Lunettes AR Apple Vision Air ──
            {
                "id": "tech_apple_vision_air",
                "category": "Tech & Science",
                "topic": "Hardware & Réalité Augmentée",
                "articles": [
                    {
                        "source": "Bloomberg",
                        "domain": "bloomberg.com",
                        "title": "Apple présente en avant-première Vision Air : des lunettes de réalité augmentée pesant 75 grammes",
                        "content": "Équipées d'écrans Micro-LED transparents et déportant le calcul lourd sur l'iPhone via une liaison ultra-large bande, les lunettes visent le grand public pour 799$.",
                        "comments": [{"text": "Le format lunettes classiques est enfin atteint, c'est ce que tout le monde attendait depuis dix ans."}]
                    },
                    {
                        "source": "The Verge",
                        "domain": "theverge.com",
                        "title": "Apple Vision Air announced: lightweight spatial computing with all-day battery",
                        "content": "Hands-on impressions highlight seamless eye-tracking gestures and instant Siri visual intelligence overlaid onto the real world.",
                        "comments": []
                    },
                    {
                        "source": "TechCrunch",
                        "domain": "techcrunch.com",
                        "title": "How Apple shrunk spatial computing down to a 75g eyewear form factor",
                        "content": "Engineering deep-dive into the custom silicon, diffractive waveguides, and ambient sensor arrays powering Apple's latest hardware category.",
                        "comments": []
                    }
                ]
            },

            # ── 12. Fusion Nucléaire : Plasma Stable Record ──
            {
                "id": "science_nuclear_fusion_record",
                "category": "Tech & Science",
                "topic": "Physique & Énergie",
                "articles": [
                    {
                        "source": "Nature",
                        "domain": "nature.com",
                        "title": "Fusion nucléaire : le réacteur WEST bat le record mondial de durée de plasma stable à haute température",
                        "content": "Le tokamak français a maintenu un plasma à 50 millions de degrés pendant plus de 20 minutes continues avec des parois internes en tungstène sans érosion mesurable.",
                        "comments": [{"text": "La maîtrise des matériaux face aux flux thermiques extrêmes est le véritable exploit de cette expérience."}]
                    },
                    {
                        "source": "Futura Sciences",
                        "domain": "futura-sciences.com",
                        "title": "Exploit historique en fusion nucléaire : un plasma stable confiné pendant 22 minutes",
                        "content": "Cette performance valide les choix d'ingénierie retenus pour le projet international ITER actuellement en phase d'assemblage à Cadarache.",
                        "comments": []
                    },
                    {
                        "source": "BBC News",
                        "domain": "bbc.com",
                        "title": "Fusion energy milestone: European scientists sustain 50-million-degree plasma for record 22 minutes",
                        "content": "Researchers say long-duration magnetic confinement brings commercial fusion power plant design another major step closer to reality.",
                        "comments": []
                    }
                ]
            },

            # ── 13. Gaming & Esport : GTA VI Multijoueur ──
            {
                "id": "gaming_gta6_reveal",
                "category": "Jeux Vidéo & Esport",
                "topic": "Jeux Vidéo & Esport",
                "articles": [
                    {
                        "source": "Jeuxvideo.com",
                        "domain": "jeuxvideo.com",
                        "title": "Grand Theft Auto VI : Rockstar Games dévoile le mode multijoueur révolutionnaire et la date finale",
                        "content": "Rockstar confirme le moteur physique nouvelle génération et la date de lancement mondial de son mode en ligne persistant.",
                        "comments": [{"text": "L'architecture serveur dynamique avec persistance de l'économie est la vraie surprise."}]
                    },
                    {
                        "source": "IGN",
                        "domain": "ign.com",
                        "title": "GTA 6 reveals groundbreaking online mode with dynamic evolving world architecture",
                        "content": "Official trailer showcases living server architecture with persistent economic ecosystems and real-time volumetric weather.",
                        "comments": []
                    },
                    {
                        "source": "Gamekult",
                        "domain": "gamekult.com",
                        "title": "Rockstar Games détaille les innovations techniques majeures de GTA VI",
                        "content": "Analyse approfondie de la gestion volumétrique, des interactions PNJ basées sur l'apprentissage par renforcement et du framerate cible.",
                        "comments": []
                    }
                ]
            },

            # ── 14. Géopolitique & Lois Maritimes : G7 ──
            {
                "id": "geopolitics_g7_maritime",
                "category": "Politique & Monde",
                "topic": "Politique & Monde",
                "articles": [
                    {
                        "source": "France 24",
                        "domain": "france24.com",
                        "title": "Sommet du G7 : Accord historique trouvé sur la sécurisation des routes maritimes et du commerce mondial",
                        "content": "Les chefs d'État du G7 signent un pacte de protection conjointe des corridors stratégiques maritimes face aux menaces géopolitiques.",
                        "comments": [{"text": "Les armateurs réclamaient ce cadre de coordination naval unifié depuis des mois."}]
                    },
                    {
                        "source": "BBC News",
                        "domain": "bbc.com",
                        "title": "G7 leaders finalize landmark security pact to safeguard international shipping lanes",
                        "content": "Joint naval coordination framework ratified to ensure trade resilience in critical straits and deter maritime aggression.",
                        "comments": []
                    },
                    {
                        "source": "Le Figaro",
                        "domain": "lefigaro.fr",
                        "title": "Pacte de sécurité maritime du G7 : Washington et les alliés déploient une force conjointe",
                        "content": "Nouvelle doctrine de sécurisation face aux perturbations du commerce international et surveillance satellitaire continue.",
                        "comments": []
                    }
                ]
            },

            # ── 15. Semi-conducteurs : OpenAI et TSMC ──
            {
                "id": "ai_tsmc_optics",
                "category": "Tech & Science",
                "topic": "Tech & Semi-conducteurs",
                "articles": [
                    {
                        "source": "Reuters",
                        "domain": "reuters.com",
                        "title": "OpenAI et TSMC scellent un partenariat industriel pour produire des puces photoniques sur silicium",
                        "content": "L'accord prévoit la production de puces optiques réduisant de 85% la consommation énergétique des clusters d'intelligence artificielle.",
                        "comments": [{"text": "C'est une rupture majeure si le gain d'efficacité énergétique de 85% se confirme en conditions réelles de datacenter."}]
                    },
                    {
                        "source": "Bloomberg",
                        "domain": "bloomberg.com",
                        "title": "TSMC and OpenAI enter landmark manufacturing deal for custom optical AI silicon",
                        "content": "Strategic industrial foundry agreement to scale optical computing chips against traditional GPU dominance.",
                        "comments": []
                    },
                    {
                        "source": "Le Monde",
                        "domain": "lemonde.fr",
                        "title": "Puces IA : L'alliance industrielle entre OpenAI et TSMC confirmée ce matin",
                        "content": "Déploiement massif prévu dès 2026 dans les datacenters de nouvelle génération pour contourner la saturation du cuivre.",
                        "comments": []
                    }
                ]
            },

            # ── 16. Anime & Pop Culture : Jujutsu Kaisen ──
            {
                "id": "anime_jujutsu_kaisen_movie",
                "category": "Manga & Anime",
                "topic": "Manga & Animation",
                "articles": [
                    {
                        "source": "Anime News Network",
                        "domain": "animenewsnetwork.com",
                        "title": "Jujutsu Kaisen : MAPPA officialise le film d'animation mondial pour la Traque Meurtrière",
                        "content": "Le studio d'animation japonais confirme une sortie mondiale simultanée en salles IMAX pour clore l'arc de la Traque Meurtrière avant la suite en série.",
                        "comments": [{"text": "La qualité de production de MAPPA pour le combat de Hakari va être époustouflante !"}]
                    },
                    {
                        "source": "Crunchyroll News",
                        "domain": "crunchyroll.com",
                        "title": "Jujutsu Kaisen annonce son prochain long-métrage avec bande-annonce et affiche teaser",
                        "content": "Gege Akutami signe une illustration exclusive pour accompagner l'annonce du retour de la franchise numéro 1 du shonen moderne.",
                        "comments": []
                    }
                ]
            },

            # ── 17. Marchés & Crypto : ETF Spot ──
            {
                "id": "crypto_etf_expansion",
                "category": "Économie & Finance",
                "topic": "Marchés & Crypto-actifs",
                "articles": [
                    {
                        "source": "Bloomberg",
                        "domain": "bloomberg.com",
                        "title": "SEC approves first spot multi-asset cryptocurrency ETF basket for US institutional investors",
                        "content": "Regulatory green light opens door for institutional pensions to hold diversified digital asset baskets through regulated custodians.",
                        "comments": [{"text": "Major milestone for institutional portfolio allocation."}]
                    },
                    {
                        "source": "Les Échos",
                        "domain": "lesechos.fr",
                        "title": "Marchés financiers : Wall Street accueille les premiers paniers indiciels d'actifs numériques régulés",
                        "content": "Plus de 2 milliards de dollars de souscriptions enregistrées lors des deux premières heures de cotation à New York.",
                        "comments": []
                    }
                ]
            },

            # ── 18. Robotique & Industrie : Robots Humanoïdes ──
            {
                "id": "robotics_humanoid_mass_production",
                "category": "Tech & Science",
                "topic": "Robotique & Automatisation",
                "articles": [
                    {
                        "source": "TechCrunch",
                        "domain": "techcrunch.com",
                        "title": "Déploiement record de 5 000 robots humanoïdes autonomes dans les lignes d'assemblage automobile",
                        "content": "Les robots de nouvelle génération réalisent désormais des tâches de précision logistique et de vissage complexe sans intervention humaine.",
                        "comments": [{"text": "L'autonomie motrice et l'adaptation aux imprévus ont progressé de manière fulgurante."}]
                    },
                    {
                        "source": "Reuters",
                        "domain": "reuters.com",
                        "title": "Industrial robotics reaches inflection point with fleet of autonomous bipedal workers",
                        "content": "Automakers report 40% reduction in repetitive injury rates and improved throughput in assembly operations.",
                        "comments": []
                    }
                ]
            }
        ]

    def get_single_source_signals(self) -> List[Dict[str, Any]]:
        """Returns isolated preliminary signals (1 single source)."""
        return [
            {
                "title": "Découverte d'un gisement géant d'hydrogène blanc naturel dans les Pyrénées",
                "source": "Futura Sciences",
                "domain": "futura-sciences.com",
                "category": "Climat & Environnement",
                "content": "Une équipe géologique identifie une réserve potentielle de plusieurs millions de tonnes d'hydrogène décarboné sous le piémont pyrénéen."
            },
            {
                "title": "Archéologie sous-marine : une cité engloutie datant de 7 500 ans découverte en mer Adriatique",
                "source": "National Geographic",
                "domain": "nationalgeographic.com",
                "category": "Culture & Savoir",
                "content": "Des relevés bathymétriques 3D révèlent des structures en pierre mégalithiques exceptionnellement bien conservées sous 20 mètres d'eau."
            },
            {
                "title": "Record mondial : un train expérimental à sustentation magnétique atteint 623 km/h sur voie sous vide",
                "source": "Railway Gazette",
                "domain": "railwaygazette.com",
                "category": "Tech & Science",
                "content": "La ligne d'essai à basse pression atmosphérique confirme la viabilité des liaisons interurbaines ultra-rapides sans frottement mécanique."
            },
            {
                "title": "Lentilles de contact bioniques : un brevet déposé pour un affichage rétinien alimenté par les larmes",
                "source": "IEEE Spectrum",
                "domain": "spectrum.ieee.org",
                "category": "Tech & Science",
                "content": "Des micro-piles à biocarburant exploitant le glucose lacrymal permettent d'alimenter une matrice d'affichage de 64 pixels sans batterie externe."
            },
            {
                "title": "Biologie marine : découverte d'un récif corallien géant et florissant à 400 mètres de profondeur au large des Galápagos",
                "source": "Nature Ocean",
                "domain": "nature.com",
                "category": "Climat & Environnement",
                "content": "Une mission sous-marine avec ROV documente un écosystème corallien intact s'étendant sur plusieurs kilomètres carrés en eaux froides."
            },
            {
                "title": "Cyberdéfense : démantèlement par Interpol d'un réseau de botnets exploitant des routeurs domestiques pour miner de la crypto",
                "source": "Zataz",
                "domain": "zataz.com",
                "category": "Tech & Science",
                "content": "L'opération conjointe a permis de neutraliser plus de 300 000 appareils infectés à travers 40 pays sans interruption pour les utilisateurs."
            },
            {
                "title": "Manga : annonce d'une adaptation anime de prestige pour le webtoon viral 'Omniscient Reader' par le studio Ufotable",
                "source": "Anime Corner",
                "domain": "animecorner.me",
                "category": "Manga & Anime",
                "content": "La bande-annonce teaser dévoilée lors de la convention de Séoul confirme une sortie mondiale simultanée en haute définition."
            },
            {
                "title": "Astronomie : un nouvel astéroïde géocroiseur riche en platine et nickel détecté par le relevé Pan-STARRS",
                "source": "Space.com",
                "domain": "space.com",
                "category": "Tech & Science",
                "content": "L'objet céleste d'environ 300 mètres de diamètre ne présente aucun danger pour la Terre et suscite déjà l'intérêt des entreprises minières spatiales."
            }
        ]

    def generate_simulation_batch(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        Picks 'count' multi-source scenarios plus 1-2 single-source signals.
        Guarantees that scenarios used recently are excluded to provide 100% fresh news every run.
        """
        all_scenarios = self.get_scenarios()
        
        # Filter out recently used scenarios if possible
        available = [s for s in all_scenarios if s["id"] not in self._recently_used_ids]
        if len(available) < count:
            # Clear oldest history if pool exhausted
            self._recently_used_ids = self._recently_used_ids[-(len(all_scenarios) - count):]
            available = [s for s in all_scenarios if s["id"] not in self._recently_used_ids]

        if not available:
            available = all_scenarios

        # Pick 'count' random distinct scenarios
        selected_scenarios = random.sample(available, min(count, len(available)))

        # Update FIFO history
        for s in selected_scenarios:
            self._recently_used_ids.append(s["id"])
        if len(self._recently_used_ids) > self._max_recent_history:
            self._recently_used_ids = self._recently_used_ids[-self._max_recent_history:]

        batch: List[Dict[str, Any]] = []

        # Process each multi-source scenario into concrete articles with unique hashes & fresh timestamps
        for scenario in selected_scenarios:
            unique_cluster_seed = os.urandom(4).hex()
            for art in scenario["articles"]:
                hash_id = os.urandom(3).hex()
                batch.append({
                    "title": art["title"],
                    "url": f"https://www.{art['domain']}/news/{scenario['id']}-{unique_cluster_seed}-{hash_id}",
                    "domain": art["domain"],
                    "source": art["source"],
                    "content": art["content"],
                    "category": scenario["category"],
                    "comments": art.get("comments", [])
                })

        # Add 1 or 2 random isolated signals for single-source discovery bubble
        single_signals = self.get_single_source_signals()
        avail_singles = [s for s in single_signals if s["title"] not in getattr(self, "_recently_used_single_titles", [])]
        if len(avail_singles) < 2:
            self._recently_used_single_titles = []
            avail_singles = single_signals
        chosen_singles = random.sample(avail_singles, min(2, len(avail_singles)))
        if not hasattr(self, "_recently_used_single_titles"):
            self._recently_used_single_titles = []
        for s in chosen_singles:
            self._recently_used_single_titles.append(s["title"])
            hash_id = os.urandom(3).hex()
            batch.append({
                "title": s["title"],
                "url": f"https://www.{s['domain']}/articles/{hash_id}",
                "domain": s["domain"],
                "source": s["source"],
                "content": s["content"],
                "category": s["category"],
                "comments": []
            })

        # Shuffle articles so multi-source streams interleave realistically during ingestion
        random.shuffle(batch)
        return batch

simulation_scenario_manager = SimulationScenarioManager()
